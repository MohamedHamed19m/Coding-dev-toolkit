import struct
from typing import Dict, Tuple
from scapy.packet import Packet
from scapy.layers.inet import IP, TCP

# Import the Pydantic models we defined in Option 1
from core_models import (
    TCPConnection, TCPState, TCPStateTransition, 
    DiagnosticSession, DoIPNodeInfo
)

class DiagnosticStateEngine:
    """
    Maintains stateful context for TCP connections and DoIP/UDS sessions.
    Designed to be fed packets one-by-one in an O(1) streaming loop.
    """
    def __init__(self):
        # Maps normalized 5-tuple -> TCPConnection
        self.tcp_connections: Dict[Tuple, TCPConnection] = {}
        # Maps connection_id -> DiagnosticSession
        self.diagnostic_sessions: Dict[str, DiagnosticSession] = {}
        # Maps connection_id -> last seen sequence numbers for retransmission detection
        self._seq_tracker: Dict[str, Dict[str, int]] = {}

    def _get_connection_key(self, src_ip, src_port, dst_ip, dst_port) -> Tuple:
        """Normalizes the 5-tuple so A->B and B->A map to the exact same connection object."""
        tuple1 = (src_ip, src_port, dst_ip, dst_port)
        tuple2 = (dst_ip, dst_port, src_ip, src_port)
        return tuple1 if tuple1 < tuple2 else tuple2

    def ingest_packet(self, pkt: Packet, timestamp: float):
        """Main entry point for the streaming parser."""
        if not pkt.haslayer(IP) or not pkt.haslayer(TCP):
            return

        ip_layer = pkt[IP]
        tcp_layer = pkt[TCP]
        
        # 1. TCP State Machine & Connection Tracking (Phase 2)
        conn = self._process_tcp_layer(ip_layer, tcp_layer, timestamp)
        
        # 2. DoIP Protocol Decoding (Phase 1 Expansion)
        payload = bytes(tcp_layer.payload)
        if payload and (tcp_layer.sport == 13400 or tcp_layer.dport == 13400):
            self._process_doip_layer(payload, timestamp, conn)

    def _process_tcp_layer(self, ip, tcp, timestamp) -> TCPConnection:
        key = self._get_connection_key(ip.src, tcp.sport, ip.dst, tcp.dport)
        
        # Initialize Connection & Session if new
        if key not in self.tcp_connections:
            conn = TCPConnection(
                src_ip=ip.src, dst_ip=ip.dst,
                src_port=tcp.sport, dst_port=tcp.dport,
                creation_time=timestamp
            )
            self.tcp_connections[key] = conn
            self.diagnostic_sessions[conn.connection_id] = DiagnosticSession(
                tester_ip=ip.src, ecu_ip=ip.dst, start_time=timestamp
            )
        else:
            conn = self.tcp_connections[key]

        # --- TCP State Machine Logic (Phase 2) ---
        flags = str(tcp.flags).upper()
        old_state = conn.current_state
        new_state = old_state

        if 'R' in flags:
            new_state = TCPState.RESET
            conn.close_time = timestamp
        elif 'S' in flags and 'A' not in flags:
            new_state = TCPState.SYN_SENT
        elif 'S' in flags and 'A' in flags:
            new_state = TCPState.SYN_RECEIVED
        elif 'F' in flags:
            if old_state == TCPState.ESTABLISHED:
                new_state = TCPState.FIN_WAIT_1
            elif old_state in [TCPState.FIN_WAIT_1, TCPState.FIN_WAIT_2]:
                new_state = TCPState.CLOSING
            elif old_state == TCPState.CLOSE_WAIT:
                new_state = TCPState.LAST_ACK
        elif 'A' in flags and 'S' not in flags and 'F' not in flags and 'R' not in flags:
            if old_state == TCPState.SYN_RECEIVED:
                new_state = TCPState.ESTABLISHED
            elif old_state == TCPState.FIN_WAIT_1:
                new_state = TCPState.FIN_WAIT_2
            elif old_state == TCPState.CLOSING:
                new_state = TCPState.TIME_WAIT
            elif old_state == TCPState.LAST_ACK:
                new_state = TCPState.CLOSED
                conn.close_time = timestamp

        # Record State Transition
        if new_state != old_state:
            conn.current_state = new_state
            conn.state_history.append(TCPStateTransition(
                timestamp=timestamp, old_state=old_state, new_state=new_state,
                flags=flags, seq_num=tcp.seq, ack_num=tcp.ack
            ))

        # --- Metrics & Retransmission Detection ---
        payload_len = len(tcp.payload)
        conn.bytes_transferred += payload_len
        
        if tcp.window == 0:
            conn.zero_window_count += 1

        # Retransmission Detection (Phase 2)
        # If we see the same sequence number again with payload, it's a retransmit
        if payload_len > 0:
            tracker = self._seq_tracker.setdefault(conn.connection_id, {})
            direction = f"{ip.src}:{tcp.sport}"
            last_seq = tracker.get(direction)
            if last_seq is not None and tcp.seq <= last_seq:
                conn.retransmission_count += 1
            tracker[direction] = tcp.seq + payload_len

        return conn

    def _process_doip_layer(self, payload: bytes, timestamp: float, conn: TCPConnection):
        if len(payload) < 8:
            return
            
        try:
            version, inv_version, payload_type, length = struct.unpack("!BBHI", payload[:8])
            if inv_version != (0xFF ^ version):
                return
                
            doip_data = payload[8:8+length]
            session = self.diagnostic_sessions[conn.connection_id]
            
            # --- Phase 1: Full ISO 13400 Coverage ---
            
            if payload_type == 0x0005 and len(doip_data) >= 3:
                # Routing Activation Request
                sa = struct.unpack("!H", doip_data[0:2])[0]
                session.tester_logical_address = sa
                session.doip_routing_metrics.requests_sent += 1
                
            elif payload_type == 0x0006 and len(doip_data) >= 5:
                # Routing Activation Response
                sa = struct.unpack("!H", doip_data[0:2])[0]
                ta = struct.unpack("!H", doip_data[2:4])[0]
                resp_code = doip_data[4]
                
                session.ecu_logical_address = ta
                if resp_code == 0x00:
                    session.doip_routing_metrics.successes += 1
                else:
                    session.doip_routing_metrics.failures += 1
                    code_counts = session.doip_routing_metrics.failure_codes
                    code_counts[resp_code] = code_counts.get(resp_code, 0) + 1
                    
            elif payload_type == 0x4002 and len(doip_data) >= 7:
                # Entity Status Response (Node Type, Max Sockets, Curr Sockets, Max Data Size)
                if not session.doip_node_info:
                    session.doip_node_info = DoIPNodeInfo(logical_address=session.ecu_logical_address or 0)
                
                session.doip_node_info.node_type = doip_data[0]
                session.doip_node_info.max_sockets = doip_data[1]
                session.doip_node_info.current_sockets = doip_data[2]
                session.doip_node_info.max_data_size = struct.unpack("!I", doip_data[3:7])[0]
                
            elif payload_type == 0x0004 and len(doip_data) >= 33:
                # Vehicle Announcement / Identification Response
                vin = doip_data[0:17].decode('ascii', errors='ignore').strip('\x00')
                logical_addr = struct.unpack("!H", doip_data[17:19])[0]
                eid = doip_data[19:25].hex().upper()
                gid = doip_data[25:31].hex().upper()
                
                if not session.doip_node_info:
                    session.doip_node_info = DoIPNodeInfo(logical_address=logical_addr)
                session.doip_node_info.vin = vin
                session.doip_node_info.eid = eid
                session.doip_node_info.gid = gid
                
            elif payload_type == 0x0007:
                session.doip_alive_check_metrics.requests_sent += 1
                
            elif payload_type == 0x0008:
                session.doip_alive_check_metrics.responses_received += 1
                
        except Exception:
            pass # Fail-safe for malformed packets during streaming
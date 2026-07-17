"""
global_parser.py
Production-Grade Universal Diagnostic Log Parser
Integrates O(1) streaming, deep protocol decoding, and stateful context tracking.
"""
import os
import struct
import logging
from typing import Generator, Optional, Tuple
from pydantic import BaseModel, Field

# External Libraries
try:
    from scapy.all import Ether, IP, TCP, UDP
    from scapy.utils import PcapReader
    import can
    from vblf.reader import BlfReader
except ImportError as e:
    print(f"[CRITICAL] Missing dependencies: {e}")
    print("Please run: pip install scapy python-can vblf pydantic")
    import sys
    sys.exit(1)

# Internal State Engine
from state_engine import DiagnosticStateEngine

# -----------------------------------------------------------------------------
# AI & Programmatic Data Models (The "Machine" Layer)
# -----------------------------------------------------------------------------
class TCPContext(BaseModel):
    connection_id: Optional[str] = None
    flags: Optional[str] = None
    seq: Optional[int] = None
    ack: Optional[int] = None

class DoIPContext(BaseModel):
    payload_type: Optional[int] = None
    payload_name: Optional[str] = None
    sa: Optional[int] = None
    ta: Optional[int] = None
    uds_sid: Optional[int] = None
    uds_nrc: Optional[int] = None

class CANContext(BaseModel):
    arbitration_id: int
    is_extended: bool
    dlc: int
    is_fd: bool
    channel: Optional[int] = None

class LogEvent(BaseModel):
    """The universal output object. Satisfies both Human CLI and AI Agents."""
    frame_idx: int
    timestamp: float
    layer: str  # "Ethernet" or "CAN"
    summary: str  # Human-readable formatted string
    
    # Structured contexts for AI / Programmatic use
    tcp: Optional[TCPContext] = None
    doip: Optional[DoIPContext] = None
    can: Optional[CANContext] = None
    
    # Relational IDs from State Engine (Crucial for Phase 7 Query Engine)
    connection_id: Optional[str] = None
    session_id: Optional[str] = None

    # CLI FILTERING:
    src_mac: Optional[str] = None
    dst_mac: Optional[str] = None
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    proto: Optional[str] = None

# -----------------------------------------------------------------------------
# Protocol Dictionaries
# -----------------------------------------------------------------------------
UDS_SERVICES = {
    0x10: "Session Control", 0x11: "ECU Reset", 0x27: "Security Access",
    0x34: "Request Download", 0x36: "Transfer Data", 0x3E: "Tester Present", 0x7F: "Negative Response"
}
UDS_NRCS = {
    0x10: "General Reject", 0x33: "Security Denied", 0x78: "Response Pending", 0x35: "Invalid Key"
}

# -----------------------------------------------------------------------------
# Global Parser Engine
# -----------------------------------------------------------------------------
class GlobalParser:
    def __init__(self):
        self.engine = DiagnosticStateEngine()
        
    def parse(self, file_path: str, limit: Optional[int] = None) -> Generator[LogEvent, None, None]:
        """Auto-detects format and yields structured LogEvents in O(1) memory."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        with open(file_path, "rb") as f:
            magic = f.read(4)
            
        if magic == b"LOGG":
            is_ethernet = self._peek_blf_for_ethernet(file_path)
            if is_ethernet:
                yield from self._parse_ethernet_blf(file_path, limit)
            else:
                yield from self._parse_can_blf(file_path, limit)
        elif magic in [b"\xd4\xc3\xb2\xa1", b"\xa1\xb2\xc3\xd4", b"\n\r\r\n"]:
            yield from self._parse_pcap(file_path, limit)
        else:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in [".pcap", ".pcapng"]:
                yield from self._parse_pcap(file_path, limit)
            elif ext == ".blf":
                yield from self._parse_can_blf(file_path, limit)
            else:
                raise ValueError(f"Unsupported file format signature: {magic.hex()}")

    def _peek_blf_for_ethernet(self, file_path: str) -> bool:
        try:
            with BlfReader(file_path) as reader:
                for idx, obj in enumerate(reader):
                    if obj.header.base.object_type.name in ["ETHERNET_FRAME", "ETHERNET_FRAME_EX"]:
                        return True
                    if idx >= 50: break
        except Exception: pass
        return False

    # --- STREAMING PARSERS ---
    def _parse_pcap(self, file_path: str, limit: Optional[int]) -> Generator[LogEvent, None, None]:
        count = 0
        with PcapReader(file_path) as reader:
            for idx, pkt in enumerate(reader):
                if limit and count >= limit: break
                timestamp = float(pkt.time)
                if IP in pkt and TCP in pkt:
                    self.engine.ingest_packet(pkt, timestamp)
                event = self._process_ethernet_packet(pkt, timestamp, idx + 1)
                if event:
                    count += 1
                    yield event

    def _parse_ethernet_blf(self, file_path: str, limit: Optional[int]) -> Generator[LogEvent, None, None]:
        count = 0
        with BlfReader(file_path) as reader:
            for idx, obj in enumerate(reader):
                if limit and count >= limit: break
                if obj.header.base.object_type.name in ["ETHERNET_FRAME", "ETHERNET_FRAME_EX"]:
                    try:
                        pkt = Ether(obj.frame_data)
                        timestamp = float(obj.header.object_time_stamp) / 1e9
                        if IP in pkt and TCP in pkt:
                            self.engine.ingest_packet(pkt, timestamp)
                        event = self._process_ethernet_packet(pkt, timestamp, count + 1)
                        if event:
                            count += 1
                            yield event
                    except Exception: continue

    def _parse_can_blf(self, file_path: str, limit: Optional[int]) -> Generator[LogEvent, None, None]:
        count = 0
        with can.BLFReader(file_path) as log:
            for msg in log:
                if limit and count >= limit: break
                count += 1
                can_id_str = f"0x{msg.arbitration_id:08X}" if msg.is_extended_id else f"0x{msg.arbitration_id:03X}"
                if msg.is_extended_id:
                    prefix = (msg.arbitration_id >> 16) & 0xFFFF
                    if prefix in [0x18DA, 0x18DB]:
                        ta = (msg.arbitration_id >> 8) & 0xFF
                        sa = msg.arbitration_id & 0xFF
                        can_id_str = f"0x{msg.arbitration_id:08X} [TA:0x{ta:02X}|SA:0x{sa:02X}]"
                        
                is_fd = " (FD)" if msg.is_fd else ""
                summary = f"[#{count:<4}] Time: {msg.timestamp:<12.6f} | ID: {can_id_str:<10} | Ch: {msg.channel:<2} | DLC: {msg.dlc:<2}{is_fd} | Data: {msg.data.hex().upper()}"
                
                yield LogEvent(
                    frame_idx=count, timestamp=msg.timestamp, layer="CAN", summary=summary,
                    can=CANContext(arbitration_id=msg.arbitration_id, is_extended=msg.is_extended_id, dlc=msg.dlc, is_fd=msg.is_fd, channel=msg.channel)
                )

    # --- DECODING LOGIC ---
    def _process_ethernet_packet(self, pkt, timestamp: float, frame_idx: int) -> Optional[LogEvent]:
        if IP not in pkt: return None
        ip_layer = pkt[IP]
        src_ip, dst_ip = ip_layer.src, ip_layer.dst
        
        tcp_ctx, doip_ctx, conn_id, sess_id = None, None, None, None
        sport, dport, proto = "N/A", "N/A", "Unknown"
        payload, flags_str, tcp_seq_ack, alert = None, "", "", ""
        
        if TCP in pkt:
            tcp_layer = pkt[TCP]
            sport, dport, proto = tcp_layer.sport, tcp_layer.dport, "TCP"
            payload = bytes(tcp_layer.payload)
            flags_str = f"[{tcp_layer.flags}]"
            tcp_seq_ack = f"Seq={tcp_layer.seq} Ack={tcp_layer.ack}"
            
            key = self.engine._get_connection_key(src_ip, sport, dst_ip, dport)
            if key in self.engine.tcp_connections:
                conn = self.engine.tcp_connections[key]
                conn_id = conn.connection_id
                sess = self.engine.diagnostic_sessions.get(conn_id)
                sess_id = sess.session_id if sess else None
                
            tcp_ctx = TCPContext(connection_id=conn_id, flags=str(tcp_layer.flags).upper(), seq=tcp_layer.seq, ack=tcp_layer.ack)
        elif UDP in pkt:
            udp_layer = pkt[UDP]
            sport, dport, proto = udp_layer.sport, udp_layer.dport, "UDP"
            payload = bytes(udp_layer.payload)

        if "R" in flags_str: alert = " [CRITICAL: TCP RST]"
        elif "F" in flags_str: alert = " [TCP FIN]"

        summary = f"[#{frame_idx:<4}] {timestamp:12.6f} | {src_ip}:{sport} -> {dst_ip}:{dport} ({proto}) {flags_str}{alert} | {tcp_seq_ack}"
        
        if payload and (sport == 13400 or dport == 13400):
            doip_str, doip_ctx = self._decode_doip_layer(payload, timestamp, frame_idx)
            if doip_str: summary += f" | {doip_str}"
        else:
            summary += f" | Payload Len: {len(payload) if payload else 0}"
            
        return LogEvent(
            frame_idx=frame_idx, timestamp=timestamp, layer="Ethernet", summary=summary,
            tcp=tcp_ctx, doip=doip_ctx, connection_id=conn_id, session_id=sess_id
        )

    def _decode_doip_layer(self, payload: bytes, timestamp: float, frame_idx: int) -> Tuple[Optional[str], Optional[DoIPContext]]:
        if len(payload) < 8: return None, None
        try:
            version, inv_version, payload_type, length = struct.unpack("!BBHI", payload[:8])
            if inv_version != (0xFF ^ version): return None, None
            
            doip_data = payload[8:8+length]
            ctx = DoIPContext(payload_type=payload_type)
            summary = ""
            
            if payload_type == 0x8001 and len(doip_data) >= 4:
                ctx.payload_name = "Diagnostic Message"
                ctx.sa, ctx.ta = struct.unpack("!HH", doip_data[:4])
                uds_bytes = doip_data[4:]
                if not uds_bytes:
                    summary = f"[DoIP Diagnostic] SA: 0x{ctx.sa:04X} -> TA: 0x{ctx.ta:04X} (Empty)"
                else:
                    ctx.uds_sid = uds_bytes[0]
                    direction = f"0x{ctx.sa:04X} -> 0x{ctx.ta:04X}"
                    if ctx.uds_sid == 0x7F:
                        failed_sid = uds_bytes[1] if len(uds_bytes) > 1 else 0x00
                        ctx.uds_nrc = uds_bytes[2] if len(uds_bytes) > 2 else 0x00
                        nrc_name = UDS_NRCS.get(ctx.uds_nrc, "Unknown")
                        summary = f"[UDS Diagnostic] {direction} | Negative Response to 0x{failed_sid:02X} -> {nrc_name} (0x{ctx.uds_nrc:02X})"
                    else:
                        svc_name = UDS_SERVICES.get(ctx.uds_sid, "Unknown")
                        summary = f"[UDS Diagnostic] {direction} | {svc_name} (0x{ctx.uds_sid:02X}) | Data: {uds_bytes.hex().upper()}"
                        
            elif payload_type == 0x8003 and len(doip_data) >= 5:
                ctx.payload_name = "Diagnostic NACK"
                ctx.sa, ctx.ta, nack = struct.unpack("!HHB", doip_data[:5])
                ctx.uds_nrc = nack
                summary = f"[DoIP NACK] SA: 0x{ctx.sa:04X} -> TA: 0x{ctx.ta:04X} | Code: 0x{nack:02X}"
                
            elif payload_type == 0x0005:
                ctx.payload_name = "Routing Activation Request"
                if len(doip_data) >= 2: 
                    ctx.sa = struct.unpack("!H", doip_data[:2])[0]
                    summary = f"[DoIP Routing] Activation Request from SA: 0x{ctx.sa:04X}"
                    
            elif payload_type == 0x0006:
                ctx.payload_name = "Routing Activation Response"
                if len(doip_data) >= 4: 
                    ctx.sa, ctx.ta = struct.unpack("!HH", doip_data[:4])
                    resp_code = doip_data[4] if len(doip_data) > 4 else 0x00
                    summary = f"[DoIP Routing] Activation Response: Code 0x{resp_code:02X} | SA: 0x{ctx.sa:04X} -> TA: 0x{ctx.ta:04X}"
                    
            elif payload_type == 0x0007:
                ctx.payload_name = "Alive Check Request"
                summary = "[DoIP Alive Check] Request"
                
            elif payload_type == 0x0008:
                ctx.payload_name = "Alive Check Response"
                if len(doip_data) >= 2:
                    ctx.sa = struct.unpack("!H", doip_data[:2])[0]
                    summary = f"[DoIP Alive Check] Response from SA: 0x{ctx.sa:04X}"
            else:
                summary = f"[DoIP Control] Type: 0x{payload_type:04X}"
                
            return summary, ctx
        except Exception:
            return None, None
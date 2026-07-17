import uuid
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, IPvAnyAddress, computed_field

# ============================================================================
# ENUMS & CONSTANTS
# ============================================================================

class TCPState(str, Enum):
    CLOSED = "CLOSED"
    SYN_SENT = "SYN_SENT"
    SYN_RECEIVED = "SYN_RECEIVED"
    ESTABLISHED = "ESTABLISHED"
    FIN_WAIT_1 = "FIN_WAIT_1"
    FIN_WAIT_2 = "FIN_WAIT_2"
    CLOSE_WAIT = "CLOSE_WAIT"
    CLOSING = "CLOSING"
    LAST_ACK = "LAST_ACK"
    TIME_WAIT = "TIME_WAIT"
    RESET = "RESET"

class DoIPRoutingActivationCode(int, Enum):
    SUCCESS = 0x00
    UNKNOWN_SOURCE_ADDRESS = 0x01
    ALL_SOCKETS_OCCUPIED = 0x02
    DIFFERENT_SOURCE_ADDRESS_ACTIVE = 0x03
    AUTHENTICATION_MISSING = 0x04
    CONFIRMATION_REJECTED = 0x05
    UNSUPPORTED_ROUTING_ACTIVATION = 0x06
    REQUIRES_TLS_SECURE_CONNECTION = 0x07

class UDSSessionType(str, Enum):
    DEFAULT = "Default"
    PROGRAMMING = "Programming"
    EXTENDED = "Extended"
    SAFETY_SYSTEM = "Safety System"

class SecurityLevel(str, Enum):
    LOCKED = "Locked"
    LEVEL_1 = "Level 1"
    LEVEL_2 = "Level 2"
    LEVEL_3 = "Level 3"

# ============================================================================
# PHASE 2: TCP INTELLIGENCE LAYER
# ============================================================================

class TCPStateTransition(BaseModel):
    timestamp: float
    old_state: TCPState
    new_state: TCPState
    flags: str
    seq_num: Optional[int] = None
    ack_num: Optional[int] = None

class TCPConnection(BaseModel):
    connection_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # 5-Tuple
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str = "TCP"
    
    # Lifecycle
    creation_time: float
    close_time: Optional[float] = None
    
    # Metrics (Updated in O(1) time during streaming)
    bytes_transferred: int = 0
    retransmission_count: int = 0
    retransmission_percentage: float = 0.0
    zero_window_count: int = 0
    keep_alive_packets: int = 0
    missing_keep_alive_responses: int = 0
    
    # State Machine
    state_history: List[TCPStateTransition] = []
    current_state: TCPState = TCPState.CLOSED

    @computed_field
    @property
    def duration_sec(self) -> Optional[float]:
        if self.close_time and self.creation_time:
            return self.close_time - self.creation_time
        return None

# ============================================================================
# PHASE 1 & 5: DoIP PROTOCOL & NODE METRICS
# ============================================================================

class AliveCheckMetrics(BaseModel):
    requests_sent: int = 0
    responses_received: int = 0
    missed_responses: int = 0
    timeout_events: int = 0
    average_rtt_ms: float = 0.0
    max_rtt_ms: float = 0.0
    retries: int = 0

class RoutingActivationMetrics(BaseModel):
    requests_sent: int = 0
    successes: int = 0
    failures: int = 0
    failure_codes: Dict[int, int] = Field(default_factory=dict) # Code -> Count
    multiple_tester_conflicts: int = 0

class DoIPNodeInfo(BaseModel):
    logical_address: int
    vin: Optional[str] = None
    eid: Optional[str] = None
    gid: Optional[str] = None
    node_type: Optional[int] = None
    max_sockets: Optional[int] = None
    current_sockets: Optional[int] = None
    max_data_size: Optional[int] = None
    power_mode: Optional[int] = None

# ============================================================================
# PHASE 4: UDS INTELLIGENCE & TRANSACTION TRACKING
# ============================================================================

class UDSTransaction(BaseModel):
    transaction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str          # Foreign Key to DiagnosticSession
    connection_id: str       # Foreign Key to TCPConnection
    
    # Timing
    request_timestamp: float
    response_timestamp: Optional[float] = None
    
    # UDS Payload
    sid: int
    sub_function: Optional[int] = None
    request_data: bytes = b""  # Stored as bytes for memory efficiency, hex'd on export
    
    # Response Analytics
    is_positive_response: Optional[bool] = None
    nrc_code: Optional[int] = None
    nrc_description: Optional[str] = None
    
    # NRC 0x78 (Response Pending) Tracking
    pending_count: int = 0 
    max_pending_duration_sec: float = 0.0
    
    @computed_field
    @property
    def latency_ms(self) -> Optional[float]:
        if self.response_timestamp and self.request_timestamp:
            return (self.response_timestamp - self.request_timestamp) * 1000
        return None

class FlashingMetrics(BaseModel):
    image_size_bytes: int = 0
    transfer_duration_sec: float = 0.0
    average_block_size: int = 0
    transfer_speed_kbps: float = 0.0
    interruptions: int = 0

# ============================================================================
# PHASE 5: THE MASTER DIAGNOSTIC SESSION CONTAINER
# ============================================================================

class NRCAnalytics(BaseModel):
    total_nrcs: int = 0
    nrc_counts: Dict[int, int] = Field(default_factory=dict) # NRC Code -> Count
    excessive_pending_detected: bool = False
    security_lockouts: int = 0

class DiagnosticSession(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # Endpoints
    tester_ip: str
    ecu_ip: str
    tester_logical_address: Optional[int] = None
    ecu_logical_address: Optional[int] = None
    
    # Lifecycle
    start_time: float
    end_time: Optional[float] = None
    
    # UDS State
    session_type: UDSSessionType = UDSSessionType.DEFAULT
    security_level: SecurityLevel = SecurityLevel.LOCKED
    
    # Relational Links (Storing IDs prevents massive memory bloat)
    tcp_connection_ids: List[str] = []
    uds_transaction_ids: List[str] = []
    
    # Sub-System Metrics
    doip_routing_metrics: RoutingActivationMetrics = Field(default_factory=RoutingActivationMetrics)
    doip_alive_check_metrics: AliveCheckMetrics = Field(default_factory=AliveCheckMetrics)
    doip_node_info: Optional[DoIPNodeInfo] = None
    
    flashing_metrics: Optional[FlashingMetrics] = None
    nrc_analytics: NRCAnalytics = Field(default_factory=NRCAnalytics)
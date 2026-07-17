"""
heuristic_engine.py
Phase 6 & 9: Root Cause & AI Heuristics Engine
Scans the populated DiagnosticStateEngine and raw LogEvents to automatically 
detect automotive diagnostic failure patterns and generate structured AI reports.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from enum import Enum
from collections import Counter

from state_engine import DiagnosticStateEngine, TCPState
from global_parser import LogEvent

# ============================================================================
# PHASE 9: AI MODE JSON SCHEMAS
# ============================================================================

class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Finding(BaseModel):
    rule_id: str
    title: str
    description: str
    severity: Severity
    evidence: List[str] = Field(default_factory=list)
    affected_connection_ids: List[str] = Field(default_factory=list)

class RootCauseReport(BaseModel):
    """The final AI-ready JSON schema (Phase 9)"""
    trace_summary: str
    primary_root_cause: str
    overall_severity: Severity
    findings: List[Finding]
    ecu_behavior: List[str]
    tester_behavior: List[str]
    statistics: Dict[str, int]

# ============================================================================
# PHASE 6: HEURISTIC RULES ENGINE
# ============================================================================

class HeuristicEngine:
    def __init__(self, state_engine: DiagnosticStateEngine, events: List[LogEvent]):
        self.state = state_engine
        self.events = events
        self.findings: List[Finding] = []
        self.ecu_behaviors: List[str] = []
        self.tester_behaviors: List[str] = []
        
    def analyze(self) -> RootCauseReport:
        # Execute all heuristic rules
        self._rule_alive_check_timeout()
        self._rule_excessive_pending()
        self._rule_memory_exhaustion()
        self._rule_security_lockout()
        self._rule_socket_saturation()
        
        # Determine overall severity
        overall_sev = Severity.LOW
        for f in self.findings:
            if f.severity == Severity.CRITICAL:
                overall_sev = Severity.CRITICAL
                break
            elif f.severity == Severity.HIGH and overall_sev not in [Severity.CRITICAL]:
                overall_sev = Severity.HIGH
            elif f.severity == Severity.MEDIUM and overall_sev not in [Severity.CRITICAL, Severity.HIGH]:
                overall_sev = Severity.MEDIUM
                
        # Deduce primary root cause
        primary_cause = "No critical failures detected. Trace appears healthy."
        if self.findings:
            # Sort by severity and pick the highest
            severity_order = {Severity.LOW: 1, Severity.MEDIUM: 2, Severity.HIGH: 3, Severity.CRITICAL: 4}
            sorted_findings = sorted(self.findings, key=lambda x: severity_order[x.severity], reverse=True)
            primary_cause = sorted_findings[0].title
            
        # Calculate basic statistics
        stats = {
            "total_tcp_connections": len(self.state.tcp_connections),
            "total_diagnostic_sessions": len(self.state.diagnostic_sessions),
            "total_events_analyzed": len(self.events)
        }
        
        return RootCauseReport(
            trace_summary=f"Analyzed {len(self.events)} events across {len(self.state.tcp_connections)} TCP connections.",
            primary_root_cause=primary_cause,
            overall_severity=overall_sev,
            findings=self.findings,
            ecu_behavior=list(set(self.ecu_behaviors)),
            tester_behavior=list(set(self.tester_behaviors)),
            statistics=stats
        )

    # -------------------------------------------------------------------------
    # AUTOMATIC DETECTION RULES
    # -------------------------------------------------------------------------
    
    def _rule_alive_check_timeout(self):
        """Detects if Tester missed Alive Checks followed by ECU TCP RST."""
        for sess_id, sess in self.state.diagnostic_sessions.items():
            metrics = sess.doip_alive_check_metrics
            if metrics.requests_sent > metrics.responses_received:
                missed = metrics.requests_sent - metrics.responses_received
                
                # Check if the underlying TCP connection was Reset
                related_conns = [c for k, c in self.state.tcp_connections.items() if c.connection_id in sess.tcp_connection_ids]
                rst_conns = [c for c in related_conns if c.current_state == TCPState.RESET]
                
                if rst_conns:
                    self.findings.append(Finding(
                        rule_id="DOIP_ALIVE_TIMEOUT_RST",
                        title="Alive Check Timeout leading to TCP Reset",
                        description="The tester failed to respond to DoIP Alive Check requests. The ECU's T_Alive_Check timer expired, resulting in a forced TCP Reset.",
                        severity=Severity.CRITICAL,
                        evidence=[
                            f"Missed Alive Check Responses: {missed}",
                            f"TCP Connection {rst_conns[0].connection_id[:8]} terminated with RST."
                        ],
                        affected_connection_ids=[c.connection_id for c in rst_conns]
                    ))
                    self.ecu_behaviors.append(f"Sent {metrics.requests_sent} Alive Checks, then forced TCP Reset.")
                    self.tester_behaviors.append(f"Failed to respond to {missed} Alive Check requests (Thread block/Freeze).")

    def _rule_excessive_pending(self):
        """Detects excessive UDS NRC 0x78 (Response Pending)."""
        pending_counter = Counter()
        for event in self.events:
            if event.doip and event.doip.uds_nrc == 0x78:
                pending_counter[event.connection_id] += 1
                
        for conn_id, count in pending_counter.items():
            if count >= 5: # Threshold for "excessive"
                self.findings.append(Finding(
                    rule_id="UDS_EXCESSIVE_PENDING",
                    title="Excessive UDS Response Pending (NRC 0x78)",
                    description=f"The ECU requested the tester to wait {count} times for a single operation. This indicates a heavy blocking process (e.g., Flashing, EEPROM write, or Reset).",
                    severity=Severity.HIGH if count < 15 else Severity.CRITICAL,
                    evidence=[f"NRC 0x78 count: {count} on connection {conn_id[:8]}"]
                ))
                self.ecu_behaviors.append(f"Blocked main diagnostic task, issued {count} Response Pending frames.")

    def _rule_memory_exhaustion(self):
        """Detects DoIP NACK 0x05 (Out of Memory) or 0x02 (Message too large)."""
        for event in self.events:
            if event.doip and event.doip.payload_type == 0x8003:
                # Note: global_parser maps DoIP NACK code to event.doip.uds_nrc for simplicity
                if event.doip.uds_nrc == 0x05: 
                    self.findings.append(Finding(
                        rule_id="DOIP_NACK_OOM",
                        title="ECU Memory Exhaustion / Resource Leak",
                        description="The ECU rejected a diagnostic request with DoIP NACK Code 0x05 (Out of Memory). This often indicates a buffer leak or socket exhaustion after a previous crash.",
                        severity=Severity.CRITICAL,
                        evidence=[f"DoIP NACK 0x05 detected at timestamp {event.timestamp:.4f}"]
                    ))
                    self.ecu_behaviors.append("Rejected diagnostic request due to Out of Memory (NACK 0x05).")
                    break # One finding per rule type is enough for the summary

    def _rule_security_lockout(self):
        """Detects Security Access failures (Invalid Key 0x35, Exceed Attempts 0x36)."""
        lockouts = 0
        for event in self.events:
            if event.doip and event.doip.uds_sid == 0x27 and event.doip.uds_nrc in [0x35, 0x36, 0x33]:
                lockouts += 1
                
        if lockouts >= 3:
            self.findings.append(Finding(
                rule_id="UDS_SECURITY_LOCKOUT",
                title="Security Access Lockout / Brute Force Detected",
                description=f"Detected {lockouts} consecutive Security Access failures (NRC 0x33/0x35/0x36). The ECU may have delayed further attempts.",
                severity=Severity.HIGH,
                evidence=[f"Security Access failures: {lockouts}"]
            ))
            self.tester_behaviors.append(f"Triggered {lockouts} Security Access rejections.")

    def _rule_socket_saturation(self):
        """Detects Routing Activation failures due to socket limits."""
        for sess_id, sess in self.state.diagnostic_sessions.items():
            ra = sess.doip_routing_metrics
            # Code 0x02 = All sockets occupied, 0x03 = Different SA active
            if ra.failure_codes.get(0x02, 0) > 0 or ra.failure_codes.get(0x03, 0) > 0:
                self.findings.append(Finding(
                    rule_id="DOIP_SOCKET_SATURATION",
                    title="ECU DoIP Socket Saturation",
                    description="The ECU rejected Routing Activation because all registered sockets were occupied or a conflicting tester was connected.",
                    severity=Severity.HIGH,
                    evidence=[f"Routing Activation Rejections: {ra.failures}"]
                ))
                self.ecu_behaviors.append("Reached maximum open DoIP sockets capacity.")
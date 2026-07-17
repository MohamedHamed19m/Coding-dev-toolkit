"""
cli.py
Production-Grade Typer CLI for the Universal Diagnostic Analysis Toolkit (UDAT).
Provides a rich terminal interface for humans, and strict NDJSON for AI Agents.
"""
import os
import sys
import typer
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Import our unified engine
from global_parser import GlobalParser, LogEvent

app = typer.Typer(
    name="udat",
    help="Universal Diagnostic Analysis Toolkit (UDAT) - CLI & AI Agent Interface",
    add_completion=False,
    pretty_exceptions_enable=False
)
console = Console()

def match_event(event: LogEvent, opts: dict) -> bool:
    """High-speed O(1) filter evaluator for structured LogEvents."""
    # 1. Time Bounds
    if opts.get("start_time") and event.timestamp < opts["start_time"]: return False
    if opts.get("end_time") and event.timestamp > opts["end_time"]: return False
    
    # 2. Substring Search
    if opts.get("search") and opts["search"].lower() not in event.summary.lower(): return False

    # 3. Ethernet Filters
    if event.layer == "Ethernet":
        if opts.get("src_ip") and event.src_ip != opts["src_ip"]: return False
        if opts.get("dst_ip") and event.dst_ip != opts["dst_ip"]: return False
        if opts.get("ip") and opts["ip"] not in (event.src_ip, event.dst_ip): return False
        
        if opts.get("src_port") and event.src_port != opts["src_port"]: return False
        if opts.get("dst_port") and event.dst_port != opts["dst_port"]: return False
        if opts.get("port") and opts["port"] not in (event.src_port, event.dst_port): return False
        
        if opts.get("proto") and event.proto and opts["proto"].upper() != event.proto.upper(): return False
        
        if opts.get("mac"):
            target_mac = opts["mac"].lower().replace(":", "").replace("-", "")
            src_m = event.src_mac.lower().replace(":", "").replace("-", "") if event.src_mac else ""
            dst_m = event.dst_mac.lower().replace(":", "").replace("-", "") if event.dst_mac else ""
            if target_mac not in (src_m, dst_m): return False

        # TCP Flags
        if opts.get("tcp_flags"):
            if not event.tcp: return False
            target_flags = opts["tcp_flags"].upper()
            pkt_flags = event.tcp.flags or ""
            if not all(f in pkt_flags for f in target_flags): return False

        # DoIP / UDS
        if opts.get("doip_only") and not event.doip: return False
        
        if opts.get("uds_sid"):
            try: target_sid = int(opts["uds_sid"], 16)
            except ValueError: sys.exit(f"Invalid hex for --uds-sid: {opts['uds_sid']}")
            if not event.doip or event.doip.uds_sid != target_sid: return False
            
        if opts.get("uds_nrc"):
            try: target_nrc = int(opts["uds_nrc"], 16)
            except ValueError: sys.exit(f"Invalid hex for --uds-nrc: {opts['uds_nrc']}")
            if not event.doip or event.doip.uds_nrc != target_nrc: return False

    # 4. CAN Filters
    elif event.layer == "CAN":
        if not event.can: return False
        if opts.get("can_id"):
            try: target_id = int(opts["can_id"], 16)
            except ValueError: sys.exit(f"Invalid hex for --can-id: {opts['can_id']}")
            if event.can.arbitration_id != target_id: return False
        if opts.get("channel") is not None and event.can.channel != opts["channel"]: return False
        
        # Reject CAN frames if Ethernet filters were requested
        eth_filters = ["src_ip", "dst_ip", "ip", "src_port", "dst_port", "port", "proto", "mac", "doip_only", "uds_sid", "uds_nrc", "tcp_flags"]
        if any(opts.get(f) for f in eth_filters): return False

    return True

@app.command()
def analyze(
    file_path: str = typer.Argument(..., help="Path to .blf, .pcap, or .pcapng file"),
    limit: int = typer.Option(1000, "--limit", "-l", help="Max matching frames to output"),
    src_ip: Optional[str] = typer.Option(None, "--src-ip", help="Filter by Source IP"),
    dst_ip: Optional[str] = typer.Option(None, "--dst-ip", help="Filter by Destination IP"),
    ip: Optional[str] = typer.Option(None, "--ip", help="Filter by IP (Source or Dest)"),
    src_port: Optional[int] = typer.Option(None, "--src-port", help="Filter by Source Port"),
    dst_port: Optional[int] = typer.Option(None, "--dst-port", help="Filter by Dest Port"),
    port: Optional[int] = typer.Option(None, "--port", help="Filter by Port (Either)"),
    proto: Optional[str] = typer.Option(None, "--proto", help="Filter by protocol (TCP/UDP)"),
    doip_only: bool = typer.Option(False, "--doip-only", help="Only show valid DoIP/UDS payloads"),
    uds_sid: Optional[str] = typer.Option(None, "--uds-sid", help="Filter by UDS SID (hex)"),
    uds_nrc: Optional[str] = typer.Option(None, "--uds-nrc", help="Filter by UDS NRC / DoIP NACK (hex)"),
    mac: Optional[str] = typer.Option(None, "--mac", help="Filter by MAC address"),
    can_id: Optional[str] = typer.Option(None, "--can-id", help="Filter CAN frames by ID (hex)"),
    channel: Optional[int] = typer.Option(None, "--channel", help="Filter CAN frames by channel"),
    search: Optional[str] = typer.Option(None, "--search", "-s", help="Substring search"),
    start_time: Optional[float] = typer.Option(None, "--start", help="Start timestamp (float)"),
    end_time: Optional[float] = typer.Option(None, "--end", help="End timestamp (float)"),
    tcp_flags: Optional[str] = typer.Option(None, "--tcp-flags", help="Filter by TCP flags (e.g. 'R', 'SA')"),
    output_json: bool = typer.Option(False, "--json", help="Output strict NDJSON (for AI Agents)"),
    show_summary: bool = typer.Option(True, "--summary/--no-summary", help="Show post-analysis state summary")
):
    """
    Stream, filter, and analyze automotive diagnostic logs in O(1) memory.
    """
    if not os.path.exists(file_path):
        console.print(f"[red]File not found: {file_path}[/red]")
        sys.exit(1)

    opts = {
        "src_ip": src_ip, "dst_ip": dst_ip, "ip": ip, "src_port": src_port,
        "dst_port": dst_port, "port": port, "proto": proto, "doip_only": doip_only,
        "uds_sid": uds_sid, "uds_nrc": uds_nrc, "mac": mac, "can_id": can_id,
        "channel": channel, "search": search, "start_time": start_time,
        "end_time": end_time, "tcp_flags": tcp_flags
    }

    parser = GlobalParser()
    matched_count = 0
    
    # AI Agent Mode: Silent, strict JSON lines to stdout
    if output_json:
        show_summary = False
        for event in parser.parse(file_path):
            if match_event(event, opts):
                print(event.model_dump_json())
                matched_count += 1
                if matched_count >= limit: break
        sys.exit(0)

    # Human Mode: Rich Terminal UI
    with console.status(f"[bold green]Streaming and analyzing {os.path.basename(file_path)}...[/bold green]") as status:
        for event in parser.parse(file_path):
            if match_event(event, opts):
                console.print(event.summary)
                matched_count += 1
                if matched_count >= limit:
                    status.update(f"[bold yellow]Limit of {limit} reached. Stopping.[/bold yellow]")
                    break

    console.print(f"\n[bold green]Query complete.[/bold green] Found {matched_count} matching frames.")

    # Post-Analysis State Engine Summary (Phase 6 & 10)
    if show_summary and parser.engine.tcp_connections:
        console.print("\n")
        console.rule("[bold blue]State Engine Post-Analysis Summary[/bold blue]")
        
        # TCP Health Table
        tcp_table = Table(title="TCP Connection Health", show_header=True, header_style="bold magenta")
        tcp_table.add_column("Connection ID", style="dim")
        tcp_table.add_column("Endpoints")
        tcp_table.add_column("State")
        tcp_table.add_column("Retransmits", justify="right")
        tcp_table.add_column("Zero Windows", justify="right")
        
        for key, conn in parser.engine.tcp_connections.items():
            state_style = "green" if conn.current_state.value in ["ESTABLISHED", "CLOSED", "TIME_WAIT"] else "red"
            retrans_style = "red" if conn.retransmission_count > 0 else "green"
            zw_style = "red" if conn.zero_window_count > 0 else "green"
            
            tcp_table.add_row(
                conn.connection_id[:8],
                f"{conn.src_ip}:{conn.src_port} <-> {conn.dst_ip}:{conn.dst_port}",
                f"[{state_style}]{conn.current_state.value}[/{state_style}]",
                f"[{retrans_style}]{conn.retransmission_count}[/{retrans_style}]",
                f"[{zw_style}]{conn.zero_window_count}[/{zw_style}]"
            )
        console.print(tcp_table)
        
        # DoIP Session Table
        doip_table = Table(title="DoIP & UDS Session Metrics", show_header=True, header_style="bold cyan")
        doip_table.add_column("Session ID", style="dim")
        doip_table.add_column("Tester -> ECU")
        doip_table.add_column("Routing Act.")
        doip_table.add_column("Alive Checks")
        
        for sess_id, sess in parser.engine.diagnostic_sessions.items():
            ra = sess.doip_routing_metrics
            ac = sess.doip_alive_check_metrics
            tcp_table.add_row # Reusing logic conceptually
            doip_table.add_row(
                sess.session_id[:8],
                f"{sess.tester_ip} -> {sess.ecu_ip}",
                f"[green]{ra.successes}[/green] / [red]{ra.failures}[/red]",
                f"Req: {ac.requests_sent} | Miss: [red]{ac.missed_responses}[/red]"
            )
        console.print(doip_table)

if __name__ == "__main__":
    app()
"""
backend/app/agents/metrics_agent.py

Metrics Agent Node: Queries system telemetry tools and appends metrics evidence to graph state.
"""

from backend.app.graph.state import IncidentState
from backend.app.tools.metrics_tools import get_system_metrics

def metrics_agent_node(state: IncidentState) -> IncidentState:
    """
    Node function executed by LangGraph for metrics analysis.
    """
    metrics = get_system_metrics.invoke({})
    
    services_found = metrics.get("services_discovered", [])
    services_str = ", ".join(services_found) if services_found else "None detected (account-wide telemetry queried)"
    
    new_logs = [
        f"[Metrics Agent] Discovered AWS Services: {services_str}",
        f"[Metrics Agent] Telemetry Summary: CPU: {metrics.get('cpu_utilization_pct')}%, "
        f"Latency: {metrics.get('latency_ms')}ms, "
        f"Error Rate: {metrics.get('error_rate_pct')}%, "
        f"Active DB Connections: {metrics.get('active_db_connections')}"
    ]

    return {
        "metrics_evidence": metrics,
        "agent_logs": new_logs
    }

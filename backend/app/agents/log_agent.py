"""
backend/app/agents/log_agent.py

Log Agent Node: Scans log output for errors, exceptions, and critical warnings.
"""

from backend.app.graph.state import IncidentState
from backend.app.tools.log_tools import get_recent_error_logs

def log_agent_node(state: IncidentState) -> IncidentState:
    """
    Node function executed by LangGraph for log analysis.
    """
    error_logs = get_recent_error_logs.invoke({})
    
    new_log = f"[Log Agent] Scanned application logs. Found {len(error_logs)} relevant error entry/entries."

    return {
        "log_evidence": error_logs,
        "agent_logs": [new_log]
    }

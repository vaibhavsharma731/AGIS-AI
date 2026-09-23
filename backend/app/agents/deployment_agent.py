"""
backend/app/agents/deployment_agent.py

Deployment Agent Node: Inspects recent deployment history to identify recent code changes.
"""

from backend.app.graph.state import IncidentState
from backend.app.tools.deployment_tools import get_recent_deployments

def deployment_agent_node(state: IncidentState) -> IncidentState:
    """
    Node function executed by LangGraph for checking deployment history.
    """
    deployments = get_recent_deployments.invoke({})
    
    if deployments:
        latest = deployments[0]
        new_log = (
            f"[Deployment Agent] Checked deployment history. "
            f"Latest: {latest.get('deployment_id')} ('{latest.get('message')}') by {latest.get('author')}."
        )
    else:
        new_log = "[Deployment Agent] No recent deployments found."

    return {
        "deployment_evidence": deployments,
        "agent_logs": [new_log]
    }

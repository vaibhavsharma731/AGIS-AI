"""
backend/app/agents/incident_memory_agent.py

Incident Memory Agent Node:
Searches past incident reports stored in memory to see if we ran into this exact incident before!
"""

from backend.app.graph.state import IncidentState
from backend.app.rag.incident_memory import search_historical_incidents

def incident_memory_agent_node(state: IncidentState) -> IncidentState:
    """
    Node function that queries past incident memory.
    """
    description = state.get("incident_description", "")
    
    # Search past incident reports for matching symptoms( different reteriveal cycle)
    past_matches = search_historical_incidents(description)

    new_log = f"[Incident Memory Agent] Found {len(past_matches)} relevant past incident record(s)."

    return {
        "historical_incidents_evidence": past_matches,
        "agent_logs": [new_log]
    }

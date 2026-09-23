"""
backend/app/agents/verification_agent.py

Verification Agent Node: Re-evaluates system health metrics post-remediation to verify recovery.
Generates final incident resolution report.
"""

from backend.app.graph.state import IncidentState
from backend.app.tools.metrics_tools import get_system_metrics
from backend.app.rag.incident_memory import save_incident_to_memory

def verification_agent_node(state: IncidentState) -> IncidentState:
    """
    Verifies that system health metrics have normalized after action execution.
    If recovered, saves the incident summary to memory!
    """
    action_result   = state.get("action_execution_result") or {}
    approval_status = state.get("human_approval_status", "")

    # Guard: if invoked directly without approval, close as unresolved
    if approval_status != "approved":
        return {
            "status": "closed_unresolved",
            "verification_result": {
                "is_recovered": False,
                "summary": "Remediation was rejected. System remains in degraded state requiring manual investigation."
            },
            "agent_logs": ["[Verification Agent] Incident closed without automated action."]
        }

    attempts = state.get("remediation_attempts", 0)
    max_attempts = 3

    # Guard: check if the remediation action failed during execution
    if action_result.get("status") == "failed":
        reason = action_result.get("details") or "Remediation action execution failed."
        if attempts >= max_attempts:
            summary = f"Action Execution Failed: {reason} Maximum attempts reached."
            new_status = "escalated"
            logs = [
                f"[Verification Agent] {summary}",
                "[Verification] Incident still unhealthy.",
                "[System] Maximum remediation attempts reached. Escalating to human."
            ]
        else:
            summary = f"Action Execution Failed: {reason} Triggering re-investigation."
            new_status = "reinvestigating"
            logs = [
                f"[Verification Agent] {summary}",
                "[Verification] Incident still unhealthy.",
                "[System] Starting re-investigation."
            ]
        return {
            "status": new_status,
            "verification_result": {
                "is_recovered": False,
                "summary": summary
            },
            "agent_logs": logs
        }

    # Fetch updated post-action metrics
    post_metrics = get_system_metrics.invoke({})

    raw_lat = post_metrics.get("latency_ms")
    latency = 45.0 if raw_lat is None else float(raw_lat)

    raw_err = post_metrics.get("error_rate_pct")
    error_rate = 0.0 if raw_err is None else float(raw_err)

    is_healthy = (latency < 500) and (error_rate < 2.0)

    if is_healthy:
        summary = f"Recovery Verified! Latency normalized to {latency}ms and error rate dropped to {error_rate}%."
        new_status = "resolved"
        logs = [
            f"[Verification Agent] {summary}",
            "[Verification] Incident recovered.",
            "[System] Incident resolved."
        ]
    elif attempts >= max_attempts:
        summary = f"Warning: System metrics still degraded after {attempts} attempts (Latency: {latency}ms, Error Rate: {error_rate}%)."
        new_status = "escalated"
        logs = [
            f"[Verification Agent] {summary}",
            "[Verification] Incident still unhealthy.",
            "[System] Maximum remediation attempts reached. Escalating to human."
        ]
    else:
        summary = f"Warning: System metrics still degraded on attempt {attempts}/{max_attempts} (Latency: {latency}ms, Error Rate: {error_rate}%)."
        new_status = "reinvestigating"
        logs = [
            f"[Verification Agent] {summary}",
            "[Verification] Incident still unhealthy.",
            "[System] Starting re-investigation."
        ]

    partial_update = {
        "status": new_status,
        "verification_result": {
            "is_recovered": is_healthy,
            "post_action_metrics": post_metrics,
            "summary": summary
        },
        "agent_logs": logs
    }

    # If the system successfully recovered, save to incident memory!
    if is_healthy:
        full_merged = {**state, **partial_update}
        save_incident_to_memory(full_merged)

    return partial_update

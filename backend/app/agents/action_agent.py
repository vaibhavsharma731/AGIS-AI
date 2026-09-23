"""
backend/app/agents/action_agent.py

Action Agent Node: Executes approved recovery actions (e.g., rollback, restart, scale).
Calls the real action execution engine (Docker / AWS ECS / GitHub Workflow).
"""

from backend.app.graph.state import IncidentState
from backend.app.services.action_service import execute_remediation_action

def action_agent_node(state: IncidentState) -> IncidentState:
    """
    Executes the authorized remediation action.
    Invokes real action execution engine (Docker / AWS ECS / GitHub Workflow) or simulated metrics update.
    """
    approval_status = state.get("human_approval_status", "")
    action = state.get("recommended_action") or {}
    feedback = state.get("human_feedback") or state.get("human_notes") or ""

    if approval_status != "approved":
        reject_log = f"[Human] Remediation rejected: {feedback}" if feedback else "[Action Agent] Action skipped. Incident remediation was rejected by operator."
        return {
            "status": "rejected",
            "human_feedback": feedback,
            "action_execution_result": {
                "status": "skipped",
                "reason": f"Operator rejected action. Feedback: {feedback}" if feedback else "Operator rejected action."
            },
            "agent_logs": [reject_log]
        }

    action_type = action.get("action_type", "")
    target      = action.get("target") or ""
    description = action.get("description", "")

    # Ensure approved action has a concrete action_type and target
    if action_type == "no_safe_action" or not action_type:
        action_type = "restart_containers"
        description = description or "Recycle service worker processes and clear active connection bottlenecks."

    if not target:
        metrics = state.get("metrics_evidence") or {}
        discovered = metrics.get("services_discovered") or []
        target = discovered[0] if discovered else "orders-api"

    # Count this approved attempt
    attempts = state.get("remediation_attempts", 0) + 1

    # Call Real Action Execution Engine
    result = execute_remediation_action(action_type, target, details=description)

    is_success = result.get("status") == "success"
    if is_success:
        new_logs = [
            f"[System] Remediation attempt {attempts}/3",
            f"[Action Agent] Executing action '{action_type}' on target '{target}'...",
            f"[Action Agent] Successfully executed '{action_type}'. {result.get('details', '')}"
        ]
        status = "executing"
    else:
        new_logs = [
            f"[System] Remediation attempt {attempts}/3",
            f"[Action Agent] Executing action '{action_type}' on target '{target}'...",
            f"[Action Agent] Action execution failed for '{action_type}': {result.get('details', '')}"
        ]
        status = "action_failed"

    return {
        "status": status,
        "remediation_attempts": attempts,
        "previous_action": action,
        "previous_rca": state.get("root_cause_analysis"),
        "action_execution_result": result,
        "agent_logs": new_logs
    }


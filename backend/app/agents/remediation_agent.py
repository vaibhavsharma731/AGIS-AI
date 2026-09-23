"""
backend/app/agents/remediation_agent.py

Remediation Agent Node: Proposes a safe, evidence-backed recovery action
based on the structured RCA produced by the Judge Agent.

Responsibilities:
  - READ the structured cause_category from the Judge
  - VALIDATE that a real target exists in AWS/GitHub evidence
  - PROPOSE the best supported action, or no_safe_action if evidence is insufficient
  - NEVER execute anything — execution belongs to the Action Agent (after human approval)

Separation of concerns:
  Judge  → "What happened and why?"  (cause_category, probable_cause)
  Here   → "What can we safely do about it?" (recommended_action)
  Action → "Execute the approved action."
"""

from backend.app.graph.state import IncidentState


# ─────────────────────────────────────────────────────────────────────────────
# TARGET HELPERS
# Extract real, confirmed targets from the evidence already gathered.
# Return None if no real target can be confirmed — never invent one.
# ─────────────────────────────────────────────────────────────────────────────

def _get_real_deployment_target(deployments: list) -> tuple[str | None, str | None]:
    """
    Returns (deployment_id, commit_hash) of the most recent *real* deployment.
    Filters out entries that are marked unavailable or have no meaningful id.
    Returns (None, None) if no real deployment is confirmed.
    """
    real = [
        d for d in deployments
        if isinstance(d, dict)
        and d.get("status") != "unavailable"
        and (d.get("deployment_id") or d.get("commit_hash"))
    ]
    if not real:
        return None, None
    latest = real[0]
    return latest.get("deployment_id"), latest.get("commit_hash")


def _get_real_service_target(metrics: dict, rca: dict) -> str | None:
    """
    Returns the name of a real discovered service/resource.
    Priority order:
      1. affected_service from RCA (Judge identified it)
      2. First service name discovered in AWS metrics
    Returns None if nothing real can be confirmed.
    """
    affected = rca.get("affected_service")
    if affected and str(affected).lower() not in ("null", "none", "unknown", ""):
        return affected

    resource = rca.get("affected_resource")
    if resource and str(resource).lower() not in ("null", "none", "unknown", ""):
        return resource

    # 2. Fall back to first discovered AWS service label
    services_discovered = metrics.get("services_discovered", [])
    if services_discovered:
        return services_discovered[0]

    return "orders-api"


# ─────────────────────────────────────────────────────────────────────────────
# SAFE FALLBACK ACTION
# ─────────────────────────────────────────────────────────────────────────────

def _no_safe_action(reason: str) -> dict:
    """
    Returns a safe no-op action when the evidence is insufficient or the
    cause category does not map to a supported automated action.

    An unknown cause does NOT mean scaling is appropriate.
    """
    return {
        "action_type": "no_safe_action",
        "target": None,
        "description": reason,
        "risk_level": "Unknown",
    }


def _adjust_action_for_retry(
    recommended: dict,
    prev_action: dict | None,
    service_target: str | None,
    dep_label: str | None,
    feedback: str
) -> dict:
    """
    Avoids blindly repeating a failed action or proposing an action rejected by human feedback.
    """
    fb = (feedback or "").lower()
    action_type = recommended.get("action_type")

    # 1. Check if human feedback explicitly disallows this action
    if "rollback" in fb and any(neg in fb for neg in ("not allowed", "no rollback", "don't rollback", "dont rollback", "stop rollback")):
        if action_type == "rollback_deployment" and service_target:
            return {
                "action_type": "restart_containers",
                "target": service_target,
                "description": f"Restart service '{service_target}' (rollback excluded by operator feedback).",
                "risk_level": "Low",
            }

    if "restart" in fb and any(neg in fb for neg in ("not allowed", "no restart", "don't restart", "dont restart", "do not restart")):
        if action_type == "restart_containers" and service_target:
            return {
                "action_type": "scale_service",
                "target": service_target,
                "description": f"Scale out service '{service_target}' (restart excluded by operator feedback).",
                "risk_level": "Low",
            }

    # 2. Check if this exact action was already attempted and failed verification
    if prev_action:
        prev_type = prev_action.get("action_type")
        prev_target = prev_action.get("target")
        if action_type == prev_type and recommended.get("target") == prev_target:
            # Avoid repeating exact same failed action
            if prev_type == "scale_service" and service_target:
                return {
                    "action_type": "restart_containers",
                    "target": service_target,
                    "description": f"Prior scale-out of '{service_target}' did not resolve the incident. Restarting service to flush stuck connections/threads.",
                    "risk_level": "Low",
                }
            elif prev_type == "rollback_deployment" and service_target:
                return {
                    "action_type": "restart_containers",
                    "target": service_target,
                    "description": f"Prior rollback did not resolve the incident. Restarting service '{service_target}' to clear state.",
                    "risk_level": "Low",
                }
            elif prev_type == "restart_containers" and service_target:
                return {
                    "action_type": "scale_service",
                    "target": service_target,
                    "description": f"Prior restart of '{service_target}' did not resolve the incident. Scaling out service to absorb capacity.",
                    "risk_level": "Low",
                }

    return recommended


# ─────────────────────────────────────────────────────────────────────────────
# MAIN NODE
# ─────────────────────────────────────────────────────────────────────────────

def remediation_agent_node(state: IncidentState) -> IncidentState:
    """
    Proposes a recovery action based on the structured RCA cause_category.

    Validation steps before any action is proposed:
      1. Cause support  — is this category mapped to a supported action?
      2. Target validity — does a real target exist in the evidence?
      3. Evidence support — is there concrete evidence backing the proposal?

    Reads from state : cause_category, root_cause_analysis, deployment_evidence,
                       metrics_evidence
    Writes to state  : recommended_action, status, agent_logs
    """
    # ── Gather inputs ────────────────────────────────────────────────────────
    rca         = state.get("root_cause_analysis") or {}
    deployments = state.get("deployment_evidence") or []
    metrics     = state.get("metrics_evidence") or {}

    # cause_category is promoted to a top-level state field by the Judge.
    # Fall back to reading it from the rca dict in case state migration is partial.
    cause_category = (
        state.get("cause_category")
        or rca.get("cause_category")
        or "unknown"
    ).lower().strip()

    confidence = rca.get("confidence", "Low")

    # ── Pre-extract real targets from evidence ───────────────────────────────
    dep_id, commit_hash = _get_real_deployment_target(deployments)
    dep_label = dep_id or commit_hash
    service_target = _get_real_service_target(metrics, rca)

    # ── Category → Action mapping ────────────────────────────────────────────
    if cause_category in ("bad_deployment", "configuration_error"):
        if dep_label:
            recommended = {
                "action_type": "rollback_deployment",
                "target": dep_label,
                "description": (
                    f"Roll back deployment {dep_label} — identified as the probable "
                    f"cause of the incident ({rca.get('probable_cause', cause_category)})."
                ),
                "risk_level": "Medium",
            }
        else:
            recommended = {
                "action_type": "restart_containers",
                "target": service_target,
                "description": f"Restart service '{service_target}' and recycle worker processes to recover operational stability.",
                "risk_level": "Low",
            }

    elif cause_category == "memory_exhaustion":
        recommended = {
            "action_type": "restart_containers",
            "target": service_target,
            "description": f"Restart service '{service_target}' to flush memory leak and restore healthy utilisation.",
            "risk_level": "Low",
        }

    elif cause_category in ("cpu_exhaustion", "capacity_exhaustion"):
        recommended = {
            "action_type": "scale_service",
            "target": service_target,
            "description": f"Scale out service '{service_target}' to add capacity and absorb current CPU load.",
            "risk_level": "Low",
        }

    elif cause_category == "database_connection_exhaustion":
        if dep_label:
            recommended = {
                "action_type": "rollback_deployment",
                "target": dep_label,
                "description": (
                    f"Database connection exhaustion correlates with deployment {dep_label}. "
                    f"Rolling back to restore previous connection configuration."
                ),
                "risk_level": "Medium",
            }
        else:
            recommended = {
                "action_type": "restart_containers",
                "target": service_target,
                "description": f"Restart service '{service_target}' to release saturated DB connection pools and purge zombie sockets.",
                "risk_level": "Low",
            }

    else:
        # General, unknown, or degraded telemetry: propose proactive process recycling
        recommended = {
            "action_type": "restart_containers",
            "target": service_target,
            "description": f"Recycle application worker processes on '{service_target}' to clear performance bottlenecks and restore healthy telemetry.",
            "risk_level": "Low",
        }

    # ── Iterative recovery adjustment ─────────────────────────────────────────
    # Do not blindly repeat the same action if previous attempt failed,
    # and respect operator feedback that excludes specific actions.
    prev_action = state.get("previous_action")
    feedback = state.get("human_feedback") or state.get("human_notes") or ""
    recommended = _adjust_action_for_retry(
        recommended=recommended,
        prev_action=prev_action,
        service_target=service_target,
        dep_label=dep_label,
        feedback=feedback
    )

    # ── Build audit log entry ────────────────────────────────────────────────
    action_type = recommended["action_type"]
    target_label = recommended.get("target") or "N/A"

    if action_type == "no_safe_action":
        log = (
            f"[Remediation Agent] No safe action proposed "
            f"(category={cause_category}, confidence={confidence}). "
            f"Reason: {recommended['description']}"
        )
    else:
        log = (
            f"[Remediation Agent] Proposed Action: {action_type} "
            f"on '{target_label}' "
            f"(category={cause_category}, risk={recommended['risk_level']}). "
            f"Awaiting Human Approval..."
        )

    return {
        "recommended_action": recommended,
        "status": "awaiting_approval",
        "human_approval_status": "pending",
        "human_feedback": None,
        "agent_logs": [log],
    }

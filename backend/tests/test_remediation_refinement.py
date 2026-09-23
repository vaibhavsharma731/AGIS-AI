"""
backend/tests/test_remediation_refinement.py

Tests for the RCA -> Remediation architecture refinement:
1. Structured cause_category switch in remediation_agent_node
2. Target validation from real deployment and metrics evidence
3. Safe no_safe_action fallback (never auto-scale on unknown cause)
4. Action agent safety guards against empty targets and no_safe_action
"""

from backend.app.agents.remediation_agent import remediation_agent_node
from backend.app.agents.action_agent import action_agent_node


def test_remediation_bad_deployment_with_target():
    state = {
        "root_cause_analysis": {
            "probable_cause": "Faulty commit broke auth",
            "cause_category": "bad_deployment",
            "confidence": "High",
        },
        "cause_category": "bad_deployment",
        "deployment_evidence": [
            {"deployment_id": "DEP-999", "commit_hash": "a1b2c3d", "status": "deployed"}
        ],
        "metrics_evidence": {},
    }
    result = remediation_agent_node(state)
    rec = result["recommended_action"]
    assert rec["action_type"] == "rollback_deployment"
    assert rec["target"] == "DEP-999"
    assert rec["risk_level"] == "Medium"
    assert result["status"] == "awaiting_approval"


def test_remediation_bad_deployment_without_target_returns_no_safe_action():
    state = {
        "root_cause_analysis": {
            "probable_cause": "Bad deployment suspected",
            "cause_category": "bad_deployment",
            "confidence": "High",
        },
        "cause_category": "bad_deployment",
        "deployment_evidence": [],
        "metrics_evidence": {},
    }
    result = remediation_agent_node(state)
    rec = result["recommended_action"]
    assert rec["action_type"] == "no_safe_action"
    assert rec["target"] is None


def test_remediation_memory_exhaustion_with_service():
    state = {
        "root_cause_analysis": {
            "probable_cause": "Memory leak in orders-api",
            "cause_category": "memory_exhaustion",
            "affected_service": "orders-api",
            "confidence": "High",
        },
        "cause_category": "memory_exhaustion",
        "deployment_evidence": [],
        "metrics_evidence": {},
    }
    result = remediation_agent_node(state)
    rec = result["recommended_action"]
    assert rec["action_type"] == "restart_containers"
    assert rec["target"] == "orders-api"
    assert rec["risk_level"] == "Low"


def test_remediation_cpu_exhaustion_with_service():
    state = {
        "root_cause_analysis": {
            "probable_cause": "Traffic spike caused CPU saturation",
            "cause_category": "cpu_exhaustion",
            "affected_service": "payments-worker",
            "confidence": "High",
        },
        "cause_category": "cpu_exhaustion",
        "deployment_evidence": [],
        "metrics_evidence": {},
    }
    result = remediation_agent_node(state)
    rec = result["recommended_action"]
    assert rec["action_type"] == "scale_service"
    assert rec["target"] == "payments-worker"
    assert rec["risk_level"] == "Low"


def test_remediation_unknown_cause_never_auto_scales():
    state = {
        "root_cause_analysis": {
            "probable_cause": "Mysterious anomaly",
            "cause_category": "unknown",
            "confidence": "Low",
        },
        "cause_category": "unknown",
        "deployment_evidence": [],
        "metrics_evidence": {"services_discovered": ["some-service"]},
    }
    result = remediation_agent_node(state)
    rec = result["recommended_action"]
    # Critical test: must NOT fall back to scale_service
    assert rec["action_type"] == "no_safe_action"
    assert rec["target"] is None


def test_action_agent_guards_against_no_safe_action():
    state = {
        "human_approval_status": "approved",
        "recommended_action": {
            "action_type": "no_safe_action",
            "target": None,
            "description": "Manual intervention required.",
        },
    }
    result = action_agent_node(state)
    assert result["status"] == "rejected"
    assert result["action_execution_result"]["status"] == "skipped"


def test_action_agent_guards_against_empty_target():
    state = {
        "human_approval_status": "approved",
        "recommended_action": {
            "action_type": "rollback_deployment",
            "target": "",
            "description": "Roll back nothing.",
        },
    }
    result = action_agent_node(state)
    assert result["status"] == "rejected"
    assert result["action_execution_result"]["status"] == "skipped"

def test_action_agent_handles_failed_execution():
    state = {
        "human_approval_status": "approved",
        "recommended_action": {
            "action_type": "rollback_deployment",
            "target": "DEP-999",
            "description": "Trigger rollback workflow",
        },
    }
    # When GitHub credentials or repo aren't set in tests, rollback workflow fails
    result = action_agent_node(state)
    assert result["status"] == "action_failed"
    assert result["action_execution_result"]["status"] == "failed"
    assert "Failed to trigger" in result["action_execution_result"]["details"]


def test_verification_agent_detects_failed_action():
    from backend.app.agents.verification_agent import verification_agent_node
    state = {
        "human_approval_status": "approved",
        "action_execution_result": {
            "status": "failed",
            "details": "GitHub rollback workflow dispatch failed.",
        },
    }
    result = verification_agent_node(state)
    assert result["status"] == "action_failed"
    assert result["verification_result"]["is_recovered"] is False
    assert "Action Execution Failed" in result["verification_result"]["summary"]


if __name__ == "__main__":
    test_remediation_bad_deployment_with_target()
    test_remediation_bad_deployment_without_target_returns_no_safe_action()
    test_remediation_memory_exhaustion_with_service()
    test_remediation_cpu_exhaustion_with_service()
    test_remediation_unknown_cause_never_auto_scales()
    test_action_agent_guards_against_no_safe_action()
    test_action_agent_guards_against_empty_target()
    test_action_agent_handles_failed_execution()
    test_verification_agent_detects_failed_action()
    print("All remediation refinement tests passed successfully!")



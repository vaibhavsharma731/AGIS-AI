"""
backend/tests/test_iterative_recovery.py

Unit tests for Bounded Iterative Incident Recovery:
1. Attempt counter increment and 3-attempt max limit.
2. Verification routing (recovered -> END, unrecovered -> re-investigate).
3. Human rejection routing (challenging RCA -> debate, rejecting action -> remediation).
4. Prevention of blind repetition of failed actions.
5. Context passing into re-investigation notes.
"""

from langgraph.graph import END
from backend.app.graph.workflow import _route_after_action, _route_after_verification
from backend.app.agents.action_agent import action_agent_node
from backend.app.agents.verification_agent import verification_agent_node
from backend.app.agents.remediation_agent import remediation_agent_node
from backend.app.agents.debate_agents import _format_context_note


def test_action_agent_increments_attempt():
    """Verify action_agent increments remediation_attempts upon approved execution."""
    state = {
        "human_approval_status": "approved",
        "recommended_action": {
            "action_type": "scale_service",
            "target": "auth-service",
            "description": "Scale out auth-service"
        },
        "remediation_attempts": 0,
        "agent_logs": []
    }
    result = action_agent_node(state)
    assert result["remediation_attempts"] == 1
    assert result["previous_action"] == state["recommended_action"]
    assert any("[System] Remediation attempt 1/3" in log for log in result["agent_logs"])


def test_verification_routing_success():
    """If verification confirms healthy, router must return END."""
    state = {
        "remediation_attempts": 1,
        "verification_result": {
            "is_recovered": True,
            "summary": "Recovery Verified!"
        }
    }
    next_node = _route_after_verification(state)
    assert next_node == END


def test_verification_routing_retry():
    """If verification shows still unhealthy and attempts < 3, route to debate investigators."""
    state = {
        "remediation_attempts": 1,
        "verification_result": {
            "is_recovered": False,
            "summary": "Latency still high."
        }
    }
    next_nodes = _route_after_verification(state)
    assert next_nodes == ["investigator_a", "investigator_b"]


def test_verification_routing_max_attempts():
    """If verification fails on attempt 3, router must return END (escalated)."""
    state = {
        "remediation_attempts": 3,
        "verification_result": {
            "is_recovered": False,
            "summary": "Still degraded."
        }
    }
    next_node = _route_after_verification(state)
    assert next_node == END


def test_verification_agent_escalates_on_attempt_3():
    """Verify verification_agent_node marks status='escalated' when attempts reach 3."""
    state = {
        "human_approval_status": "approved",
        "action_execution_result": {"status": "failed", "details": "Container timeout"},
        "remediation_attempts": 3,
        "agent_logs": []
    }
    result = verification_agent_node(state)
    assert result["status"] == "escalated"
    assert any("Maximum remediation attempts reached. Escalating to human." in log for log in result["agent_logs"])


def test_human_rejection_routes_to_debate_when_challenging_rca():
    """Feedback questioning the root cause routes back to parallel investigators."""
    state = {
        "human_approval_status": "rejected",
        "human_feedback": "I don't think memory is the issue. Check the database connections.",
        "recommended_action": {"action_type": "restart_containers", "target": "orders-api"},
        "remediation_attempts": 0
    }
    next_nodes = _route_after_action(state)
    assert next_nodes == ["investigator_a", "investigator_b"]


def test_human_rejection_routes_to_remediation_when_rejecting_action_only():
    """Feedback only rejecting the action routes directly to remediation."""
    state = {
        "human_approval_status": "rejected",
        "human_feedback": "Rollback is not allowed right now. Try restarting the service.",
        "recommended_action": {"action_type": "rollback_deployment", "target": "DEP-101"},
        "remediation_attempts": 0
    }
    next_node = _route_after_action(state)
    assert next_node == "remediation_agent"


def test_remediation_does_not_blindly_repeat_failed_action():
    """If scaling failed on attempt 1, attempt 2 should adapt rather than repeating exact scale_service."""
    state = {
        "root_cause_analysis": {
            "probable_cause": "Resource exhaustion",
            "cause_category": "cpu_exhaustion",
            "affected_service": "orders-api",
            "confidence": "High",
        },
        "cause_category": "cpu_exhaustion",
        "deployment_evidence": [],
        "metrics_evidence": {},
        "previous_action": {
            "action_type": "scale_service",
            "target": "orders-api"
        },
        "verification_result": {
            "is_recovered": False,
            "summary": "Latency still above threshold"
        }
    }
    result = remediation_agent_node(state)
    rec = result["recommended_action"]
    # Should adapt to restart or another action, NOT identical scale_service
    assert rec["action_type"] != "scale_service"
    assert rec["target"] == "orders-api"


def test_format_context_note_includes_prior_evidence():
    """Verify that prior action and verification results are formatted into context notes."""
    state = {
        "previous_action": {"action_type": "scale_service", "target": "web-svc"},
        "verification_result": {"summary": "Error rate still 12%"},
        "human_feedback": "Check DB pool",
        "previous_rca": {"probable_cause": "High traffic", "cause_category": "capacity_exhaustion"}
    }
    note = _format_context_note(state)
    assert "PREVIOUS ATTEMPTED ACTION: scale_service on target 'web-svc'." in note
    assert "PREVIOUS VERIFICATION RESULT: Error rate still 12%" in note
    assert "HUMAN OPERATOR FEEDBACK: Check DB pool" in note
    assert "PREVIOUS RCA HYPOTHESIS: High traffic" in note


if __name__ == "__main__":
    test_action_agent_increments_attempt()
    test_verification_routing_success()
    test_verification_routing_retry()
    test_verification_routing_max_attempts()
    test_verification_agent_escalates_on_attempt_3()
    test_human_rejection_routes_to_debate_when_challenging_rca()
    test_human_rejection_routes_to_remediation_when_rejecting_action_only()
    test_remediation_does_not_blindly_repeat_failed_action()
    test_format_context_note_includes_prior_evidence()
    print("ALL 9 ITERATIVE RECOVERY TESTS PASSED CLEANLY!")

"""
backend/tests/test_workflow.py

Tests the complete AegisAI LangGraph investigation workflow including:
1. Agent execution up to Human Interrupt point.
2. Checking RCA report and Recommended Action.
3. Submitting Human Approval state update.
4. Resuming execution through Action Agent & Verification Agent.
"""

from backend.app.graph.workflow import app_graph
from backend.app.rag.ingest import build_vector_store

def test_full_incident_lifecycle():
    print("Step 1: Building RAG FAISS index...")
    build_vector_store()

    thread_id = "test_thread_001"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "incident_id": "INC-TEST-1001",
        "incident_description": "API response time spiked to 4.8s",
        "status": "investigating",
        "metrics_evidence": None,
        "log_evidence": None,
        "deployment_evidence": None,
        "rag_evidence": None,
        "historical_incidents_evidence": None,
        "hypothesis_a": None,
        "hypothesis_b": None,
        "root_cause_analysis": None,
        "recommended_action": None,
        "human_approval_status": None,
        "human_notes": None,
        "action_execution_result": None,
        "verification_result": None,
        "agent_logs": ["[Test] Starting investigation..."]
    }

    print("\nStep 3: Running LangGraph workflow up to Human Approval interrupt...")
    for event in app_graph.stream(initial_state, config):
        pass

    state_snapshot = app_graph.get_state(config)
    paused_state = state_snapshot.values

    print("\n--- DEBATE & INVESTIGATION RESULTS ---")
    hyp_a = paused_state.get("hypothesis_a", {})
    hyp_b = paused_state.get("hypothesis_b", {})
    rca = paused_state.get("root_cause_analysis", {})
    action = paused_state.get("recommended_action", {})
    memory = paused_state.get("historical_incidents_evidence", [])

    print(f"Investigator A Claim: {hyp_a.get('claim')}")
    print(f"Investigator B Claim: {hyp_b.get('claim')}")
    print(f"Past Incident Memory: {memory}")
    print(f"Judge Verdict Cause:  {rca.get('probable_cause')} (Winning: {rca.get('winning_hypothesis')})")
    print(f"Confidence:            {rca.get('confidence')}")
    print(f"Reasoning:             {rca.get('reasoning')}")
    print(f"Proposed Action:       {action.get('description')} (Risk: {action.get('risk_level')})")
    print(f"Graph Next Step:       {state_snapshot.next}")

    assert state_snapshot.next == ('action_agent',), "Graph should interrupt before action_agent!"

    print("\nStep 4: Operator approving recommended remediation...")
    updated_state = {
        **paused_state,
        "human_approval_status": "approved",
        "human_notes": "Approved for test run."
    }
    app_graph.update_state(config, updated_state)

    print("\nStep 5: Resuming LangGraph workflow to execute action & verification...")
    for event in app_graph.stream(None, config):
        pass

    final_state = app_graph.get_state(config).values

    print("\n--- FINAL VERIFICATION RESULTS ---")
    verification = final_state.get("verification_result", {})
    print(f"Status:    {final_state.get('status')}")
    print(f"Summary:   {verification.get('summary')}")
    print(f"Recovered: {verification.get('is_recovered')}")

    assert final_state.get("status") == "resolved", "Incident status should be resolved!"
    print("\n[SUCCESS] End-to-end LangGraph test passed cleanly!")

if __name__ == "__main__":
    test_full_incident_lifecycle()

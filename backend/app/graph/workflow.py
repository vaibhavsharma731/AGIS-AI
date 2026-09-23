"""
backend/app/graph/workflow.py

Defines and compiles the AegisAI LangGraph state graph.
Includes Human-in-the-Loop checkpointer (MemorySaver) and node interrupts.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from backend.app.graph.state import IncidentState
from backend.app.agents.metrics_agent import metrics_agent_node
from backend.app.agents.log_agent import log_agent_node
from backend.app.agents.deployment_agent import deployment_agent_node
from backend.app.agents.rag_agent import rag_agent_node
from backend.app.agents.incident_memory_agent import incident_memory_agent_node
from backend.app.agents.debate_agents import (
    investigator_a_node,
    investigator_b_node,
    judge_agent_node
)
from backend.app.agents.remediation_agent import remediation_agent_node
from backend.app.agents.action_agent import action_agent_node
from backend.app.agents.verification_agent import verification_agent_node


def _feedback_challenges_rca(feedback: str) -> bool:
    """
    Checks if human rejection feedback questions the root cause diagnosis.
    """
    if not feedback:
        return False
    fb = feedback.lower()
    keywords = [
        "root cause", "rca", "cause", "hypothesis", "diagnos", "investigate",
        "check", "wrong", "not the issue", "not memory", "not cpu", "database",
        "db", "network", "code", "infra", "different issue"
    ]
    return any(kw in fb for kw in keywords)


def _route_after_action(state: IncidentState):
    """
    Conditional router after action_agent:
    - If operator approved:
        Routes to verification_agent regardless of execution outcome:
        * On success (status="executing"): verification_agent queries CloudWatch/metrics
          to confirm recovery.
        * On execution failure (status="action_failed"): verification_agent records the
          failure details as new evidence and delegates to _route_after_verification for
          retry or 3-attempt escalation.
    - If operator rejected:
        * If feedback challenges the RCA: re-run debate (investigator_a & investigator_b).
        * If feedback only rejects the specific action: route directly to remediation_agent.
    """
    if state.get("human_approval_status") == "approved":
        return "verification_agent"

    feedback = (state.get("human_feedback") or state.get("human_notes") or "").strip()
    if _feedback_challenges_rca(feedback):
        return ["investigator_a", "investigator_b"]

    return "remediation_agent"


def _route_after_verification(state: IncidentState):
    """
    Conditional router after verification_agent:
    - If recovered: END.
    - If unrecovered and attempts < 3: re-investigate via parallel debate investigators.
    - If unrecovered and attempts >= 3: END (escalated).
    """
    ver = state.get("verification_result") or {}
    is_recovered = ver.get("is_recovered", False)
    attempts = state.get("remediation_attempts", 0)

    if is_recovered or attempts >= 3:
        return END

    return ["investigator_a", "investigator_b"]


# Persistent memory checkpointer for human-in-the-loop state pause/resume
checkpointer = MemorySaver()

def build_graph():
    """
    Constructs the AegisAI LangGraph StateGraph workflow with Debate & Memory.
    """
    builder = StateGraph(IncidentState)

    # 1. Add Agent Nodes
    builder.add_node("metrics_agent", metrics_agent_node)
    builder.add_node("log_agent", log_agent_node)
    builder.add_node("deployment_agent", deployment_agent_node)
    builder.add_node("rag_agent", rag_agent_node)
    builder.add_node("incident_memory_agent", incident_memory_agent_node)
    builder.add_node("investigator_a", investigator_a_node)
    builder.add_node("investigator_b", investigator_b_node)
    builder.add_node("judge_agent", judge_agent_node)
    builder.add_node("remediation_agent", remediation_agent_node)
    builder.add_node("action_agent", action_agent_node)
    builder.add_node("verification_agent", verification_agent_node)

    # 2. Define Execution Edges
    builder.add_edge(START, "metrics_agent")
    builder.add_edge("metrics_agent", "log_agent")
    builder.add_edge("log_agent", "deployment_agent")
    builder.add_edge("deployment_agent", "rag_agent")
    builder.add_edge("rag_agent", "incident_memory_agent")
    # Fan-out: both investigators run IN PARALLEL from incident_memory_agent
    builder.add_edge("incident_memory_agent", "investigator_a")
    builder.add_edge("incident_memory_agent", "investigator_b")
    # Fan-in: judge_agent waits for BOTH investigators to complete
    builder.add_edge(["investigator_a", "investigator_b"], "judge_agent")
    builder.add_edge("judge_agent", "remediation_agent")
    builder.add_edge("remediation_agent", "action_agent")
    
    # Conditional router after action_agent: approved -> verification_agent, rejected -> debate or remediation
    builder.add_conditional_edges(
        "action_agent",
        _route_after_action,
        ["verification_agent", "remediation_agent", "investigator_a", "investigator_b"]
    )
    # Conditional router after verification_agent: recovered or attempts >= 3 -> END, else re-investigate
    builder.add_conditional_edges(
        "verification_agent",
        _route_after_verification,
        ["investigator_a", "investigator_b", END]
    )

    # 3. Compile Graph with Checkpointer & Human-in-the-Loop interrupt before 'action_agent'
    compiled_graph = builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["action_agent"]
    )
    
    return compiled_graph

# Pre-compiled graph instance
app_graph = build_graph()

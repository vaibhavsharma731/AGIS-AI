"""
backend/app/graph/state.py

Defines the shared state dictionary passed through nodes in the AegisAI LangGraph workflow.
Uses TypedDict for full type safety and simplicity.
"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated
import operator

class IncidentState(TypedDict):
    """
    State dictionary that flows through every agent node in the LangGraph workflow.
    """
    # Core Incident Metadata
    incident_id: str
    incident_description: str
    status: str  # "investigating", "awaiting_approval", "executing", "verifying", "resolved", "rejected"
    
    # Evidence gathered by specialized agents
    metrics_evidence: Optional[Dict[str, Any]]
    log_evidence: Optional[List[str]]
    deployment_evidence: Optional[List[Dict[str, Any]]]
    rag_evidence: Optional[List[str]]
    historical_incidents_evidence: Optional[List[str]]  # Past incident memory RAG
    
    # Multi-Agent Debate Hypotheses
    hypothesis_a: Optional[Dict[str, Any]]  # Investigator A (Code & Deployment focus)
    hypothesis_b: Optional[Dict[str, Any]]  # Investigator B (Infrastructure & Load focus)
    
    # Root Cause & Remediation conclusions
    root_cause_analysis: Optional[Dict[str, Any]]  # {probable_cause, cause_category, confidence, reasoning, key_findings, affected_service, affected_resource}
    cause_category: Optional[str]                   # Structured category: bad_deployment | memory_exhaustion | cpu_exhaustion | capacity_exhaustion | database_connection_exhaustion | configuration_error | dependency_failure | unknown
    recommended_action: Optional[Dict[str, Any]]    # {action_type, description, risk_level, target}
    
    # Human-in-the-Loop Approval State
    human_approval_status: Optional[str]  # "pending", "approved", "rejected"
    human_notes: Optional[str]
    human_feedback: Optional[str]  # Operator feedback when rejecting or redirecting

    # Iterative Recovery & Context
    remediation_attempts: int  # Starts at 0, incremented each time an approved action executes (max 3)
    previous_action: Optional[Dict[str, Any]]  # Prior action attempted (prevents blindly repeating failed fixes)
    previous_rca: Optional[Dict[str, Any]]  # Prior RCA verdict before re-investigation

    # Execution & Verification
    action_execution_result: Optional[Dict[str, Any]]
    verification_result: Optional[Dict[str, Any]]
    
    # Audit log of workflow steps — uses reducer so parallel nodes can both write safely
    agent_logs: Annotated[List[str], operator.add]

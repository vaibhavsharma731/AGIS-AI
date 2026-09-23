"""
backend/app/main.py

FastAPI backend server for AegisAI.
Exposes REST endpoints to trigger incident investigations, stream state updates,
and submit Human-in-the-Loop approval decisions.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

from backend.app.config import settings
from backend.app.graph.workflow import app_graph
from backend.app.tools.metrics_tools import get_system_metrics
from backend.app.services.aws_service import discover_aws_resources, get_boto3_client, fetch_cloudwatch_metrics

from fastapi.staticfiles import StaticFiles
import os

# Path for persisting incident history
HISTORY_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "mock_data", "incident_history.json"))

def load_history() -> List[Dict]:
    """Load incident history from disk."""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_to_history(state: Dict):
    """Append a completed incident state to the history file."""
    history = load_history()
    rca = state.get("root_cause_analysis") or {}
    action = state.get("recommended_action") or {}
    result = state.get("action_execution_result") or {}
    record = {
        "incident_id": state.get("incident_id", "INC-UNKNOWN"),
        "description": state.get("incident_description", ""),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "probable_cause": rca.get("probable_cause", "Unknown"),
        "winning_hypothesis": rca.get("winning_hypothesis", "Unknown"),
        "confidence": rca.get("confidence", "Unknown"),
        "action_taken": action.get("action_type", "None"),
        "action_target": action.get("target", ""),
        "outcome": result.get("status", "unknown"),
        "status": state.get("status", "unknown"),
        "full_state": state
    }
    history.insert(0, record)  # newest first
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history[:50], f, indent=2)  # keep last 50 incidents

def build_postmortem_markdown(state: Dict) -> str:
    """Generate a clean Markdown post-mortem report from incident state."""
    rca = state.get("root_cause_analysis") or {}
    hyp_a = state.get("hypothesis_a") or {}
    hyp_b = state.get("hypothesis_b") or {}
    action = state.get("recommended_action") or {}
    result = state.get("action_execution_result") or {}
    verification = state.get("verification_result") or {}
    logs = state.get("agent_logs") or []
    evidence = rca.get("key_evidence") or []
    
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# 📋 AegisAI Post-Mortem Report",
        f"",
        f"**Incident ID:** {state.get('incident_id', 'N/A')}  ",
        f"**Generated:** {now}  ",
        f"**Status:** {state.get('status', 'N/A').upper()}  ",
        f"**Remediation Attempts:** {state.get('remediation_attempts', 0)} / 3  ",
        f"",
        f"---",
        f"",
        f"## 🔍 Incident Description",
        f"",
        f"{state.get('incident_description', 'N/A')}",
        f"",
        f"---",
        f"",
        f"## 🕵️ Agent Debate Summary",
        f"",
        f"### Investigator A — Code & Deployment",
        f"- **Claim:** {hyp_a.get('claim', 'N/A')}",
        f"- **Reasoning:** {hyp_a.get('reasoning', 'N/A')}",
        f"- **Confidence:** {hyp_a.get('confidence', 'N/A')}",
        f"",
        f"### Investigator B — Infrastructure & Metrics",
        f"- **Claim:** {hyp_b.get('claim', 'N/A')}",
        f"- **Reasoning:** {hyp_b.get('reasoning', 'N/A')}",
        f"- **Confidence:** {hyp_b.get('confidence', 'N/A')}",
        f"",
        f"---",
        f"",
        f"## ⚖️ Judge Verdict — Root Cause Analysis",
        f"",
        f"| Field | Value |",
        f"|---|---|",
        f"| Probable Cause | {rca.get('probable_cause', 'N/A')} |",
        f"| Winning Hypothesis | {rca.get('winning_hypothesis', 'N/A')} |",
        f"| Confidence | {rca.get('confidence', 'N/A')} |",
        f"",
        f"**Reasoning:**",
        f"",
        f"{rca.get('reasoning', 'N/A')}",
        f"",
        f"**Key Evidence:**",
        f"",
    ]
    for ev in evidence:
        lines.append(f"- {ev}")
    lines += [
        f"",
        f"---",
        f"",
        f"## ⚡ Remediation Action",
        f"",
        f"| Field | Value |",
        f"|---|---|",
        f"| Action Type | {action.get('action_type', 'N/A')} |",
        f"| Target | {action.get('target', 'N/A')} |",
        f"| Risk Level | {action.get('risk_level', 'N/A')} |",
        f"| Description | {action.get('description', 'N/A')} |",
        f"| Execution Status | {result.get('status', 'N/A')} |",
        f"| Execution Details | {result.get('details', 'N/A')} |",
        f"",
        f"---",
        f"",
        f"## ✅ Verification",
        f"",
        f"{verification.get('summary', 'Not yet verified.')}",
        f"",
        f"---",
        f"",
        f"## 📜 Full Agent Audit Trail",
        f"",
    ]
    for log in logs:
        lines.append(f"- {log}")
    lines += [
        f"",
        f"---",
        f"*Generated by AegisAI Autonomous Incident Response Engine*",
    ]
    return "\n".join(lines)

app = FastAPI(
    title="AegisAI API",
    description="Autonomous Cloud Incident Response & Root-Cause Analysis Engine",
    version="1.0.0"
)

# Enable CORS for frontend dashboard access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount frontend directory static assets
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.exists(FRONTEND_DIR):
    app.mount("/dashboard", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

# Request Models
class IncidentStartRequest(BaseModel):
    scenario: Optional[str] = "db_exhaustion"
    incident_description: Optional[str] = "API latency spike & high error rate"

class ApprovalDecisionRequest(BaseModel):
    status: str  # "approved" or "rejected"
    notes: Optional[str] = ""

class SetupRequest(BaseModel):
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "us-east-1"
    cloudwatch_log_group: str = "/aws/apps/aegis-ai"
    github_token: Optional[str] = ""
    github_repo: Optional[str] = ""

from fastapi.responses import RedirectResponse

@app.get("/")
def root_redirect():
    return RedirectResponse(url="/dashboard/")

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "AegisAI Backend"}

@app.post("/api/setup")
def save_setup(req: SetupRequest):
    """
    Onboarding wizard endpoint.
    Receives credentials from the UI setup wizard, saves them to .env,
    and returns the updated integration status.
    """
    settings.update_integrations(
        aws_key=req.aws_access_key_id or None,
        aws_secret=req.aws_secret_access_key or None,
        aws_region=req.aws_region or None,
        cw_group=req.cloudwatch_log_group or None,
        github_token=req.github_token or None,
        github_repo=req.github_repo or None,
    )
    aws_ok = bool(settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY)
    github_ok = bool(settings.GITHUB_TOKEN and settings.GITHUB_REPO)
    return {
        "success": True,
        "aws_configured": aws_ok,
        "github_configured": github_ok,
        "region": settings.AWS_REGION,
        "cloudwatch_log_group": settings.CLOUDWATCH_LOG_GROUP,
        "github_repo": settings.GITHUB_REPO or "Not set",
    }

@app.get("/api/setup/status")
def get_setup_status():
    """Returns whether the app has been configured yet (for the onboarding check)."""
    aws_ok = bool(settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY)
    github_ok = bool(settings.GITHUB_TOKEN and settings.GITHUB_REPO)
    return {
        "configured": aws_ok,
        "aws_configured": aws_ok,
        "github_configured": github_ok,
        "region": settings.AWS_REGION,
        "cloudwatch_log_group": settings.CLOUDWATCH_LOG_GROUP,
        "github_repo": settings.GITHUB_REPO or "",
    }


@app.get("/api/integrations/status")
def integrations_status():
    """
    Checks and returns current status of external integrations (GitHub, AWS CloudWatch, Docker).
    """
    github_configured = bool(settings.GITHUB_REPO and settings.GITHUB_TOKEN)
    aws_configured = bool(settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY)
    
    return {
        "integration_mode": settings.INTEGRATION_MODE,
        "github": {
            "configured": github_configured,
            "repo": settings.GITHUB_REPO or "Not set",
            "status": "active" if github_configured else "mock_fallback"
        },
        "aws_cloudwatch": {
            "configured": aws_configured,
            "region": settings.AWS_REGION,
            "log_group": settings.CLOUDWATCH_LOG_GROUP,
            "status": "active" if aws_configured else "mock_fallback"
        },
        "docker": {
            "container_target": settings.DOCKER_CONTAINER_NAME,
            "status": "active"
        }
    }


@app.get("/api/metrics")
def get_current_metrics():
    """
    Returns live system metrics for the frontend status dashboard.
    """
    return get_system_metrics.invoke({})

@app.get("/api/infrastructure/discovered")
def get_discovered_infrastructure():
    """
    Discovers and returns all active AWS services in the connected account.
    Used by the frontend to populate the Infrastructure Detected and Evidence Availability panels.
    """
    cw_client = get_boto3_client("cloudwatch")
    if not cw_client:
        return {
            "available": False,
            "reason": "AWS credentials not configured or boto3 not installed.",
            "services": {}
        }

    discovered = discover_aws_resources(cw_client)

    # Build an availability-aware summary per service type
    summary = {
        "ec2":         {"available": len(discovered.get("ec2", [])) > 0,         "count": len(discovered.get("ec2", [])),         "resources": [r["Value"] for r in discovered.get("ec2", [])]},
        "rds":         {"available": len(discovered.get("rds", [])) > 0,         "count": len(discovered.get("rds", [])),         "resources": [r["Value"] for r in discovered.get("rds", [])]},
        "alb":         {"available": len(discovered.get("alb", [])) > 0,         "count": len(discovered.get("alb", [])),         "resources": [r["Value"] for r in discovered.get("alb", [])]},
        "api_gateway": {"available": len(discovered.get("api_gateway", [])) > 0, "count": len(discovered.get("api_gateway", [])), "resources": [r["Value"] for r in discovered.get("api_gateway", [])]},
        "lambda":      {"available": len(discovered.get("lambda", [])) > 0,      "count": len(discovered.get("lambda", [])),      "resources": [r["Value"] for r in discovered.get("lambda", [])]},
        "cloudwatch_logs": {
            "available": bool(settings.CLOUDWATCH_LOG_GROUP),
            "log_group": settings.CLOUDWATCH_LOG_GROUP or None
        },
        "github": {
            "available": bool(settings.GITHUB_TOKEN and settings.GITHUB_REPO),
            "repo": settings.GITHUB_REPO or None
        }
    }

    return {"available": True, "region": settings.AWS_REGION, "services": summary}


@app.post("/api/incident/simulate")
def simulate_scenario(scenario: str = "db_exhaustion"):
    """
    Simulate scenario endpoint (stubbed out since mock data has been removed in favor of live AWS telemetry).
    """
    return {"message": f"Real AWS mode is active. Scenario '{scenario}' noted."}

@app.post("/api/incident/investigate")
def investigate_incident(req: IncidentStartRequest):
    """
    Triggers the LangGraph investigation workflow for a thread ID.
    Executes up to the Human Approval interrupt point.
    """
    thread_id = f"thread_{req.scenario}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "incident_id": f"INC-{req.scenario.upper()}",
        "incident_description": req.incident_description,
        "status": "investigating",
        "metrics_evidence": None,
        "log_evidence": None,
        "deployment_evidence": None,
        "rag_evidence": None,
        "historical_incidents_evidence": None,
        "hypothesis_a": None,
        "hypothesis_b": None,
        "root_cause_analysis": None,
        "cause_category": None,
        "recommended_action": None,
        "human_approval_status": None,
        "human_notes": None,
        "human_feedback": None,
        "remediation_attempts": 0,
        "previous_action": None,
        "previous_rca": None,
        "action_execution_result": None,
        "verification_result": None,
        "agent_logs": ["[Incident Manager] Incident received. Starting agent investigation graph..."]
    }

    # Stream graph execution until it pauses at the interrupt point before 'action_agent'
    try:
        for event in app_graph.stream(initial_state, config):
            pass
        
        current_state = app_graph.get_state(config).values
        return {
            "thread_id": thread_id,
            "state": current_state
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph execution failed: {str(e)}")

@app.get("/api/incident/{thread_id}/state")
def get_incident_state(thread_id: str):
    """
    Retrieves current state of an ongoing or completed investigation thread.
    """
    config = {"configurable": {"thread_id": thread_id}}
    state_snapshot = app_graph.get_state(config)
    
    if not state_snapshot or not state_snapshot.values:
        raise HTTPException(status_code=404, detail="Incident thread not found.")
        
    return {
        "thread_id": thread_id,
        "next_step": state_snapshot.next,
        "state": state_snapshot.values
    }

@app.post("/api/incident/{thread_id}/approve")
def submit_approval_decision(thread_id: str, req: ApprovalDecisionRequest):
    """
    Submits Human Approval/Rejection decision and resumes the paused LangGraph workflow!
    """
    config = {"configurable": {"thread_id": thread_id}}
    state_snapshot = app_graph.get_state(config)

    if not state_snapshot or not state_snapshot.values:
        raise HTTPException(status_code=404, detail="Incident thread not found.")

    # Update state with human decision and feedback
    app_graph.update_state(config, {
        "human_approval_status": req.status,
        "human_notes": req.notes,
        "human_feedback": req.notes if req.status == "rejected" else None,
        "status": "approved" if req.status == "approved" else "rejected"
    })

    # Resume graph execution (invokes action_agent, verification_agent, and loops if needed)
    try:
        for event in app_graph.stream(None, config):
            pass

        updated_snapshot = app_graph.get_state(config)
        final_state = updated_snapshot.values
        is_paused = bool(updated_snapshot.next)

        # Persist completed incident to history if finished
        if not is_paused:
            save_to_history(final_state)

        return {
            "thread_id": thread_id,
            "status": "awaiting_approval" if is_paused else "completed",
            "state": final_state
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resume graph: {str(e)}")


@app.get("/api/incidents/history")
def get_incident_history():
    """
    Returns list of past completed incidents (newest first, max 50).
    """
    return load_history()


@app.get("/api/incident/{thread_id}/report")
def download_postmortem_report(thread_id: str):
    """
    Generates and returns a Markdown post-mortem report for a completed incident.
    Client downloads this as a .md file.
    """
    config = {"configurable": {"thread_id": thread_id}}
    state_snapshot = app_graph.get_state(config)

    if not state_snapshot or not state_snapshot.values:
        raise HTTPException(status_code=404, detail="Incident thread not found.")

    state = state_snapshot.values
    markdown = build_postmortem_markdown(state)
    incident_id = state.get("incident_id", thread_id)

    return PlainTextResponse(
        content=markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="postmortem_{incident_id}.md"'}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host=settings.HOST, port=settings.PORT, reload=True)

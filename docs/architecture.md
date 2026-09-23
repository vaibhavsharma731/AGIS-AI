# AegisAI — System Architecture & Workflow Guide

AegisAI is an autonomous cloud incident response platform built with **LangChain** and **LangGraph**.

## 1. High-Level Architecture

```text
               +-----------------------------------+
               |    FastAPI REST Server (8000)     |
               +-----------------------------------+
                                 |
                        [ Incident Trigger ]
                                 v
  +-----------------------------------------------------------------+
  |                       LangGraph Engine                          |
  |                                                                 |
  |  [Metrics Agent] -> [Log Agent] -> [Deployment Agent] -> [RAG]  |
  |                                                            |    |
  |  [Action Agent] <- [Human Approval (Interrupt)] <- [RCA Agent]  |
  |        |                                                        |
  |        v                                                        |
  |  [Verification Agent] -> [Resolved / Incident Report]           |
  +-----------------------------------------------------------------+
                                 |
                        [ Real-time Updates ]
                                 v
               +-----------------------------------+
               |  Interactive Frontend Dashboard   |
               +-----------------------------------+
```

---

## 2. Core Components

### A. Graph State (`backend/app/graph/state.py`)
State flows between nodes as a single Python `TypedDict` (`IncidentState`):
- `incident_id`: Unique identifier (e.g. `INC-1001`).
- `metrics_evidence`: CPU, latency, active DB connections, error rate.
- `log_evidence`: Filtered log lines containing `ERROR` or `CRITICAL`.
- `deployment_evidence`: Git commit messages, authors, modified files.
- `rag_evidence`: Relevant runbook sections retrieved from FAISS.
- `root_cause_analysis`: Structured JSON report (probable cause, confidence, evidence).
- `recommended_action`: Action type, target component, risk level.
- `human_approval_status`: `"pending"`, `"approved"`, or `"rejected"`.
- `verification_result`: Post-action metric check and recovery confirmation.

### B. Human-in-the-Loop (`backend/app/graph/workflow.py`)
LangGraph pauses execution before risky actions using `MemorySaver` checkpointer and `interrupt_before=["action_agent"]`.
- The graph stops after `remediation_agent` proposes a fix.
- The human operator reviews the RCA and clicks **Approve** or **Reject** on the web dashboard.
- Calling `/api/incident/{thread_id}/approve` updates graph state and resumes execution from `action_agent`.

### C. RAG Engine (`backend/app/rag/`)
- Loads operational runbooks from `backend/knowledge/runbooks/`.
- Splits docs with `RecursiveCharacterTextSplitter`.
- Indexing with `FAISS` vector store.
- Supports Google Gemini Embeddings, OpenAI Embeddings, HuggingFace embeddings, or CPU fallback.

---

## 3. Directory Layout

- `backend/`: Fast, clean Python backend using FastAPI, LangChain, and LangGraph.
- `frontend/`: Single-page dark-mode web dashboard serving real-time telemetry and approval UI.
- `docs/`: Architecture guides and setup documentation.
- `fake_scripts/`: Mock telemetry generator (`simulate_incident.py`).

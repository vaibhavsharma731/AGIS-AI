# AegisAI — Autonomous Cloud Incident Response & Root-Cause Analysis Platform

## 1. Project Overview

**Project name:** AegisAI

**One-line description:**

> AegisAI is an AI-powered cloud incident investigation and response system that uses LangChain and LangGraph to investigate production incidents, collect evidence from multiple sources, use RAG-based organizational knowledge, identify a probable root cause, recommend remediation, request human approval for risky actions, execute approved actions, and verify recovery.

### The core idea

Instead of a developer manually checking:

- Cloud metrics
- Application logs
- Recent deployments
- Documentation/runbooks
- Previous incidents

AegisAI coordinates specialized AI agents that investigate the incident step by step.

The core lifecycle is:

**Observe → Investigate → Correlate → Explain → Ask for approval → Act → Verify → Report**

---

# 2. Why We Are Building This

A normal chatbot answers questions.

A normal RAG application retrieves information from documents.

AegisAI should demonstrate something more advanced:

- Multi-step AI workflows
- Agent/tool use
- RAG
- LangChain
- LangGraph
- Human-in-the-loop
- Persistent state
- Incident memory
- Cloud monitoring
- Controlled automation
- Evidence-based reasoning
- Verification after an action

The project should feel like a small AI engineering product, not a demo chatbot.

---

# 3. Important Development Philosophy

## Keep the code understandable

This is one of the most important requirements.

Do **NOT** write unnecessarily complicated Python.

Prefer:

```python
def get_incident():
    ...

def check_metrics():
    ...

def search_logs():
    ...

def find_recent_deployment():
    ...

def investigate_incident():
    ...
```

over complicated abstractions that hide what the application is doing.

Every important function should have one obvious responsibility.

Avoid:

- unnecessary design patterns
- excessive inheritance
- deeply nested classes
- overly clever one-liners
- unnecessary decorators
- giant functions
- difficult async code unless actually needed
- complicated custom frameworks
- unnecessary microservices
- premature optimization

The project should be understandable to a final-year BTech student learning AI engineering.

---

# 4. LangChain Requirement

Use LangChain for understandable, meaningful tasks.

Examples:

- Chat model
- Prompt templates
- Structured output
- Tools
- Document loading
- Text splitting
- Embeddings
- Retriever
- RAG chain
- Tool calling

Do not add LangChain simply to mention it in the README.

Whenever LangChain is used, the code should make it obvious why it is being used.

---

# 5. LangGraph Requirement

Use LangGraph for orchestration.

The graph should represent the incident investigation workflow.

Initial graph:

```text
START
  |
  v
Incident Manager
  |
  +------> Metrics Agent
  |
  +------> Log Agent
  |
  +------> Deployment Agent
  |
  v
RCA Agent
  |
  v
RAG / Knowledge Agent
  |
  v
Remediation Agent
  |
  v
Human Approval
  |
  +---- Reject ----> Investigation / End
  |
  +---- Approve ---> Action Agent
                         |
                         v
                    Verification
                         |
                         v
                       Report
                         |
                         v
                        END
```

The exact graph can evolve during development.

---

# 6. What Each Agent Does

## Agent 1 — Incident Manager

Input:

```text
Incident description
```

Example:

> API response time increased significantly during the last 15 minutes.

Responsibilities:

- Understand the incident
- Identify what needs investigation
- Coordinate the investigation
- Store important information in graph state

Keep this agent simple.

---

## Agent 2 — Metrics Agent

Purpose:

Investigate infrastructure/service metrics.

Possible metrics:

- CPU utilization
- Memory utilization
- Request count
- Error rate
- Latency
- Instance count

For the initial version, these can be simulated.

Later, connect them to AWS CloudWatch.

Example result:

```text
CPU increased from 18% to 94%.
Error rate increased from 1% to 17%.
Latency increased from 220ms to 4.8s.
```

---

## Agent 3 — Log Agent

Purpose:

Investigate application/system logs.

Initial version:

Use sample log files or generated logs.

Later:

Connect to AWS CloudWatch Logs.

Example:

```text
ERROR Database connection pool exhausted
ERROR Request timeout
WARNING Too many active connections
```

The agent should return relevant evidence, not a giant dump of logs.

---

## Agent 4 — Deployment Agent

Purpose:

Check whether a recent deployment could be related to the incident.

Initial version:

Use a small mock deployment history.

Later:

Connect to GitHub.

Example:

```text
Latest deployment:
#184

Time:
10 minutes before incident

Changed:
database.py
connection_pool.py
```

---

# 7. RAG Knowledge Agent

This is an important part of the project.

Create a knowledge base containing:

```text
knowledge/
    runbooks/
    architecture/
    troubleshooting/
    previous_incidents/
```

Example documents:

```text
database_runbook.md
api_troubleshooting.md
aws_ec2_runbook.md
incident_102.md
incident_103.md
```

RAG pipeline:

```text
Documents
   |
   v
Document Loader
   |
   v
Text Chunking
   |
   v
Embeddings
   |
   v
Vector Database
   |
   v
Retriever
   |
   v
Relevant Context
   |
   v
LLM
```

Use a simple vector database for development.

Possible choice:

**FAISS**

Alternative:

**Qdrant**

Do not overcomplicate the first version.

---

# 8. Root Cause Analysis Agent

This agent receives evidence from:

- Metrics Agent
- Log Agent
- Deployment Agent
- RAG Agent

Example:

```text
Metrics:
CPU = 94%

Logs:
Database connection pool exhausted

Deployment:
database.py changed 10 minutes ago

RAG:
Runbook says connection exhaustion can occur
when database connections are not released correctly.
```

The agent produces a structured result:

```text
Probable Root Cause:
Recent database connection handling change.

Evidence:
1. Connection pool exhaustion in logs.
2. Database code changed shortly before incident.
3. CPU and latency increased at the same time.

Confidence:
High / Medium / Low

Reasoning:
Short, understandable explanation.
```

Do not make the model claim certainty when the evidence is incomplete.

---

# 9. Remediation Agent

The remediation agent proposes actions.

Example:

```text
Recommended action:
Rollback deployment #184

Reason:
The deployment changed database connection handling
and occurred shortly before the incident.

Risk:
Medium
```

Possible actions:

- Restart service
- Scale service
- Roll back deployment
- Increase capacity
- Disable a simulated problematic feature

For safety, actual destructive actions must NOT happen automatically.

---

# 10. Human-in-the-Loop

This is a major LangGraph feature.

Before a risky action:

```text
AI investigation
      |
      v
Recommended remediation
      |
      v
HUMAN APPROVAL
      |
   +--+--+
   |     |
Approve Reject
   |     |
   v     v
Action  Stop / Reinvestigate
```

The user should see:

```text
ROOT CAUSE

Database connection pool exhaustion

RECOMMENDED ACTION

Rollback deployment #184

RISK

Medium

EVIDENCE

CloudWatch logs
Recent deployment
Internal runbook

[ APPROVE ]
[ REJECT ]
```

Use LangGraph's interrupt/resume functionality for this.

The approval step should be easy to understand in code.

---

# 11. Action Agent

After approval:

```text
Human approves
      |
      v
Action Agent
      |
      v
Execute approved action
```

### IMPORTANT

Do not immediately connect this to a real production AWS environment.

For development:

1. Build a simulated environment.
2. Make the action safe.
3. Verify the entire workflow.
4. Only later connect a small AWS test environment.

The first implementation can simulate:

```text
restart_service()
scale_service()
rollback_deployment()
```

These functions can update a mock environment.

---

# 12. Verification Agent

After remediation:

```text
Action
  |
  v
Verification
  |
  +---- Problem remains ----> Investigate again
  |
  +---- Recovered ----------> Generate report
```

Example:

Before:

```text
Latency: 4.8 sec
Errors: 17%
CPU: 94%
```

After:

```text
Latency: 210 ms
Errors: 0.4%
CPU: 31%
```

The AI should report whether the system appears recovered based on the available test metrics.

---

# 13. Incident Memory

After resolving an incident, save a structured incident record.

Example:

```text
incident_id: 1042

problem:
API latency increased

root_cause:
Database connection exhaustion

evidence:
...

action:
Rollback deployment #184

result:
Recovered
```

Store historical incidents in a database or suitable storage.

Then future investigations can retrieve similar incidents.

This creates a second useful RAG use case:

```text
New Incident
     |
     v
Search Historical Incidents
     |
     v
Find Similar Incident
     |
     v
Use Previous Evidence/Solution
```

---

# 14. Multi-Agent Debate — Optional Advanced Feature

Only add this after the basic system works.

Two investigators can independently analyze the incident:

```text
                 Incident
                    |
           +--------+--------+
           |                 |
           v                 v
    Investigator A     Investigator B
           |                 |
           v                 v
      Hypothesis A       Hypothesis B
           |                 |
           +--------+--------+
                    |
                    v
               Judge Agent
                    |
                    v
             Final Analysis
```

If the agents disagree, the graph can request more evidence.

Do not build this in V1.

---

# 15. Suggested Project Structure

Keep the repository clean and structured.

```text
aegis-ai/
│
├── backend/
│   │
│   ├── app/
│   │   ├── main.py
│   │   │
│   │   ├── agents/
│   │   │   ├── incident_manager.py
│   │   │   ├── metrics_agent.py
│   │   │   ├── log_agent.py
│   │   │   ├── deployment_agent.py
│   │   │   ├── rag_agent.py
│   │   │   ├── rca_agent.py
│   │   │   ├── remediation_agent.py
│   │   │   └── verification_agent.py
│   │   │
│   │   ├── graph/
│   │   │   ├── state.py
│   │   │   └── workflow.py
│   │   │
│   │   ├── tools/
│   │   │   ├── metrics_tools.py
│   │   │   ├── log_tools.py
│   │   │   ├── github_tools.py
│   │   │   └── aws_tools.py
│   │   │
│   │   ├── rag/
│   │   │   ├── ingest.py
│   │   │   ├── embeddings.py
│   │   │   └── retriever.py
│   │   │
│   │   ├── models/
│   │   │   └── schemas.py
│   │   │
│   │   └── config.py
│   │
│   ├── knowledge/
│   │   ├── runbooks/
│   │   ├── architecture/
│   │   └── previous_incidents/
│   │
│   ├── tests/
│   │
│   ├── requirements.txt
│   └── README.md
│
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── README.md
│
├── mock_data/
│   ├── logs/
│   ├── metrics/
│   └── deployments/
│
├── docs/
│   ├── architecture.md
│   ├── workflow.md
│   └── setup.md
│
├── .env.example
├── .gitignore
└── README.md
```

The exact framework for the frontend can be chosen later.

---

# 16. Development Phases

## Phase 1 — Understand the architecture

Before writing code, explain:

- What is an agent?
- What is LangChain?
- What is LangGraph?
- What is graph state?
- What is a node?
- What is an edge?
- What is RAG?
- What is a tool?
- What is human-in-the-loop?

Do not start with a huge amount of code.

---

## Phase 2 — Build a tiny LangGraph

Create:

```text
START
  ↓
Agent
  ↓
END
```

Then:

```text
START
  ↓
Investigation
  ↓
RCA
  ↓
END
```

Make sure the student understands the graph before adding complexity.

---

## Phase 3 — Add simulated investigation tools

Add:

```text
Metrics
Logs
Deployments
```

Use simple Python functions first.

Example:

```python
def get_metrics():
    return {
        "cpu": 94,
        "latency": 4.8,
        "error_rate": 17
    }
```

---

## Phase 4 — Add RAG

Create a small knowledge base.

Build:

```text
documents
→ chunks
→ embeddings
→ FAISS
→ retriever
→ LLM
```

Test RAG separately before connecting it to LangGraph.

---

## Phase 5 — Combine RAG + Agents + LangGraph

Connect the pieces.

```text
Incident
→ Metrics
→ Logs
→ Deployment
→ RAG
→ RCA
```

---

## Phase 6 — Add Human Approval

Add LangGraph interrupt/resume.

Do not proceed to real cloud actions until this works.

---

## Phase 7 — Add simulated remediation

Implement safe mock actions.

Test:

```text
incident
→ investigation
→ recommendation
→ approval
→ simulated action
→ verification
```

---

## Phase 8 — Build the frontend

Create a dashboard showing:

- Current incident
- Agent status
- Investigation timeline
- Metrics
- Logs
- Retrieved evidence
- Root cause
- Confidence
- Recommended action
- Human approval
- Verification result

The interface should feel like an incident command center, not a generic chatbot.

---

## Phase 9 — Add AWS test environment

ONLY AFTER THE APPLICATION WORKS LOCALLY.

Create a small AWS test setup.

Possible components:

```text
EC2
CloudWatch
Application Load Balancer
Auto Scaling
```

Use the smallest practical resources and monitor costs.

Start with read-only investigation.

Then add one controlled remediation action.

---

## Phase 10 — Testing and Evaluation

Test cases should include:

### Case 1
CPU spike

### Case 2
Database connection exhaustion

### Case 3
Recent bad deployment

### Case 4
No obvious root cause

### Case 5
Conflicting evidence

### Case 6
Recommended action rejected by human

### Case 7
Remediation fails

### Case 8
System recovers after remediation

Measure:

- Correct retrieval
- Evidence quality
- Root-cause accuracy
- Tool-call correctness
- Human approval behavior
- Verification correctness
- Failure handling

---

# 17. What NOT to Do

Do not:

- Copy another GitHub project's code.
- Build 10 agents immediately.
- Make every function an agent.
- Use LangGraph where a normal Python function is enough.
- Use LangChain just for the resume.
- Give an LLM unrestricted AWS credentials.
- Automatically execute dangerous cloud actions.
- Hardcode fake results and pretend they came from AWS.
- Create a giant complicated Python architecture.
- Start with deployment before local testing.
- Add unnecessary technologies just to make the stack look impressive.

---

# 18. V1 Definition of Done

V1 is complete when this works:

```text
User enters incident
        ↓
LangGraph starts
        ↓
Metrics checked
        ↓
Logs checked
        ↓
Deployment checked
        ↓
RAG retrieves relevant runbook
        ↓
RCA generated
        ↓
Remediation proposed
        ↓
Human approves/rejects
        ↓
Safe simulated action
        ↓
Verification
        ↓
Final incident report
```

Do NOT add AWS before this works.

---

# 19. Example Final Output

```text
==================================================
AEGISAI INCIDENT REPORT
==================================================

Incident:
API latency increased significantly.

Status:
RESOLVED

Probable Root Cause:
Database connection pool exhaustion following
a recent deployment.

Evidence:

1. CPU increased from 18% to 94%.
2. Application logs show connection pool exhaustion.
3. Deployment #184 occurred 10 minutes before
   the incident.
4. Internal runbook describes the same failure pattern.

Recommended Remediation:
Rollback deployment #184.

Human Approval:
APPROVED

Action:
Rollback executed.

Verification:

Before:
Latency: 4.8s
Error rate: 17%

After:
Latency: 210ms
Error rate: 0.4%

Conclusion:
Service metrics returned to normal ranges.
==================================================
```

---

# 20. Resume Description

### AegisAI — Autonomous Cloud Incident Response & Root-Cause Analysis

> Built a multi-agent incident response platform using LangChain and LangGraph that investigates cloud incidents by correlating infrastructure metrics, application logs, deployment history, historical incidents, and RAG-retrieved runbooks; generates evidence-backed root-cause analyses and remediation plans, uses human approval for consequential actions, and verifies service recovery.

Technologies:

```text
Python
LangChain
LangGraph
RAG
FAISS/Qdrant
LLM
AWS
CloudWatch
GitHub API
FastAPI
React/Next.js
PostgreSQL
Docker
```

---

# 21. Important Interview Understanding

The student must be able to explain these questions:

### Why LangGraph?

Because the application is a stateful multi-step workflow with branching, loops, persistence, and human approval.

### Why LangChain?

For model integration, prompts, structured outputs, tools, document processing, embeddings, and retrieval.

### Why RAG?

The AI needs organization-specific runbooks, architecture information, and previous incidents that are not reliably contained in the model's training data.

### Why multiple agents?

Different investigation tasks require different tools and responsibilities.

### Why not one LLM?

A single LLM response does not reliably perform the complete investigation workflow or provide controlled execution.

### Why human-in-the-loop?

Cloud actions can have consequences. The AI should not blindly execute risky remediation.

### Why incident memory?

Previous incidents can provide useful evidence and context for future investigations.

### What happens if the AI is wrong?

Evidence should be shown, confidence should not be treated as certainty, actions should be controlled, and verification should determine whether the remediation actually worked.

---

# 22. Final Architecture

```text
                         ┌─────────────────────┐
                         │       FRONTEND      │
                         │  Incident Dashboard │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │       FASTAPI       │
                         └──────────┬──────────┘
                                    │
                                    ▼
                     ┌────────────────────────────┐
                     │       LANGGRAPH            │
                     │       ORCHESTRATOR         │
                     └────────────┬───────────────┘
                                  │
          ┌───────────────────────┼──────────────────────┐
          │                       │                      │
          ▼                       ▼                      ▼
   Metrics Agent             Log Agent           Deployment Agent
          │                       │                      │
          └───────────────────────┼──────────────────────┘
                                  ▼
                          ┌──────────────┐
                          │   RCA Agent  │
                          └──────┬───────┘
                                 │
                                 ▼
                          ┌──────────────┐
                          │   RAG Agent  │
                          └──────┬───────┘
                                 │
                     ┌───────────┴───────────┐
                     ▼                       ▼
               Vector Database         Incident Memory
                     │                       │
                     └───────────┬───────────┘
                                 ▼
                         Remediation Agent
                                 │
                                 ▼
                         HUMAN APPROVAL
                                 │
                                 ▼
                           Action Agent
                                 │
                                 ▼
                         Verification Agent
                                 │
                                 ▼
                         Incident Report
```

---

# 23. Rules for the AI Coding Assistant

The AI coding assistant must:

1. Read this document completely before writing project code.
2. Understand the architecture before implementing it.
3. Build the project incrementally.
4. Explain each important concept before introducing it.
5. Use simple Python.
6. Keep functions small and readable.
7. Use clear variable names.
8. Use LangChain meaningfully.
9. Use LangGraph meaningfully.
10. Never hide the important workflow behind complicated abstractions.
11. Keep backend and frontend separate.
12. Keep RAG code separate from agent code.
13. Keep tools separate from agents.
14. Keep graph state and graph workflow separate.
15. Keep mock data separate from real AWS integrations.
16. Build and test locally first.
17. Add AWS testing only after the local project is complete.
18. Never use real production infrastructure.
19. Never give unrestricted cloud permissions.
20. Explain errors and fix them step by step.
21. After every major phase, test the existing functionality before moving forward.
22. Do not rewrite working code unnecessarily.
23. Do not add technologies without explaining why they are needed.
24. Prefer a working simple implementation over an impressive complicated implementation.

---

# 24. Development Principle

> **Understand → Build → Test → Explain → Improve**

The goal is not merely to produce code.

The goal is for the developer/student to understand the entire project well enough to explain it confidently in an interview.


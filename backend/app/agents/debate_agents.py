"""
backend/app/agents/debate_agents.py

Multi-Agent Debate System — three agents work together to find the root cause:

  Investigator A  →  Blames CODE changes or recent DEPLOYMENTS
  Investigator B  →  Blames INFRASTRUCTURE overload (CPU, memory, traffic spikes)
  Judge Agent     →  Reads both arguments, looks at evidence, picks the true root cause

The two investigators run IN PARALLEL (see workflow.py), then the Judge reads both results.
"""

import json
import logging
from langchain_core.prompts import PromptTemplate
from backend.app.graph.state import IncidentState
from backend.app.agents.llm_factory import get_llm

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# PROMPTS
# Each prompt is a template with {placeholders} that get filled in at runtime.
# ─────────────────────────────────────────────────────────────────────────────

# Investigator A: looks at recent deployments and code changes
INVESTIGATOR_A_PROMPT = PromptTemplate.from_template("""
You are Investigator A, a senior Site Reliability Engineer specialising in CODE CHANGES and DEPLOYMENT FAILURES.
Your sole job is to build the strongest possible case that the root cause of this incident is a recent deployment, config change, or code regression.

━━━ INCIDENT BRIEF ━━━
{description}

━━━ DEPLOYMENT HISTORY ━━━
{deployments}

━━━ LOG EVIDENCE ━━━
{logs}

━━━ YOUR TASK ━━━
Follow these reasoning steps:

1. EVIDENCE SCAN — List every deployment, config change, or release event present in the data.
   Note timestamps, affected services, and any rollback events.

2. ANOMALY IDENTIFICATION — Find log lines that correlate with a deployment window:
   - Errors, exceptions, or warnings that appeared AFTER a deployment
   - Services that restarted, crashed, or changed behaviour post-deploy
   - Any "version", "release", "migration", or "schema change" indicators in logs

3. HYPOTHESIS CONSTRUCTION — Build your argument:
   - Which specific deployment is most likely responsible?
   - What mechanism caused the failure? (e.g. bad env var, DB migration, removed API endpoint, memory leak in new code)
   - How strongly does the timeline support your case?

4. CONFIDENCE RATING — Based on how much concrete deployment/log evidence you found:
   - "High"   → clear timeline correlation + specific log errors tied to a deployment
   - "Medium" → partial evidence, some timing correlation but gaps exist
   - "Low"    → weak or no deployment evidence; mostly circumstantial

IMPORTANT RULES:
- If deployment history is empty or unavailable, state that clearly and rate confidence "Low".
- Do NOT invent deployments. Only reference what is in the data above.
- Be specific: quote actual log messages or deployment names when possible.
- Keep claim under 20 words. Keep reasoning under 200 words.

Return ONLY valid JSON, no markdown fences, no extra keys:
{{
  "claim": "One-sentence root cause claim under 20 words",
  "evidence_cited": ["Specific log line or deployment event 1", "Specific log line or deployment event 2"],
  "reasoning": "Step-by-step explanation citing concrete evidence from the data above.",
  "confidence": "High | Medium | Low",
  "affected_service": "Name of the service or component most likely responsible"
}}
""")

# Investigator B: looks at system metrics (CPU, memory, latency)
INVESTIGATOR_B_PROMPT = PromptTemplate.from_template("""
You are Investigator B, a senior Infrastructure Engineer specialising in SYSTEM METRICS, RESOURCE EXHAUSTION, and PERFORMANCE DEGRADATION.
Your sole job is to build the strongest possible case that the root cause of this incident is an infrastructure or resource problem — not a code bug.

━━━ INCIDENT BRIEF ━━━
{description}

━━━ METRICS DATA ━━━
{metrics}

━━━ LOG EVIDENCE ━━━
{logs}

━━━ YOUR TASK ━━━
Follow these reasoning steps:

1. METRICS SCAN — Examine each metric value provided:
   - CPU utilisation: is it above 80%? Sustained or spiked?
   - Memory usage: approaching limit? OOM killer events?
   - Error rate / 5xx responses: is the percentage above normal baseline?
   - Latency (p95/p99): are response times significantly elevated?
   - Connection counts: DB connection pool exhaustion? Network saturation?
   - Note: if a metric shows 0 or "Unavailable", say so — do NOT assume it is fine.

2. ANOMALY IDENTIFICATION — Find infrastructure warning signs in logs:
   - Timeout errors, connection refused, resource limit exceeded
   - OOM kill, swap usage, disk I/O saturation messages
   - Autoscaling events, load balancer health check failures
   - Cascading failures (one service degrading others)

3. HYPOTHESIS CONSTRUCTION — Build your argument:
   - Which resource bottleneck is most likely the root cause?
   - What is the failure chain? (e.g. CPU spike → slow DB queries → timeout cascade → 503 errors)
   - Does the timing of metric anomalies match the incident window?

4. CONFIDENCE RATING — Based on how much concrete metric evidence you found:
   - "High"   → multiple metrics are clearly anomalous + log evidence confirms resource exhaustion
   - "Medium" → one or two metrics are elevated, some log correlation
   - "Low"    → metrics are mostly normal/unavailable; circumstantial at best

IMPORTANT RULES:
- If metrics data is empty, 0, or marked "Unavailable", state that clearly and lower confidence accordingly.
- Do NOT assume high resource usage if the data does not show it.
- Quote actual metric values (e.g. "CPU at 94%") when referencing evidence.
- Keep claim under 20 words. Keep reasoning under 200 words.

Return ONLY valid JSON, no markdown fences, no extra keys:
{{
  "claim": "One-sentence root cause claim under 20 words",
  "evidence_cited": ["Specific metric value or log line 1", "Specific metric value or log line 2"],
  "reasoning": "Step-by-step explanation citing concrete metric values and log evidence.",
  "confidence": "High | Medium | Low",
  "affected_resource": "The specific resource or system component that is saturated or failing"
}}
""")

# Judge Agent: reads both investigators' arguments and picks a winner
JUDGE_PROMPT = PromptTemplate.from_template("""
You are the Chief Incident Judge — a principal engineer who has investigated hundreds of production outages.
Your role is to objectively evaluate two competing hypotheses, weigh the evidence, and deliver the definitive Root Cause Analysis (RCA).

━━━ INCIDENT DESCRIPTION ━━━
{description}

━━━ HYPOTHESIS A (Code & Deployment) ━━━
{hyp_a}

━━━ HYPOTHESIS B (Infrastructure & Resources) ━━━
{hyp_b}

━━━ SUPPORTING EVIDENCE ━━━
Metrics: {metrics}
Logs:    {logs}

━━━ RUNBOOK & KNOWLEDGE BASE ━━━
{rag_docs}

━━━ HISTORICAL INCIDENT MEMORY ━━━
{past_incidents}

━━━ YOUR JUDGMENT PROCESS ━━━
Work through each step carefully:

1. EVIDENCE WEIGHING
   - Which investigator cited stronger, more specific evidence?
   - Does the evidence from metrics/logs support A, B, or both?
   - Are there any contradictions or data gaps that weaken either case?

2. RUNBOOK & HISTORY CROSS-CHECK
   - Do the runbooks describe a known failure pattern that matches either hypothesis?
   - Have past incidents with similar symptoms had the same root cause?
   - Does historical memory reinforce or contradict either investigator?

3. FINAL VERDICT
   - Pick the stronger hypothesis, or "Combined" if both factors contributed equally.
   - State the exact root cause in plain engineering language.
   - Identify the top 3-5 pieces of key evidence that drove your decision.

4. CONFIDENCE ASSESSMENT
   - "High"   → overwhelming evidence for one clear cause
   - "Medium" → solid evidence but some ambiguity remains
   - "Low"    → insufficient data to be certain; multiple causes equally plausible

IMPORTANT RULES:
- Base your verdict ONLY on the evidence above. Do NOT add assumed facts.
- If both hypotheses are weak (low confidence ratings), say so honestly.
- The key_findings must reference actual data — not generic statements.
- Keep probable_cause under 15 words. Keep reasoning under 300 words.

Return ONLY valid JSON, no markdown fences, no extra keys:
{{
  "probable_cause": "Concise root cause title under 15 words",
  "cause_category": "One of: bad_deployment | memory_exhaustion | cpu_exhaustion | capacity_exhaustion | database_connection_exhaustion | configuration_error | dependency_failure | unknown",
  "winning_hypothesis": "Investigator A | Investigator B | Combined",
  "confidence": "High | Medium | Low",
  "affected_service": "Name of the primary application service affected, or null if unknown",
  "affected_resource": "Name of the primary AWS/infrastructure resource affected (e.g. RDS instance name, EC2 id), or null if unknown",
  "reasoning": "Thorough explanation citing specific evidence, runbook matches, and historical patterns.",
  "key_findings": [
    "Finding 1 with specific evidence reference",
    "Finding 2 with specific evidence reference",
    "Finding 3 with specific evidence reference"
  ]
}}
""")


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def parse_llm_json(raw_response, fallback_type: str = "investigator") -> dict:
    """
    Converts the raw text the LLM returns into a Python dictionary.
    Includes regex/boundary substring extraction and a try/except safety net
    with fallback schemas to prevent JSONDecodeError crashes.
    """
    # If the response came back as a list of parts, join into one string
    if isinstance(raw_response, list):
        text = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in raw_response
        )
    else:
        text = str(raw_response)

    # Remove markdown code fences if present, then strip surrounding whitespace
    clean_text = text.strip().replace("```json", "").replace("```", "").strip()

    # 1. Direct JSON parse attempt
    try:
        return json.loads(clean_text)
    except Exception:
        pass

    # 2. Extract JSON object substring between outermost '{' and '}'
    try:
        start_idx = clean_text.find("{")
        end_idx = clean_text.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            substring = clean_text[start_idx:end_idx + 1]
            return json.loads(substring)
    except Exception as e:
        logger.warning(f"[Debate Agents] JSON parse failed ({e}). Raw text: {clean_text[:180]}")

    # 3. Graceful fallback schemas so downstream nodes never crash on malformed JSON
    if fallback_type == "judge":
        return {
            "probable_cause": "System degradation requiring manual investigation",
            "cause_category": "unknown",
            "winning_hypothesis": "Combined",
            "confidence": "Low",
            "affected_service": None,
            "affected_resource": None,
            "reasoning": f"Model returned unformatted response: {clean_text[:250]}",
            "key_findings": ["Automated analysis produced unstructured JSON; safe fallback engaged."]
        }
    elif fallback_type == "investigator_b":
        return {
            "claim": "Infrastructure overload suspected based on telemetry",
            "evidence_cited": [],
            "reasoning": f"Model returned unformatted response: {clean_text[:250]}",
            "confidence": "Low",
            "affected_resource": "unknown"
        }
    else:
        return {
            "claim": "Code or configuration regression suspected",
            "evidence_cited": [],
            "reasoning": f"Model returned unformatted response: {clean_text[:250]}",
            "confidence": "Low",
            "affected_service": "unknown"
        }


def _format_context_note(state: IncidentState) -> str:
    """Format previous attempt, verification failure, or human feedback into brief context."""
    notes = []
    if state.get("previous_action"):
        act = state["previous_action"]
        notes.append(f"PREVIOUS ATTEMPTED ACTION: {act.get('action_type')} on target '{act.get('target')}'.")
    if state.get("verification_result"):
        ver = state["verification_result"]
        notes.append(f"PREVIOUS VERIFICATION RESULT: {ver.get('summary')} (System remained unhealthy).")
    if state.get("human_feedback"):
        notes.append(f"HUMAN OPERATOR FEEDBACK: {state['human_feedback']}")
    if state.get("previous_rca"):
        prca = state["previous_rca"]
        notes.append(f"PREVIOUS RCA HYPOTHESIS: {prca.get('probable_cause')} (Category: {prca.get('cause_category')}).")

    if notes:
        return "\n\n━━━ RETRY & VERIFICATION CONTEXT ━━━\n" + "\n".join(notes)
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# AGENT NODES
# Each function is one "node" in the LangGraph workflow.
# It receives the current state, does its job, and returns an updated state.
# ─────────────────────────────────────────────────────────────────────────────

def investigator_a_node(state: IncidentState) -> IncidentState:
    """
    Investigator A: Forms a hypothesis blaming recent code / deployment changes.

    Uses Groq (ultra-fast Llama) as the primary model.
    Falls back to Google Gemini if Groq is unavailable.

    Reads from state : incident_description, deployment_evidence, log_evidence
    Writes to state  : hypothesis_a, agent_logs
    """

    # Build the input data for the prompt
    description = state.get("incident_description", "") + _format_context_note(state)
    prompt_inputs = {
        "description": description,
        "deployments": json.dumps(state.get("deployment_evidence") or []),
        "logs":        json.dumps(state.get("log_evidence")        or []),
    }

    # Get resilient LLM (primary Groq, with NVIDIA and Google fallbacks)
    llm = get_llm(provider="groq")
    response = (INVESTIGATOR_A_PROMPT | llm).invoke(prompt_inputs)

    # Parse the LLM's JSON text response into a Python dict
    hypothesis_a = parse_llm_json(response.content, fallback_type="investigator_a")

    # Return ONLY the keys this node owns — do NOT spread **state.
    # The Annotated reducer on agent_logs safely merges entries from parallel nodes.
    confidence = hypothesis_a.get('confidence', 'Unknown')
    service    = hypothesis_a.get('affected_service', 'Unknown')
    return {
        "hypothesis_a": hypothesis_a,
        "agent_logs":   [f"[Investigator A] Claim: {hypothesis_a.get('claim')} | Confidence: {confidence} | Service: {service}"],
    }


def investigator_b_node(state: IncidentState) -> IncidentState:
    """
    Investigator B: Forms a hypothesis blaming infrastructure / system overload.

    Uses NVIDIA as the primary model, with automatic Groq/Google fallbacks.

    Reads from state : incident_description, metrics_evidence, log_evidence
    Writes to state  : hypothesis_b, agent_logs
    """

    description = state.get("incident_description", "") + _format_context_note(state)
    prompt_inputs = {
        "description": description,
        "metrics":     json.dumps(state.get("metrics_evidence") or {}),
        "logs":        json.dumps(state.get("log_evidence")     or []),
    }

    # Get resilient LLM (primary NVIDIA, with Groq and Google fallbacks)
    llm = get_llm(provider="nvidia")
    response = (INVESTIGATOR_B_PROMPT | llm).invoke(prompt_inputs)

    hypothesis_b = parse_llm_json(response.content, fallback_type="investigator_b")

    # Return ONLY the keys this node owns — do NOT spread **state.
    confidence = hypothesis_b.get('confidence', 'Unknown')
    resource   = hypothesis_b.get('affected_resource', 'Unknown')
    return {
        "hypothesis_b": hypothesis_b,
        "agent_logs":   [f"[Investigator B] Claim: {hypothesis_b.get('claim')} | Confidence: {confidence} | Resource: {resource}"],
    }


def judge_agent_node(state: IncidentState) -> IncidentState:
    """
    Judge Agent: Reads BOTH investigators' hypotheses and picks the real root cause.

    This node only runs AFTER both investigators have finished (fan-in in workflow.py).

    Reads from state : hypothesis_a, hypothesis_b, all evidence fields
    Writes to state  : root_cause_analysis, agent_logs
    """

    # Google Gemini is best suited for the Judge — it excels at long-context
    # reasoning (reading both hypotheses + all evidence in one pass).
    # Falls back to Groq → NVIDIA if Gemini is unavailable.
    llm = get_llm(provider="google")

    description = state.get("incident_description", "") + _format_context_note(state)
    response = (JUDGE_PROMPT | llm).invoke({
        "description":    description,
        "hyp_a":          json.dumps(state.get("hypothesis_a")         or {}),
        "hyp_b":          json.dumps(state.get("hypothesis_b")         or {}),
        "metrics":        json.dumps(state.get("metrics_evidence")     or {}),
        "logs":           json.dumps(state.get("log_evidence")         or []),
        "rag_docs":       json.dumps(state.get("rag_evidence")         or []),
        "past_incidents": json.dumps(state.get("historical_incidents_evidence") or []),
    })

    rca = parse_llm_json(response.content, fallback_type="judge")

    # Promote cause_category to a top-level state field so remediation can read it directly
    cause_category = rca.get("cause_category", "unknown") or "unknown"

    findings_count = len(rca.get("key_findings", []))
    new_log = (
        f"[Judge Agent] Verdict: {rca.get('probable_cause')} "
        f"(Category: {cause_category}, Winner: {rca.get('winning_hypothesis')}, "
        f"Confidence: {rca.get('confidence')}, Findings: {findings_count})"
    )

    return {
        "root_cause_analysis": rca,
        "cause_category":      cause_category,
        "agent_logs":          [new_log],
    }

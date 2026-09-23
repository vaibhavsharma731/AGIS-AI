"""
backend/app/rag/incident_memory.py

Incident Memory Helper:
- Saves resolved incidents as markdown files in `backend/knowledge/previous_incidents/`
- Triggers FAISS vector store refresh so new incidents are indexed immediately for RAG
- Provides fast keyword/token incident search across historical incident reports
"""

import os
import glob
from backend.app.config import settings

# Directory where past incident reports are stored
PAST_INCIDENTS_DIR = os.path.join(settings.KNOWLEDGE_DIR, "previous_incidents")

def save_incident_to_memory(state: dict):
    """
    Saves a resolved incident report to disk as a markdown file,
    and refreshes the FAISS index so the incident enters vector memory immediately.
    """
    os.makedirs(PAST_INCIDENTS_DIR, exist_ok=True)

    incident_id = state.get("incident_id", "INC-UNKNOWN")
    description = state.get("incident_description", "No description provided.")
    
    rca = state.get("root_cause_analysis") or {}
    cause = rca.get("probable_cause", "Unknown Cause")
    reasoning = rca.get("reasoning", "No reasoning provided.")
    
    action = state.get("recommended_action") or {}
    action_type = action.get("action_type", "Unknown Action")
    
    # Create clean markdown text for the incident memory
    content = f"""# Historical Incident: {incident_id}

## Problem Description
{description}

## Root Cause
{cause}

## Explanation
{reasoning}

## Fix Applied
{action_type}

## Result
Resolved and Verified successfully.
"""

    file_path = os.path.join(PAST_INCIDENTS_DIR, f"{incident_id.lower()}.md")
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[Incident Memory] Saved past incident to '{file_path}'.")

        # Refresh FAISS vector index so the new incident is searchable via RAG
        try:
            from backend.app.rag.ingest import build_vector_store
            build_vector_store()
            print("[Incident Memory] FAISS index refreshed with new incident.")
        except Exception as e:
            print(f"[Incident Memory] Notice: Could not refresh FAISS index ({e}).")

    except Exception as e:
        print(f"[Incident Memory] Failed to save incident memory: {e}")

def search_historical_incidents(query: str, top_k: int = 2) -> list[str]:
    """
    Keyword-based Incident Memory Search:
    Performs fast token-matching across resolved incident markdown files in
    `backend/knowledge/previous_incidents/`. This zero-dependency keyword scan
    complements vector search by immediately discovering newly recorded incidents.
    """
    if not os.path.exists(PAST_INCIDENTS_DIR):
        return ["No previous incidents recorded yet in memory database."]

    md_files = glob.glob(os.path.join(PAST_INCIDENTS_DIR, "*.md"))
    if not md_files:
        return ["No previous incident files found in memory store."]

    results = []
    query_words = [w.lower() for w in query.split() if len(w) > 3]

    for filepath in md_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()

            # Check if any key query words appear in this past incident
            matches = sum(1 for word in query_words if word in text.lower())
            if matches > 0:
                filename = os.path.basename(filepath)
                # Return snippet of problem and fix
                snippet = f"[{filename}] " + text.replace("\n", " ")[:300] + "..."
                results.append(snippet)
        except Exception:
            continue

    if not results:
        return ["No matching past incidents found for this problem description."]

    return results[:top_k]

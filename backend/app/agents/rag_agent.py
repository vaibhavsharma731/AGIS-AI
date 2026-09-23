"""
backend/app/agents/rag_agent.py

RAG Knowledge Agent Node: Uses vector search to retrieve relevant operational runbooks.
"""

from backend.app.graph.state import IncidentState
from backend.app.rag.retriever import get_runbook_context

def rag_agent_node(state: IncidentState) -> IncidentState:
    """
    Queries vector store for matching runbooks based on accumulated log/metric evidence.
    """
    # Safely extract only string entries — log_evidence may contain unavailable-payload dicts
    raw_logs = state.get("log_evidence") or []
    log_strings = [entry for entry in raw_logs if isinstance(entry, str)]
    log_summary = " ".join(log_strings)

    query = f"{state.get('incident_description', '')} {log_summary}".strip()
    from backend.app.rag.embeddings import get_embeddings, is_fake_embeddings

    # Fail gracefully with explicit evidence if embeddings are unavailable
    if is_fake_embeddings(get_embeddings()):
        return {
            "rag_evidence": ["Vector embeddings unavailable. Automated RAG retrieval skipped to avoid random matching."],
            "agent_logs": ["[RAG Agent] Embeddings unavailable (FakeEmbeddings fallback active). Gracefully skipping RAG search."]
        }

    #fetching top 2 relatable chunks
    runbook_chunks = get_runbook_context(query, top_k=2)

    new_log = f"[RAG Agent] Retrieved {len(runbook_chunks)} relevant runbook context snippet(s)."

    return {
        "rag_evidence": runbook_chunks,
        "agent_logs": [new_log]
    }

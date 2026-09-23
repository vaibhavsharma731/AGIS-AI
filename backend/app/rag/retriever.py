"""
backend/app/rag/retriever.py

Provides functionality to query the local FAISS runbook vector store for relevant troubleshooting procedures.
"""

import os
from typing import List
from langchain_community.vectorstores import FAISS

from backend.app.config import settings
from backend.app.rag.embeddings import get_embeddings, is_fake_embeddings
from backend.app.rag.ingest import build_vector_store

def get_runbook_context(query: str, top_k: int = 3) -> List[str]:
    """
    Search the FAISS vector index for runbooks related to the query string (e.g., error log or symptom).
    Returns list of relevant runbook text chunks.
    """
    embeddings = get_embeddings()

    if is_fake_embeddings(embeddings):
        return ["Vector embeddings unavailable. Automated RAG retrieval skipped to avoid random matching."]

    # Load FAISS index if present, else build it on the fly
    if os.path.exists(settings.FAISS_INDEX_PATH):
        try:
            vectorstore = FAISS.load_local(
                settings.FAISS_INDEX_PATH,
                embeddings,
                allow_dangerous_deserialization=True
            )
        except Exception as e:
            print(f"[RAG Retriever] Failed loading index ({e}), building fresh index...")
            vectorstore = build_vector_store()
    else:
        print("[RAG Retriever] Index path not found. Building FAISS index...")
        vectorstore = build_vector_store()

    if not vectorstore:
        return ["No runbook knowledge base available."]

    # Perform similarity search
    docs = vectorstore.similarity_search(query, k=top_k)
    return [doc.page_content for doc in docs]

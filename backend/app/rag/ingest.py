"""
backend/app/rag/ingest.py

Loads runbook Markdown documents from `backend/knowledge/`, splits them into text chunks,
generates embeddings, and builds a local FAISS vector store.
"""

import os
import glob
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

from backend.app.config import settings
from backend.app.rag.embeddings import get_embeddings

def build_vector_store():
    """
    Reads markdown runbooks, builds FAISS vector index, and saves to disk.
    """
    runbook_pattern = os.path.join(settings.KNOWLEDGE_DIR, "**", "*.md")
    md_files = glob.glob(runbook_pattern, recursive=True)

    if not md_files:
        print(f"[RAG Ingest] No runbooks found in '{settings.KNOWLEDGE_DIR}'.")
        return None

    documents = []
    for filepath in md_files:
        try:
            loader = TextLoader(filepath, encoding="utf-8")
            docs = loader.load()
            documents.extend(docs)
        except Exception as e:
            print(f"[RAG Ingest] Error loading {filepath}: {e}")

    print(f"[RAG Ingest] Loaded {len(documents)} runbook document(s).")

    # Split documents into readable chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50
    )
    chunks = text_splitter.split_documents(documents)
    print(f"[RAG Ingest] Split into {len(chunks)} text chunk(s).")

    # Generate embeddings & save FAISS index
    embeddings = get_embeddings()
    vectorstore = FAISS.from_documents(chunks, embeddings)

    os.makedirs(os.path.dirname(settings.FAISS_INDEX_PATH), exist_ok=True)
    vectorstore.save_local(settings.FAISS_INDEX_PATH)
    print(f"[RAG Ingest] Saved FAISS index to '{settings.FAISS_INDEX_PATH}'.")
    return vectorstore

if __name__ == "__main__":
    build_vector_store()

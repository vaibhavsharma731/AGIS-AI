"""
backend/app/rag/embeddings.py
Provides embeddings instance for RAG vector index building and retrieval.
"""

import logging

logger = logging.getLogger(__name__)

def get_embeddings():
    """
    Returns embeddings for RAG indexing and retrieval.
    Falls back to FakeEmbeddings (RANDOM vectors) only as an absolute last
    resort — and loudly logs it, since a silent fallback here means every
    RAG similarity search afterward returns meaningless results.
    """
    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    except Exception as e:
        logger.error(
            f"[Embeddings] FAILED to load HuggingFaceEmbeddings ({e}). "
            "Falling back to FakeEmbeddings — RAG similarity search will "
            "return RANDOM, MEANINGLESS results until this is fixed. "
            "Check that 'sentence-transformers' is installed and the model "
            "can be downloaded/loaded."
        )
        from langchain_community.embeddings import FakeEmbeddings
        return FakeEmbeddings(size=384)


def is_fake_embeddings(embeddings) -> bool:
    """
    Checks if the embeddings instance is a FakeEmbeddings fallback.
    """
    if embeddings is None:
        return True
    try:
        from langchain_community.embeddings import FakeEmbeddings
        if isinstance(embeddings, FakeEmbeddings):
            return True
    except Exception:
        pass
    return "fake" in embeddings.__class__.__name__.lower()
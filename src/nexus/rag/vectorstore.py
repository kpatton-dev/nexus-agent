"""ChromaDB vector store for NEXUS knowledge base."""

import logging
import threading
from pathlib import Path
from typing import Optional

import chromadb
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

from nexus.config import CHROMA_PERSIST_DIR, CHROMA_COLLECTION, EMBEDDING_MODEL

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_vectorstore: Optional[Chroma] = None
_chroma_client: Optional[chromadb.PersistentClient] = None
_embeddings: Optional[HuggingFaceEmbeddings] = None


def get_embeddings() -> HuggingFaceEmbeddings:
    """Get or create the embedding function. Local model — no API cost."""
    global _embeddings
    if _embeddings is None:
        logger.info("Loading embedding model: %s", EMBEDDING_MODEL)
        _embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    return _embeddings


def get_vectorstore() -> Chroma:
    """Get or create the persistent ChromaDB vector store.

    Thread-safe: uses a lock and shared PersistentClient to avoid
    ChromaDB's singleton conflict when agents run in parallel.
    """
    global _vectorstore, _chroma_client
    with _lock:
        if _vectorstore is None:
            persist_dir = str(Path(CHROMA_PERSIST_DIR).resolve())
            logger.info("Initializing ChromaDB at %s", persist_dir)
            _chroma_client = chromadb.PersistentClient(path=persist_dir)
            _vectorstore = Chroma(
                client=_chroma_client,
                collection_name=CHROMA_COLLECTION,
                embedding_function=get_embeddings(),
            )
    return _vectorstore


def get_retriever(top_k: int = 8, content_type_filter: Optional[list[str]] = None):
    """Get a retriever with optional content type filtering.

    Args:
        top_k: Number of results to return.
        content_type_filter: Optional list of content types to filter by
            (e.g., ["incident", "conversation"]).
    """
    store = get_vectorstore()
    search_kwargs = {"k": top_k}
    if content_type_filter:
        search_kwargs["filter"] = {
            "$or": [{"content_type": ct} for ct in content_type_filter]
        }
    return store.as_retriever(search_kwargs=search_kwargs)


def get_collection_stats() -> dict:
    """Return basic stats about the vector store."""
    store = get_vectorstore()
    collection = store._collection
    count = collection.count()
    return {
        "total_chunks": count,
        "collection_name": CHROMA_COLLECTION,
        "persist_dir": CHROMA_PERSIST_DIR,
    }

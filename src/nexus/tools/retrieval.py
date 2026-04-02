"""RAG retrieval tools for NEXUS agents."""

import logging
from langchain.tools import tool

from nexus.rag.vectorstore import get_retriever

logger = logging.getLogger(__name__)


@tool(response_format="content_and_artifact")
def search_documentation(query: str) -> tuple[str, list[dict]]:
    """Search internal documentation, runbooks, and procedures.

    Use this to find how-to guides, standard operating procedures,
    system documentation, and process descriptions.
    """
    retriever = get_retriever(
        top_k=8,
        content_type_filter=["documentation", "runbook", "team_info"],
    )
    docs = retriever.invoke(query)
    if not docs:
        return "No relevant documentation found.", []

    sources = []
    text_parts = []
    for doc in docs:
        meta = doc.metadata
        sources.append({
            "title": meta.get("title", "Unknown"),
            "source": meta.get("source", "unknown"),
            "content_type": meta.get("content_type", "documentation"),
            "system_tags": meta.get("system_tags", ""),
        })
        text_parts.append(
            f"[{meta.get('title', 'Unknown')}] ({meta.get('source', 'unknown')})\n{doc.page_content}"
        )

    return "\n\n---\n\n".join(text_parts), sources


@tool(response_format="content_and_artifact")
def search_incidents(query: str) -> tuple[str, list[dict]]:
    """Search incident history, tickets, and conversation logs.

    Use this to find past incidents, their resolutions, patterns in failures,
    and historical ticket data.
    """
    retriever = get_retriever(
        top_k=8,
        content_type_filter=["incident", "conversation"],
    )
    docs = retriever.invoke(query)
    if not docs:
        return "No relevant incident data found.", []

    sources = []
    text_parts = []
    for doc in docs:
        meta = doc.metadata
        sources.append({
            "title": meta.get("title", "Unknown"),
            "source": meta.get("source", "unknown"),
            "content_type": meta.get("content_type", "incident"),
            "ticket_id": meta.get("ticket_id", ""),
        })
        text_parts.append(
            f"[{meta.get('title', 'Unknown')}] (ticket: {meta.get('ticket_id', 'N/A')})\n{doc.page_content}"
        )

    return "\n\n---\n\n".join(text_parts), sources


@tool(response_format="content_and_artifact")
def search_architecture(query: str) -> tuple[str, list[dict]]:
    """Search system architecture, dependency maps, and integration documentation.

    Use this to understand how systems connect, what depends on what,
    and the impact of changes or outages.
    """
    retriever = get_retriever(
        top_k=8,
        content_type_filter=["documentation", "change_log", "team_info"],
    )
    docs = retriever.invoke(query)
    if not docs:
        return "No relevant architecture documentation found.", []

    sources = []
    text_parts = []
    for doc in docs:
        meta = doc.metadata
        sources.append({
            "title": meta.get("title", "Unknown"),
            "source": meta.get("source", "unknown"),
            "content_type": meta.get("content_type", "documentation"),
            "system_tags": meta.get("system_tags", ""),
        })
        text_parts.append(
            f"[{meta.get('title', 'Unknown')}] systems: {meta.get('system_tags', 'N/A')}\n{doc.page_content}"
        )

    return "\n\n---\n\n".join(text_parts), sources


@tool(response_format="content_and_artifact")
def search_all(query: str) -> tuple[str, list[dict]]:
    """Search across ALL knowledge base content — documentation, incidents, architecture.

    Use this for broad queries that may span multiple content types.
    """
    retriever = get_retriever(top_k=10)
    docs = retriever.invoke(query)
    if not docs:
        return "No relevant content found in the knowledge base.", []

    sources = []
    text_parts = []
    for doc in docs:
        meta = doc.metadata
        sources.append({
            "title": meta.get("title", "Unknown"),
            "source": meta.get("source", "unknown"),
            "content_type": meta.get("content_type", "unknown"),
        })
        text_parts.append(
            f"[{meta.get('title', 'Unknown')}] ({meta.get('content_type', 'unknown')})\n{doc.page_content}"
        )

    return "\n\n---\n\n".join(text_parts), sources

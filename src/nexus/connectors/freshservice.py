"""FreshService data connector for NEXUS knowledge base ingestion."""

import logging
import time

import httpx

from nexus.config import FRESHSERVICE_DOMAIN, FRESHSERVICE_API_KEY
from nexus.rag.vectorstore import get_vectorstore
from nexus.rag.chunker import chunk_by_headers, detect_systems

logger = logging.getLogger(__name__)

STATUS_MAP = {2: "Open", 3: "Pending", 4: "Resolved", 5: "Closed"}
PRIORITY_MAP = {1: "Low", 2: "Medium", 3: "High", 4: "Urgent"}


def ingest_freshservice_tickets(max_pages: int = 10) -> int:
    """Fetch tickets from FreshService and ingest into vector store.

    Returns total number of chunks ingested.
    """
    if not FRESHSERVICE_DOMAIN or not FRESHSERVICE_API_KEY:
        raise ValueError("FreshService credentials not configured")

    store = get_vectorstore()
    base_url = f"https://{FRESHSERVICE_DOMAIN}/api/v2"
    total_chunks = 0
    page = 1

    while page <= max_pages:
        resp = httpx.get(
            f"{base_url}/tickets",
            auth=(FRESHSERVICE_API_KEY, "X"),
            params={"per_page": 100, "page": page, "order_by": "updated_at", "order_type": "desc"},
            timeout=30,
        )
        if resp.status_code == 429:
            logger.warning("Rate limited, waiting 3s...")
            time.sleep(3)
            continue
        resp.raise_for_status()

        tickets = resp.json().get("tickets", [])
        if not tickets:
            break

        for ticket in tickets:
            ticket_id = ticket["id"]
            status = STATUS_MAP.get(ticket.get("status"), "Unknown")
            priority = PRIORITY_MAP.get(ticket.get("priority"), "Unknown")
            subject = ticket.get("subject", "No subject")
            description = ticket.get("description_text", "") or ""

            # Fetch conversations (resolution notes, replies)
            conversations_text = _fetch_conversations(base_url, ticket_id)

            doc_text = (
                f"# Ticket #{ticket_id}: {subject}\n\n"
                f"**Status:** {status} | **Priority:** {priority}\n\n"
                f"## Description\n{description}\n\n"
            )
            if conversations_text:
                doc_text += f"## Resolution / Conversations\n{conversations_text}\n"

            metadata = {
                "source": "freshservice",
                "content_type": "incident",
                "title": f"FS-{ticket_id}: {subject}",
                "ticket_id": str(ticket_id),
                "status": status,
                "priority": priority,
            }

            chunks = chunk_by_headers(doc_text, metadata)
            ids = [c["id"] for c in chunks]
            documents = [c["content"] for c in chunks]
            metadatas = [c["metadata"] for c in chunks]

            store.add_texts(texts=documents, metadatas=metadatas, ids=ids)
            total_chunks += len(chunks)

        logger.info("Ingested page %d (%d tickets)", page, len(tickets))
        page += 1

    return total_chunks


def _fetch_conversations(base_url: str, ticket_id: int) -> str:
    """Fetch conversation entries for a ticket."""
    try:
        time.sleep(0.1)  # rate limit courtesy
        resp = httpx.get(
            f"{base_url}/tickets/{ticket_id}/conversations",
            auth=(FRESHSERVICE_API_KEY, "X"),
            timeout=15,
        )
        if resp.status_code != 200:
            return ""

        conversations = resp.json().get("conversations", [])
        parts = []
        for conv in conversations:
            body = conv.get("body_text", "") or ""
            if body.strip():
                parts.append(body.strip())
        return "\n\n".join(parts)

    except Exception as e:
        logger.debug("Could not fetch conversations for ticket %d: %s", ticket_id, e)
        return ""

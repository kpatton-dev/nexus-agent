"""Confluence data connector for NEXUS knowledge base ingestion."""

import logging
import re

import httpx

from nexus.config import CONFLUENCE_URL, CONFLUENCE_USERNAME, CONFLUENCE_API_TOKEN, CONFLUENCE_SPACE_KEY
from nexus.rag.vectorstore import get_vectorstore
from nexus.rag.chunker import chunk_by_headers, guess_content_type

logger = logging.getLogger(__name__)


def ingest_confluence_pages(max_pages: int = 200) -> int:
    """Fetch pages from Confluence and ingest into vector store.

    Returns total number of chunks ingested.
    """
    if not CONFLUENCE_URL or not CONFLUENCE_USERNAME or not CONFLUENCE_API_TOKEN:
        raise ValueError("Confluence credentials not configured")

    store = get_vectorstore()
    total_chunks = 0
    start = 0
    limit = 50

    while start < max_pages:
        resp = httpx.get(
            f"{CONFLUENCE_URL}/rest/api/content",
            auth=(CONFLUENCE_USERNAME, CONFLUENCE_API_TOKEN),
            params={
                "spaceKey": CONFLUENCE_SPACE_KEY,
                "expand": "body.storage,version",
                "limit": limit,
                "start": start,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            break

        for page in results:
            page_id = page["id"]
            title = page.get("title", "Untitled")
            html_body = page.get("body", {}).get("storage", {}).get("value", "")
            text = _html_to_text(html_body)

            if not text.strip():
                continue

            content_type = guess_content_type(title, text)
            metadata = {
                "source": "confluence",
                "content_type": content_type,
                "title": title,
                "page_id": page_id,
            }

            chunks = chunk_by_headers(text, metadata)
            ids = [c["id"] for c in chunks]
            documents = [c["content"] for c in chunks]
            metadatas = [c["metadata"] for c in chunks]

            store.add_texts(texts=documents, metadatas=metadatas, ids=ids)
            total_chunks += len(chunks)

        logger.info("Ingested %d Confluence pages (start=%d)", len(results), start)
        start += limit

        if data.get("size", 0) < limit:
            break

    return total_chunks


def _html_to_text(html: str) -> str:
    """Convert Confluence HTML to plain text."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(separator="\n")
    except ImportError:
        # Fallback: strip tags with regex
        text = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", text).strip()

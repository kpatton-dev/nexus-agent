"""Live FreshService API tools for NEXUS agents."""

import logging
from typing import Optional

import httpx
from langchain.tools import tool

from nexus.config import FRESHSERVICE_DOMAIN, FRESHSERVICE_API_KEY

logger = logging.getLogger(__name__)

STATUS_MAP = {2: "Open", 3: "Pending", 4: "Resolved", 5: "Closed"}
PRIORITY_MAP = {1: "Low", 2: "Medium", 3: "High", 4: "Urgent"}


def _fs_get(endpoint: str, params: Optional[dict] = None) -> dict:
    """Make authenticated GET request to FreshService API."""
    if not FRESHSERVICE_DOMAIN or not FRESHSERVICE_API_KEY:
        raise ValueError("FreshService credentials not configured")

    url = f"https://{FRESHSERVICE_DOMAIN}/api/v2/{endpoint}"
    resp = httpx.get(
        url,
        auth=(FRESHSERVICE_API_KEY, "X"),
        params=params or {},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


@tool
def query_freshservice_tickets(
    search_query: str,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 10,
) -> str:
    """Query FreshService for recent tickets matching a search term.

    Use this to get LIVE ticket data — current open incidents, recent resolutions, etc.
    The search_query searches ticket subjects and descriptions.
    Optional filters: status (Open/Pending/Resolved/Closed), priority (Low/Medium/High/Urgent).
    """
    try:
        # Build filter query
        filter_parts = [f"subject:'{search_query}' OR description:'{search_query}'"]
        if status:
            status_code = next((k for k, v in STATUS_MAP.items() if v.lower() == status.lower()), None)
            if status_code:
                filter_parts.append(f"status:{status_code}")
        if priority:
            priority_code = next((k for k, v in PRIORITY_MAP.items() if v.lower() == priority.lower()), None)
            if priority_code:
                filter_parts.append(f"priority:{priority_code}")

        # Use the tickets endpoint with filter
        params = {"per_page": min(limit, 30), "order_by": "updated_at", "order_type": "desc"}
        data = _fs_get("tickets", params)
        tickets = data.get("tickets", [])

        if not tickets:
            return f"No FreshService tickets found matching '{search_query}'."

        results = []
        for t in tickets[:limit]:
            results.append(
                f"#{t['id']} | {STATUS_MAP.get(t.get('status'), '?')} | "
                f"{PRIORITY_MAP.get(t.get('priority'), '?')} | "
                f"{t.get('subject', 'No subject')}"
            )

        return f"Found {len(results)} tickets:\n" + "\n".join(results)

    except Exception as e:
        logger.error("FreshService query failed: %s", e)
        return f"FreshService query failed: {e}"

"""Jira data connector for NEXUS knowledge base ingestion."""

import logging

import httpx

from nexus.config import JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN, JIRA_PROJECT_KEY
from nexus.rag.vectorstore import get_vectorstore
from nexus.rag.chunker import chunk_by_headers

logger = logging.getLogger(__name__)

ISSUE_TYPE_TO_CONTENT = {
    "Bug": "incident",
    "Incident": "incident",
    "Problem": "incident",
    "Epic": "change_log",
    "Story": "documentation",
    "Task": "documentation",
}


def ingest_jira_issues(max_pages: int = 10) -> int:
    """Fetch issues from Jira and ingest into vector store.

    Uses the new POST /search/jql endpoint with token-based pagination.
    Returns total number of chunks ingested.
    """
    if not JIRA_URL or not JIRA_USERNAME or not JIRA_API_TOKEN:
        raise ValueError("Jira credentials not configured")

    store = get_vectorstore()
    total_chunks = 0
    total_issues = 0
    page_size = 50
    next_page_token = None

    jql = f'project = "{JIRA_PROJECT_KEY}" ORDER BY updated DESC'

    for page in range(max_pages):
        body = {
            "jql": jql,
            "maxResults": page_size,
            "fields": ["summary", "status", "priority", "issuetype", "description", "comment", "updated"],
        }
        if next_page_token:
            body["nextPageToken"] = next_page_token

        resp = httpx.post(
            f"{JIRA_URL}/rest/api/2/search/jql",
            auth=(JIRA_USERNAME, JIRA_API_TOKEN),
            json=body,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        issues = data.get("issues", [])
        if not issues:
            break

        for issue in issues:
            key = issue["key"]
            fields = issue["fields"]
            summary = fields.get("summary", "No summary")
            status = fields.get("status", {}).get("name", "Unknown")
            priority = fields.get("priority", {}).get("name", "Unknown")
            issue_type = fields.get("issuetype", {}).get("name", "Task")

            description = _extract_adf_text(fields.get("description")) if fields.get("description") else ""

            comments_text = ""
            comments_data = fields.get("comment", {}).get("comments", [])
            for comment in comments_data:
                body_text = _extract_adf_text(comment.get("body"))
                if body_text:
                    comments_text += f"\n\n{body_text}"

            doc_text = (
                f"# {key}: {summary}\n\n"
                f"**Type:** {issue_type} | **Status:** {status} | **Priority:** {priority}\n\n"
                f"## Description\n{description}\n"
            )
            if comments_text:
                doc_text += f"\n## Comments{comments_text}\n"

            content_type = ISSUE_TYPE_TO_CONTENT.get(issue_type, "documentation")
            metadata = {
                "source": "jira",
                "content_type": content_type,
                "title": f"{key}: {summary}",
                "issue_key": key,
                "status": status,
                "priority": priority,
            }

            chunks = chunk_by_headers(doc_text, metadata)
            ids = [c["id"] for c in chunks]
            documents = [c["content"] for c in chunks]
            metadatas = [c["metadata"] for c in chunks]

            store.add_texts(texts=documents, metadatas=metadatas, ids=ids)
            total_chunks += len(chunks)

        total_issues += len(issues)
        logger.info("Ingested %d Jira issues (page %d, total %d)", len(issues), page + 1, total_issues)

        # Token-based pagination
        if data.get("isLast", True):
            break
        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break

    return total_chunks


def _extract_adf_text(node) -> str:
    """Recursively extract plain text from Atlassian Document Format."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")
        children = node.get("content", [])
        return " ".join(_extract_adf_text(child) for child in children)
    if isinstance(node, list):
        return " ".join(_extract_adf_text(item) for item in node)
    return ""

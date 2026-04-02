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


def ingest_jira_issues(max_results: int = 500) -> int:
    """Fetch issues from Jira and ingest into vector store.

    Returns total number of chunks ingested.
    """
    if not JIRA_URL or not JIRA_USERNAME or not JIRA_API_TOKEN:
        raise ValueError("Jira credentials not configured")

    store = get_vectorstore()
    total_chunks = 0
    start = 0
    page_size = 50

    jql = f'project = "{JIRA_PROJECT_KEY}" ORDER BY updated DESC'

    while start < max_results:
        resp = httpx.get(
            f"{JIRA_URL}/rest/api/3/search",
            auth=(JIRA_USERNAME, JIRA_API_TOKEN),
            params={
                "jql": jql,
                "maxResults": page_size,
                "startAt": start,
                "fields": "summary,status,priority,issuetype,description,comment,updated",
            },
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

            # Extract description text from ADF or plain text
            description = _extract_adf_text(fields.get("description")) if fields.get("description") else ""

            # Extract comments
            comments_text = ""
            comments_data = fields.get("comment", {}).get("comments", [])
            for comment in comments_data:
                body = _extract_adf_text(comment.get("body"))
                if body:
                    comments_text += f"\n\n{body}"

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

        logger.info("Ingested %d Jira issues (start=%d)", len(issues), start)
        start += page_size

        if len(issues) < page_size:
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

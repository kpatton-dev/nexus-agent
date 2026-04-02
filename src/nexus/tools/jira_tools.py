"""Live Jira API tools for NEXUS agents."""

import logging
from typing import Optional

import httpx
from langchain.tools import tool

from nexus.config import JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN, JIRA_PROJECT_KEY

logger = logging.getLogger(__name__)


def _jira_search(jql: str, fields: list[str], max_results: int = 10) -> dict:
    """Search Jira issues using the new POST /search/jql endpoint."""
    if not JIRA_URL or not JIRA_USERNAME or not JIRA_API_TOKEN:
        raise ValueError("Jira credentials not configured")

    url = f"{JIRA_URL}/rest/api/2/search/jql"
    resp = httpx.post(
        url,
        auth=(JIRA_USERNAME, JIRA_API_TOKEN),
        json={"jql": jql, "maxResults": max_results, "fields": fields},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


@tool
def query_jira_issues(
    search_text: str,
    issue_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 10,
) -> str:
    """Search Jira issues by text, optionally filtered by type and status.

    Use this to find LIVE Jira issues — bugs, incidents, epics, tasks.
    search_text: keywords to search in summary and description.
    issue_type: optional filter (Bug, Incident, Task, Epic, Story).
    status: optional filter (Open, In Progress, Done, etc.).
    """
    try:
        jql_parts = [f'project = "{JIRA_PROJECT_KEY}"', f'text ~ "{search_text}"']
        if issue_type:
            jql_parts.append(f'issuetype = "{issue_type}"')
        if status:
            jql_parts.append(f'status = "{status}"')

        jql = " AND ".join(jql_parts) + " ORDER BY updated DESC"
        data = _jira_search(jql, ["summary", "status", "priority", "issuetype", "updated"], min(limit, 50))
        issues = data.get("issues", [])

        if not issues:
            return f"No Jira issues found matching '{search_text}'."

        results = []
        for issue in issues:
            fields = issue["fields"]
            results.append(
                f"{issue['key']} | {fields.get('issuetype', {}).get('name', '?')} | "
                f"{fields.get('status', {}).get('name', '?')} | "
                f"{fields.get('priority', {}).get('name', '?')} | "
                f"{fields.get('summary', 'No summary')}"
            )

        return f"Found {len(results)} issues:\n" + "\n".join(results)

    except Exception as e:
        logger.error("Jira query failed: %s", e)
        return f"Jira query failed: {e}"

"""Analyst agent — incident pattern analysis and root cause identification."""

from langchain_anthropic import ChatAnthropic
from langchain.agents import create_agent as create_react_agent

from nexus.config import CLAUDE_MODEL
from nexus.prompts import ANALYST_PROMPT
from nexus.tools.retrieval import search_incidents, search_all
from nexus.tools.freshservice import query_freshservice_tickets
from nexus.tools.jira_tools import query_jira_issues

analyst_agent = create_react_agent(
    model=ChatAnthropic(model=CLAUDE_MODEL),
    tools=[search_incidents, search_all, query_freshservice_tickets, query_jira_issues],
    name="analyst",
    system_prompt=ANALYST_PROMPT,
)

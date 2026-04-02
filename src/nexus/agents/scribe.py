"""Scribe agent — runbook and documentation generation."""

from langchain_anthropic import ChatAnthropic
from langchain.agents import create_agent as create_react_agent

from nexus.config import CLAUDE_MODEL
from nexus.prompts import SCRIBE_PROMPT
from nexus.tools.retrieval import search_documentation, search_incidents, search_all

scribe_agent = create_react_agent(
    model=ChatAnthropic(model=CLAUDE_MODEL),
    tools=[search_documentation, search_incidents, search_all],
    name="scribe",
    system_prompt=SCRIBE_PROMPT,
)

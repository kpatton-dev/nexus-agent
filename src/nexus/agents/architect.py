"""Architect agent — system dependency mapping and blast radius analysis."""

from langchain_anthropic import ChatAnthropic
from langchain.agents import create_agent as create_react_agent

from nexus.config import CLAUDE_MODEL
from nexus.prompts import ARCHITECT_PROMPT
from nexus.tools.retrieval import search_architecture, search_all

architect_agent = create_react_agent(
    model=ChatAnthropic(model=CLAUDE_MODEL),
    tools=[search_architecture, search_all],
    name="architect",
    system_prompt=ARCHITECT_PROMPT,
)

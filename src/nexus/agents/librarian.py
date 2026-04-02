"""Librarian agent — documentation retrieval and synthesis."""

from langchain_anthropic import ChatAnthropic
from langchain.agents import create_agent as create_react_agent

from nexus.config import CLAUDE_MODEL
from nexus.prompts import LIBRARIAN_PROMPT
from nexus.tools.retrieval import search_documentation, search_all

librarian_agent = create_react_agent(
    model=ChatAnthropic(model=CLAUDE_MODEL),
    tools=[search_documentation, search_all],
    name="librarian",
    system_prompt=LIBRARIAN_PROMPT,
)

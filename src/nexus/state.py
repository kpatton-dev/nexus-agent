"""State definitions for the NEXUS agent graph."""

from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages


class NexusState(TypedDict, total=False):
    """Shared state across all agents in the graph."""

    # Core conversation
    messages: Annotated[list, add_messages]

    # Orchestration metadata
    routed_agents: list[str]  # which agents were selected
    routing_reasoning: str  # why those agents were chosen

    # RAG context — populated by retrieval tools
    retrieved_docs: list[dict]  # [{content, source, content_type, title, score}]

    # Agent outputs — each agent writes its findings here
    librarian_findings: str
    analyst_findings: str
    architect_findings: str
    scribe_output: str

    # Synthesis
    final_answer: str
    sources: list[dict]
    confidence: str  # high / medium / low

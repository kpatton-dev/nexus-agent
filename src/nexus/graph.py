"""NEXUS multi-agent graph — supervisor orchestration pattern.

Architecture:
    User Query → Supervisor (Claude Haiku) → routes to 1+ specialist agents
    Each specialist agent (Claude Sonnet) has its own tools and expertise.
    Supervisor synthesizes final response from agent outputs.

Agents:
    - librarian: Documentation retrieval and synthesis
    - analyst: Incident pattern analysis + live ticket queries
    - architect: System dependency mapping and blast radius
    - scribe: Runbook and documentation generation
"""

import logging

from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import MemorySaver
from langgraph_supervisor import create_supervisor

from nexus.config import CLAUDE_FAST_MODEL
from nexus.prompts import ORCHESTRATOR_PROMPT
from nexus.agents import librarian_agent, analyst_agent, architect_agent, scribe_agent

logger = logging.getLogger(__name__)

# Build the supervisor graph
# Haiku routes (fast + cheap), specialist agents use Sonnet (quality)
workflow = create_supervisor(
    agents=[librarian_agent, analyst_agent, architect_agent, scribe_agent],
    model=ChatAnthropic(model=CLAUDE_FAST_MODEL),
    prompt=ORCHESTRATOR_PROMPT,
    output_mode="full_history",
)

# Compile with in-memory checkpointer for conversation persistence
# Swap to PostgresSaver for production deployment
graph = workflow.compile(checkpointer=MemorySaver())


def query(user_message: str, thread_id: str = "default") -> dict:
    """Run a query through the NEXUS graph.

    Args:
        user_message: The user's question.
        thread_id: Conversation thread ID for memory persistence.

    Returns:
        Full state dict with messages. The last substantive AI message
        contains the agent's analysis.
    """
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(
        {"messages": [{"role": "user", "content": user_message}]},
        config=config,
    )
    # The supervisor may return an empty final message after receiving
    # the agent's transfer-back. Find the last substantive AI response.
    result["answer"] = _extract_answer(result.get("messages", []))
    return result


def _extract_answer(messages: list) -> str:
    """Walk messages backwards to find the last substantive AI response.

    Skips short transfer/handoff messages from the supervisor pattern.
    """
    from langchain_core.messages import AIMessage

    skip_patterns = {"transferring back to supervisor", "transferring to", "successfully transferred"}

    for msg in reversed(messages):
        if not isinstance(msg, AIMessage):
            continue
        content = msg.content
        # Handle string content
        if isinstance(content, str):
            if content.strip() and not any(p in content.lower() for p in skip_patterns):
                if len(content.strip()) > 50:  # skip short routing messages
                    return content.strip()
        # Handle list-of-blocks content
        if isinstance(content, list):
            text_parts = [
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            combined = "\n".join(t for t in text_parts if t.strip())
            if combined.strip() and len(combined.strip()) > 50:
                return combined.strip()
    return "No answer generated."


def stream_query(user_message: str, thread_id: str = "default"):
    """Stream a query through the NEXUS graph, yielding events as they happen.

    Yields tuples of (event_type, data) for real-time UI updates.
    """
    config = {"configurable": {"thread_id": thread_id}}
    for event in graph.stream(
        {"messages": [{"role": "user", "content": user_message}]},
        config=config,
        stream_mode="updates",
    ):
        for node_name, node_output in event.items():
            yield node_name, node_output

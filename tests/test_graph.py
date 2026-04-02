"""Smoke tests for the NEXUS graph."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_graph_compiles():
    """Verify the graph compiles without errors."""
    from nexus.graph import graph
    assert graph is not None


def test_graph_has_agents():
    """Verify all four agents are registered in the graph."""
    from nexus.graph import graph
    node_names = set(graph.get_graph().nodes.keys())
    assert "librarian" in node_names
    assert "analyst" in node_names
    assert "architect" in node_names
    assert "scribe" in node_names


def test_state_schema():
    """Verify state schema has expected fields."""
    from nexus.state import NexusState
    fields = NexusState.__annotations__
    assert "messages" in fields
    assert "retrieved_docs" in fields
    assert "confidence" in fields

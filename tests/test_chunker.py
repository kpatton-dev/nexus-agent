"""Tests for the document chunker."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nexus.rag.chunker import chunk_by_headers, detect_systems, guess_content_type


def test_chunk_by_headers_splits():
    # Sections need enough content to exceed MIN_CHUNK_TOKENS to avoid merging
    long_content = "This is substantial content. " * 30
    text = f"# Section One\n{long_content}\n\n# Section Two\n{long_content}"
    chunks = chunk_by_headers(text)
    assert len(chunks) == 2
    assert "Section One" in chunks[0]["content"]
    assert "Section Two" in chunks[1]["content"]


def test_chunk_no_headers():
    text = "Just some plain text without any headers."
    chunks = chunk_by_headers(text)
    assert len(chunks) == 1


def test_detect_systems():
    text = "The Salesforce to NetSuite integration via Workato failed."
    systems = detect_systems(text)
    assert "Salesforce" in systems
    assert "NetSuite" in systems
    assert "Workato" in systems


def test_guess_content_type():
    assert guess_content_type("incident-report.md", "outage at 3am") == "incident"
    assert guess_content_type("runbook.md", "steps to resolve") == "runbook"
    assert guess_content_type("readme.md", "general information") == "documentation"


def test_chunk_ids_are_deterministic():
    text = "# Test\nContent here."
    meta = {"source": "manual", "title": "test"}
    chunks_a = chunk_by_headers(text, meta)
    chunks_b = chunk_by_headers(text, meta)
    assert chunks_a[0]["id"] == chunks_b[0]["id"]

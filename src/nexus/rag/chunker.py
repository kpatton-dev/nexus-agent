"""Document chunking for NEXUS knowledge base ingestion."""

import hashlib
import logging
import re
from pathlib import Path
from typing import Optional

from nexus.config import KNOWN_SYSTEMS

logger = logging.getLogger(__name__)

MAX_CHUNK_TOKENS = 800  # ~3200 chars
MIN_CHUNK_TOKENS = 100  # ~400 chars
CHARS_PER_TOKEN = 4  # rough estimate


def chunk_by_headers(text: str, metadata: Optional[dict] = None) -> list[dict]:
    """Split text on markdown headers (# ## ###), preserving context.

    Returns list of {content, metadata} dicts ready for vector store upsert.
    """
    metadata = metadata or {}
    sections = re.split(r"(?m)^(#{1,3}\s.+)$", text)

    chunks = []
    current_header = ""
    current_content = ""

    for section in sections:
        if re.match(r"^#{1,3}\s", section):
            # Save previous chunk if it has content
            if current_content.strip():
                chunks.append((current_header, current_content.strip()))
            current_header = section.strip()
            current_content = ""
        else:
            current_content += section

    # Don't forget the last section
    if current_content.strip():
        chunks.append((current_header, current_content.strip()))

    # If no headers found, treat entire text as one chunk
    if not chunks:
        chunks = [("", text.strip())]

    # Merge small chunks with previous
    merged = []
    for header, content in chunks:
        full_text = f"{header}\n{content}" if header else content
        token_estimate = len(full_text) / CHARS_PER_TOKEN

        if merged and token_estimate < MIN_CHUNK_TOKENS:
            prev_header, prev_content = merged[-1]
            merged[-1] = (prev_header, f"{prev_content}\n\n{full_text}")
        else:
            merged.append((header, content))

    # Build final chunk dicts with metadata
    results = []
    for i, (header, content) in enumerate(merged):
        full_text = f"{header}\n{content}" if header else content
        chunk_id = _generate_chunk_id(metadata.get("source", "unknown"), metadata.get("title", ""), i)
        system_tags = detect_systems(full_text)

        results.append({
            "id": chunk_id,
            "content": full_text,
            "metadata": {
                **metadata,
                "chunk_index": i,
                "total_chunks": len(merged),
                "section_header": header,
                "system_tags": ", ".join(system_tags),
            },
        })

    return results


def detect_systems(text: str) -> list[str]:
    """Detect known enterprise system names in text."""
    text_lower = text.lower()
    return [sys for sys in KNOWN_SYSTEMS if sys.lower() in text_lower]


def guess_content_type(filename: str, text: str) -> str:
    """Guess content type from filename and content keywords."""
    combined = f"{filename} {text[:500]}".lower()

    if any(kw in combined for kw in ["runbook", "procedure", "how to", "how-to", "steps to"]):
        return "runbook"
    if any(kw in combined for kw in ["incident", "outage", "downtime", "postmortem", "post-mortem"]):
        return "incident"
    if any(kw in combined for kw in ["change", "release", "deploy", "migration", "upgrade"]):
        return "change_log"
    if any(kw in combined for kw in ["team", "directory", "contact", "escalat", "oncall", "on-call"]):
        return "team_info"
    return "documentation"


def _generate_chunk_id(source: str, title: str, chunk_index: int) -> str:
    """Generate deterministic chunk ID for idempotent upserts."""
    raw = f"{source}::{title}::{chunk_index}"
    return hashlib.md5(raw.encode()).hexdigest()


def parse_file(filepath: Path) -> tuple[str, dict]:
    """Parse a file into text + metadata based on extension.

    Returns (text, metadata) tuple.
    """
    suffix = filepath.suffix.lower()
    metadata = {"title": filepath.stem, "source": "manual", "file_path": str(filepath)}

    if suffix in (".md", ".txt"):
        text = filepath.read_text(encoding="utf-8", errors="replace")
        # Extract YAML frontmatter if present
        fm_match = re.match(r"^---\n(.+?)\n---\n(.*)$", text, re.DOTALL)
        if fm_match:
            for line in fm_match.group(1).split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    metadata[key.strip()] = val.strip()
            text = fm_match.group(2)
        return text, metadata

    if suffix == ".pdf":
        try:
            import fitz  # pymupdf
            doc = fitz.open(str(filepath))
            text = "\n\n".join(page.get_text() for page in doc)
            doc.close()
            return text, metadata
        except ImportError:
            logger.warning("pymupdf not installed — skipping %s", filepath.name)
            return "", metadata

    if suffix == ".docx":
        try:
            from docx import Document
            doc = Document(str(filepath))
            text = "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
            return text, metadata
        except ImportError:
            logger.warning("python-docx not installed — skipping %s", filepath.name)
            return "", metadata

    if suffix in (".xlsx", ".csv"):
        try:
            import pandas as pd
            if suffix == ".csv":
                df = pd.read_csv(filepath)
            else:
                df = pd.read_excel(filepath)
            text = df.to_markdown(index=False)
            return text, metadata
        except ImportError:
            logger.warning("pandas not installed — skipping %s", filepath.name)
            return "", metadata

    # Fallback: try reading as text
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
        return text, metadata
    except Exception as e:
        logger.warning("Could not parse %s: %s", filepath.name, e)
        return "", metadata

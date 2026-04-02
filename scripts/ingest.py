"""Data ingestion CLI for NEXUS knowledge base.

Usage:
    python scripts/ingest.py manual              # Ingest local knowledge base files
    python scripts/ingest.py freshservice         # Ingest FreshService tickets
    python scripts/ingest.py jira                 # Ingest Jira issues
    python scripts/ingest.py confluence           # Ingest Confluence pages
    python scripts/ingest.py all                  # Ingest everything
    python scripts/ingest.py stats                # Show vector store stats
"""

import logging
import sys
from pathlib import Path

# Add src to path so we can import nexus
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import typer
from rich.console import Console
from rich.progress import Progress

from nexus.config import KNOWLEDGE_BASE_DIR
from nexus.rag.vectorstore import get_vectorstore, get_collection_stats
from nexus.rag.chunker import chunk_by_headers, guess_content_type, parse_file

app = typer.Typer(help="NEXUS Knowledge Base Ingestion")
console = Console()

logger = logging.getLogger("nexus.ingest")
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")


@app.command()
def manual():
    """Ingest local knowledge base files (markdown, docx, pdf, xlsx, etc.)."""
    kb_path = Path(KNOWLEDGE_BASE_DIR)
    if not kb_path.exists():
        console.print(f"[red]Knowledge base directory not found: {kb_path}[/red]")
        console.print("Create the directory and add files, or set KNOWLEDGE_BASE_DIR env var.")
        raise typer.Exit(1)

    extensions = {".md", ".txt", ".pdf", ".docx", ".xlsx", ".csv", ".pptx", ".rtf"}
    files = [f for f in kb_path.rglob("*") if f.suffix.lower() in extensions and not f.name.startswith(".")]

    if not files:
        console.print(f"[yellow]No supported files found in {kb_path}[/yellow]")
        raise typer.Exit(0)

    console.print(f"Found [bold]{len(files)}[/bold] files to ingest")
    store = get_vectorstore()
    total_chunks = 0

    with Progress() as progress:
        task = progress.add_task("Ingesting files...", total=len(files))
        for filepath in files:
            text, metadata = parse_file(filepath)
            if not text.strip():
                logger.warning("Empty file, skipping: %s", filepath.name)
                progress.advance(task)
                continue

            metadata["content_type"] = guess_content_type(filepath.name, text)
            chunks = chunk_by_headers(text, metadata)

            ids = [c["id"] for c in chunks]
            documents = [c["content"] for c in chunks]
            metadatas = [c["metadata"] for c in chunks]

            store.add_texts(texts=documents, metadatas=metadatas, ids=ids)
            total_chunks += len(chunks)
            logger.info("Ingested %s → %d chunks", filepath.name, len(chunks))
            progress.advance(task)

    console.print(f"\n[green]Done![/green] Ingested {total_chunks} chunks from {len(files)} files")


@app.command()
def freshservice():
    """Ingest tickets from FreshService API."""
    from nexus.connectors.freshservice import ingest_freshservice_tickets
    count = ingest_freshservice_tickets()
    console.print(f"[green]Done![/green] Ingested {count} ticket chunks from FreshService")


@app.command()
def jira():
    """Ingest issues from Jira API."""
    from nexus.connectors.jira_connector import ingest_jira_issues
    count = ingest_jira_issues()
    console.print(f"[green]Done![/green] Ingested {count} issue chunks from Jira")


@app.command()
def confluence():
    """Ingest pages from Confluence API."""
    from nexus.connectors.confluence import ingest_confluence_pages
    count = ingest_confluence_pages()
    console.print(f"[green]Done![/green] Ingested {count} page chunks from Confluence")


@app.command(name="all")
def ingest_all():
    """Ingest from all sources."""
    console.print("[bold]Ingesting from all sources...[/bold]\n")
    manual()
    try:
        freshservice()
    except Exception as e:
        console.print(f"[yellow]FreshService skipped: {e}[/yellow]")
    try:
        jira()
    except Exception as e:
        console.print(f"[yellow]Jira skipped: {e}[/yellow]")
    try:
        confluence()
    except Exception as e:
        console.print(f"[yellow]Confluence skipped: {e}[/yellow]")
    console.print("\n[green bold]All sources ingested.[/green bold]")


@app.command()
def stats():
    """Show vector store statistics."""
    info = get_collection_stats()
    console.print(f"Collection: [bold]{info['collection_name']}[/bold]")
    console.print(f"Total chunks: [bold]{info['total_chunks']}[/bold]")
    console.print(f"Persist dir: {info['persist_dir']}")


if __name__ == "__main__":
    app()

"""Interactive chat CLI for NEXUS.

Usage:
    python scripts/chat.py
    python scripts/chat.py --stream          # Stream agent events in real-time
    python scripts/chat.py --thread mythread # Named conversation thread
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from nexus.graph import query, stream_query

app = typer.Typer()
console = Console()


@app.command()
def chat(
    stream: bool = typer.Option(False, help="Stream agent events in real-time"),
    thread: str = typer.Option("default", help="Conversation thread ID"),
):
    """Interactive chat with NEXUS multi-agent system."""
    console.print(Panel.fit(
        "[bold]NEXUS[/bold] — Multi-Agent IT Operations Intelligence\n"
        "Powered by LangGraph + Claude\n\n"
        "Agents: Librarian | Analyst | Architect | Scribe\n"
        "Type 'quit' or 'exit' to leave.",
        border_style="blue",
    ))

    while True:
        try:
            user_input = console.input("\n[bold blue]You:[/bold blue] ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input or user_input.lower() in ("quit", "exit", "q"):
            console.print("[dim]Goodbye.[/dim]")
            break

        if stream:
            console.print("\n[bold green]NEXUS:[/bold green]")
            for node_name, output in stream_query(user_input, thread_id=thread):
                if node_name == "supervisor":
                    continue  # don't print routing internals
                messages = output.get("messages", [])
                for msg in messages:
                    content = msg.content if hasattr(msg, "content") else str(msg)
                    if content.strip():
                        console.print(f"  [dim]{node_name}:[/dim]")
                        console.print(Markdown(content))
        else:
            with console.status("[bold blue]NEXUS is thinking...[/bold blue]"):
                result = query(user_input, thread_id=thread)

            messages = result.get("messages", [])
            if messages:
                final = messages[-1]
                content = final.content if hasattr(final, "content") else str(final)
                console.print("\n[bold green]NEXUS:[/bold green]")
                console.print(Markdown(content))


if __name__ == "__main__":
    app()

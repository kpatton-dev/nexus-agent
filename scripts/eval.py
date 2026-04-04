"""NEXUS Evaluation Pipeline

Runs a suite of test questions against the agent graph and scores
answers for relevance, accuracy, and source quality.

Usage:
    python scripts/eval.py                    # Run full eval suite
    python scripts/eval.py --quick            # Run 5 quick questions only
    python scripts/eval.py --export results   # Export results to JSON
"""

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from langchain_anthropic import ChatAnthropic

from nexus.graph import query, _extract_answer
from nexus.config import CLAUDE_FAST_MODEL

app = typer.Typer(help="NEXUS Evaluation Pipeline")
console = Console()

logger = logging.getLogger("nexus.eval")
logging.basicConfig(level=logging.WARNING)

# ---------------------------------------------------------------------------
# Eval dataset — questions with expected content and metadata
# ---------------------------------------------------------------------------
EVAL_QUESTIONS = [
    {
        "id": "arch-01",
        "question": "What systems are affected if UKG goes down?",
        "expected_keywords": ["netsuite", "five9", "coupa", "okta", "workato"],
        "expected_agent": "architect",
        "category": "blast_radius",
        "difficulty": "medium",
    },
    {
        "id": "lib-01",
        "question": "What's the process for Coupa-to-NetSuite PO reconciliation?",
        "expected_keywords": ["coupa", "netsuite", "purchase order", "reconcil"],
        "expected_agent": "librarian",
        "category": "documentation",
        "difficulty": "easy",
    },
    {
        "id": "analyst-01",
        "question": "What are the most common types of FreshService tickets?",
        "expected_keywords": ["ticket", "incident", "request", "freshservice"],
        "expected_agent": "analyst",
        "category": "incident_analysis",
        "difficulty": "medium",
    },
    {
        "id": "arch-02",
        "question": "What integrations does Salesforce have with other systems?",
        "expected_keywords": ["salesforce", "netsuite", "workato", "integration"],
        "expected_agent": "architect",
        "category": "dependency_map",
        "difficulty": "medium",
    },
    {
        "id": "lib-02",
        "question": "How do I connect to VPN using GlobalProtect?",
        "expected_keywords": ["vpn", "globalprotect", "okta"],
        "expected_agent": "librarian",
        "category": "documentation",
        "difficulty": "easy",
    },
    {
        "id": "scribe-01",
        "question": "Create a runbook for handling Salesforce-NetSuite sync failures",
        "expected_keywords": ["runbook", "salesforce", "netsuite", "sync", "step"],
        "expected_agent": "scribe",
        "category": "runbook_gen",
        "difficulty": "hard",
    },
    {
        "id": "arch-03",
        "question": "Who owns the Workato integration recipes?",
        "expected_keywords": ["workato", "owner", "recipe"],
        "expected_agent": "architect",
        "category": "ownership",
        "difficulty": "easy",
    },
    {
        "id": "analyst-02",
        "question": "What Coupa supplier issues have been reported?",
        "expected_keywords": ["coupa", "supplier", "issue", "incident"],
        "expected_agent": "analyst",
        "category": "incident_analysis",
        "difficulty": "medium",
    },
    {
        "id": "lib-03",
        "question": "What is the Expensify expense report workflow?",
        "expected_keywords": ["expensify", "expense", "report"],
        "expected_agent": "librarian",
        "category": "documentation",
        "difficulty": "medium",
    },
    {
        "id": "arch-04",
        "question": "What happens if Workato goes down? What integrations break?",
        "expected_keywords": ["workato", "integration", "recipe", "break", "impact"],
        "expected_agent": "architect",
        "category": "blast_radius",
        "difficulty": "hard",
    },
    {
        "id": "analyst-03",
        "question": "Are there any patterns in Okta-related incidents?",
        "expected_keywords": ["okta", "incident", "pattern"],
        "expected_agent": "analyst",
        "category": "incident_analysis",
        "difficulty": "hard",
    },
    {
        "id": "lib-04",
        "question": "How do I report an issue in FreshService?",
        "expected_keywords": ["freshservice", "report", "issue", "ticket"],
        "expected_agent": "librarian",
        "category": "documentation",
        "difficulty": "easy",
    },
    {
        "id": "arch-05",
        "question": "What is the system dependency map for Five9 IT?",
        "expected_keywords": ["dependency", "system", "map", "integration"],
        "expected_agent": "architect",
        "category": "dependency_map",
        "difficulty": "medium",
    },
    {
        "id": "scribe-02",
        "question": "Generate documentation for the UKG API integration patterns",
        "expected_keywords": ["ukg", "api", "integration", "documentation"],
        "expected_agent": "scribe",
        "category": "runbook_gen",
        "difficulty": "hard",
    },
    {
        "id": "analyst-04",
        "question": "What Jira issues are related to the CCC project?",
        "expected_keywords": ["jira", "ccc", "issue"],
        "expected_agent": "analyst",
        "category": "incident_analysis",
        "difficulty": "easy",
    },
]


def score_keyword_coverage(answer: str, expected_keywords: list[str]) -> float:
    """Score 0-1 based on how many expected keywords appear in the answer."""
    if not answer or answer == "No answer generated.":
        return 0.0
    answer_lower = answer.lower()
    hits = sum(1 for kw in expected_keywords if kw.lower() in answer_lower)
    return hits / len(expected_keywords) if expected_keywords else 0.0


def score_answer_quality(answer: str) -> float:
    """Score 0-1 based on answer structure and substance."""
    if not answer or answer == "No answer generated.":
        return 0.0

    score = 0.0
    # Has meaningful length
    if len(answer) > 200:
        score += 0.3
    elif len(answer) > 50:
        score += 0.15

    # Has structure (headers, lists, tables)
    if "#" in answer:
        score += 0.2
    if "- " in answer or "* " in answer or "1." in answer:
        score += 0.15
    if "|" in answer:  # tables
        score += 0.1

    # Has citations / source references
    if any(kw in answer.lower() for kw in ["source:", "according to", "based on", "[", "citation"]):
        score += 0.15

    # Doesn't hedge excessively
    hedge_count = sum(1 for h in ["i'm not sure", "i don't have", "insufficient", "no relevant"]
                      if h in answer.lower())
    score -= hedge_count * 0.15

    return max(0.0, min(1.0, score))


def score_with_llm(question: str, answer: str, expected_keywords: list[str]) -> dict:
    """Use Claude Haiku as a judge to score answer quality."""
    try:
        llm = ChatAnthropic(model=CLAUDE_FAST_MODEL)
        prompt = f"""Score this answer on a scale of 1-5 for each criterion.
Return ONLY a JSON object with scores, nothing else.

Question: {question}
Expected topics: {', '.join(expected_keywords)}

Answer to evaluate:
{answer[:2000]}

Score these criteria (1=poor, 5=excellent):
- relevance: Does the answer address the question?
- accuracy: Is the information factual and well-sourced?
- completeness: Does it cover the expected topics?
- actionability: Could someone act on this information?

Return format: {{"relevance": N, "accuracy": N, "completeness": N, "actionability": N}}"""

        result = llm.invoke(prompt)
        scores = json.loads(result.content)
        return scores
    except Exception as e:
        logger.warning("LLM scoring failed: %s", e)
        return {"relevance": 0, "accuracy": 0, "completeness": 0, "actionability": 0}


@app.command()
def run(
    quick: bool = typer.Option(False, help="Run only 5 quick questions"),
    export: str = typer.Option(None, help="Export results to JSON file"),
    llm_judge: bool = typer.Option(False, "--llm-judge", help="Use Claude as a judge (costs ~$0.02)"),
):
    """Run the NEXUS evaluation pipeline."""
    questions = EVAL_QUESTIONS[:5] if quick else EVAL_QUESTIONS

    console.print(Panel.fit(
        f"[bold]NEXUS Evaluation Pipeline[/bold]\n"
        f"Questions: {len(questions)} | LLM Judge: {'Yes' if llm_judge else 'No'}",
        border_style="blue",
    ))

    results = []
    total_keyword_score = 0
    total_quality_score = 0
    total_llm_score = 0
    errors = 0

    for i, q in enumerate(questions):
        console.print(f"\n[dim]({i+1}/{len(questions)})[/dim] [bold]{q['id']}[/bold]: {q['question'][:60]}...")

        start_time = time.time()
        try:
            result = query(q["question"], thread_id=f"eval-{q['id']}")
            answer = result.get("answer", _extract_answer(result.get("messages", [])))
            elapsed = time.time() - start_time

            # Score
            kw_score = score_keyword_coverage(answer, q["expected_keywords"])
            quality_score = score_answer_quality(answer)
            total_keyword_score += kw_score
            total_quality_score += quality_score

            llm_scores = {}
            if llm_judge:
                llm_scores = score_with_llm(q["question"], answer, q["expected_keywords"])
                avg_llm = sum(llm_scores.values()) / len(llm_scores) if llm_scores else 0
                total_llm_score += avg_llm / 5  # normalize to 0-1

            # Color-coded score display
            kw_color = "green" if kw_score >= 0.6 else "yellow" if kw_score >= 0.3 else "red"
            q_color = "green" if quality_score >= 0.6 else "yellow" if quality_score >= 0.3 else "red"

            console.print(f"  Keywords: [{kw_color}]{kw_score:.0%}[/{kw_color}] | "
                         f"Quality: [{q_color}]{quality_score:.0%}[/{q_color}] | "
                         f"Time: {elapsed:.1f}s | "
                         f"Length: {len(answer)} chars")

            if llm_judge and llm_scores:
                console.print(f"  LLM Judge: R={llm_scores.get('relevance',0)} "
                             f"A={llm_scores.get('accuracy',0)} "
                             f"C={llm_scores.get('completeness',0)} "
                             f"Act={llm_scores.get('actionability',0)}")

            results.append({
                "id": q["id"],
                "question": q["question"],
                "category": q["category"],
                "difficulty": q["difficulty"],
                "expected_agent": q["expected_agent"],
                "keyword_score": kw_score,
                "quality_score": quality_score,
                "llm_scores": llm_scores,
                "elapsed_seconds": elapsed,
                "answer_length": len(answer),
                "answer_preview": answer[:300],
            })

        except Exception as e:
            console.print(f"  [red]ERROR: {e}[/red]")
            errors += 1
            results.append({
                "id": q["id"],
                "question": q["question"],
                "error": str(e),
            })

    # Summary
    n = len(questions) - errors
    console.print("\n")

    table = Table(title="Evaluation Summary", border_style="blue")
    table.add_column("Metric", style="bold")
    table.add_column("Score", justify="center")

    avg_kw = total_keyword_score / n if n else 0
    avg_q = total_quality_score / n if n else 0

    table.add_row("Keyword Coverage", f"{avg_kw:.0%}")
    table.add_row("Answer Quality", f"{avg_q:.0%}")
    if llm_judge:
        avg_llm = total_llm_score / n if n else 0
        table.add_row("LLM Judge (avg)", f"{avg_llm:.0%}")
    table.add_row("Questions Run", str(len(questions)))
    table.add_row("Errors", str(errors))
    table.add_row("Overall", f"{(avg_kw + avg_q) / 2:.0%}")

    console.print(table)

    # Category breakdown
    categories = {}
    for r in results:
        if "error" in r:
            continue
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"kw": [], "q": []}
        categories[cat]["kw"].append(r["keyword_score"])
        categories[cat]["q"].append(r["quality_score"])

    if categories:
        cat_table = Table(title="Score by Category", border_style="dim")
        cat_table.add_column("Category")
        cat_table.add_column("Keywords", justify="center")
        cat_table.add_column("Quality", justify="center")
        cat_table.add_column("Count", justify="center")

        for cat, scores in sorted(categories.items()):
            avg_k = sum(scores["kw"]) / len(scores["kw"])
            avg_q = sum(scores["q"]) / len(scores["q"])
            cat_table.add_row(cat, f"{avg_k:.0%}", f"{avg_q:.0%}", str(len(scores["kw"])))

        console.print(cat_table)

    # Export
    if export:
        output = {
            "timestamp": datetime.now().isoformat(),
            "total_questions": len(questions),
            "errors": errors,
            "avg_keyword_score": avg_kw,
            "avg_quality_score": avg_q,
            "results": results,
        }
        export_path = Path(export).with_suffix(".json")
        export_path.write_text(json.dumps(output, indent=2, default=str))
        console.print(f"\n[green]Results exported to {export_path}[/green]")


if __name__ == "__main__":
    app()

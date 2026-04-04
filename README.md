# NEXUS Agent

Multi-agent IT operations intelligence system powered by LangGraph and Claude.

NEXUS routes natural language questions to specialized AI agents that search across enterprise knowledge bases, live ticketing systems, and documentation to provide grounded, source-cited answers.

## Architecture

```
                         ┌─────────────────────┐
                         │     User Query       │
                         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │     Supervisor       │
                         │   (Claude Haiku)     │
                         │  Intent → Routing    │
                         └──────────┬──────────┘
                                    │
               ┌────────────┬───────┴───────┬────────────┐
               ▼            ▼               ▼            ▼
        ┌─────────┐  ┌──────────┐  ┌────────────┐  ┌─────────┐
        │Librarian│  │ Analyst  │  │ Architect  │  │  Scribe │
        │  Docs & │  │Incidents │  │Dependencies│  │ Runbook │
        │Runbooks │  │& Patterns│  │& Blast     │  │   Gen   │
        │         │  │          │  │  Radius    │  │         │
        └────┬────┘  └────┬─────┘  └─────┬──────┘  └────┬────┘
             │             │              │              │
             └──────┬──────┴──────┬───────┘              │
                    ▼             ▼                      ▼
             ┌───────────┐ ┌──────────┐          ┌───────────┐
             │ ChromaDB  │ │ Live API │          │   RAG +   │
             │   RAG     │ │ Queries  │          │ Synthesis │
             │ (2,880    │ │FS / Jira │          │           │
             │  chunks)  │ │          │          │           │
             └───────────┘ └──────────┘          └───────────┘
```

## Agents

| Agent | Role | Tools |
|-------|------|-------|
| **Librarian** | Documentation retrieval, procedures, how-to guides | RAG search (docs, runbooks) |
| **Analyst** | Incident pattern analysis, root cause identification | RAG search (incidents) + live FreshService/Jira queries |
| **Architect** | System dependency mapping, blast radius analysis | RAG search (architecture, change logs) |
| **Scribe** | Runbook and documentation generation | RAG search (docs + incidents) for synthesis |

## Tech Stack

- **Orchestration**: LangGraph (supervisor pattern)
- **LLM**: Claude Sonnet (agents) + Claude Haiku (routing)
- **RAG**: ChromaDB + HuggingFace `all-MiniLM-L6-v2` embeddings (local, zero API cost)
- **Live Data**: FreshService API, Jira API (real-time ticket queries)
- **Data Sources**: FreshService tickets, Jira issues, Confluence pages, local docs (md, docx, pdf, xlsx, pptx)
- **UI**: Streamlit web app with real-time agent routing display
- **Observability**: LangSmith tracing
- **Evaluation**: 15-question test suite with keyword coverage + quality scoring

## Quick Start

```bash
# Clone and install
git clone https://github.com/kpatton-dev/nexus-agent.git
cd nexus-agent
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pip install sentence-transformers streamlit

# Configure
cp .env.example .env
# Edit .env with your API keys

# Ingest knowledge base
python scripts/ingest.py manual      # Local files
python scripts/ingest.py freshservice # FreshService tickets
python scripts/ingest.py jira        # Jira issues
python scripts/ingest.py confluence  # Confluence pages
python scripts/ingest.py stats       # Check chunk count

# Run
streamlit run app.py                 # Web UI
python scripts/chat.py --stream      # CLI chat
python scripts/eval.py               # Run evaluation suite
```

## Evaluation Results

Baseline evaluation across 15 test questions:

| Metric | Score |
|--------|-------|
| Keyword Coverage | 95% |
| Answer Quality | 77% |
| Overall | 86% |
| Errors | 0 |

| Category | Keywords | Quality | Count |
|----------|----------|---------|-------|
| Documentation | 100% | 86% | 4 |
| Incident Analysis | 100% | 79% | 4 |
| Dependency Mapping | 100% | 90% | 2 |
| Blast Radius | 70% | 52% | 2 |
| Runbook Generation | 90% | 73% | 2 |
| Ownership | 100% | 75% | 1 |

## Project Structure

```
nexus-agent/
├── src/nexus/
│   ├── graph.py           # LangGraph supervisor orchestration
│   ├── state.py           # Shared agent state schema
│   ├── config.py          # Configuration from environment
│   ├── prompts.py         # Agent system prompts
│   ├── agents/            # 4 specialist agents
│   ├── tools/             # RAG retrieval + live API tools
│   ├── rag/               # ChromaDB vectorstore + chunker
│   └── connectors/        # Data ingestion (FS, Jira, Confluence)
├── scripts/
│   ├── chat.py            # Interactive CLI
│   ├── ingest.py          # Data ingestion pipeline
│   └── eval.py            # Evaluation pipeline
├── app.py                 # Streamlit web UI
├── tests/                 # Unit tests
├── langgraph.json         # LangGraph Platform config
└── pyproject.toml
```

## License

MIT

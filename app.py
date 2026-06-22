"""NEXUS — Multi-Agent IT Operations Intelligence

Streamlit frontend for the NEXUS LangGraph agent system.
"""

import hashlib
import hmac
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from nexus.graph import graph, _extract_answer
from nexus.rag.vectorstore import get_collection_stats

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="NEXUS",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Auth gate — password from NEXUS_PASSWORD env var
# ---------------------------------------------------------------------------
def check_password() -> bool:
    """Return True if the user has entered the correct password."""
    expected = os.getenv("NEXUS_PASSWORD", "")
    if not expected:
        return True  # no password set — allow through (local dev)

    if st.session_state.get("authenticated"):
        return True

    st.markdown("## 🔮 NEXUS")
    st.caption("Multi-Agent IT Operations Intelligence")
    password = st.text_input("Password", type="password", key="pw_input")
    if st.button("Login", type="primary"):
        if hmac.compare_digest(password, expected):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


if not check_password():
    st.stop()

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* Tighter padding */
    .block-container { padding-top: 2rem; }

    /* Agent badges */
    .agent-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 4px;
    }
    .badge-librarian { background: #3b82f6; color: white; }
    .badge-analyst { background: #f59e0b; color: black; }
    .badge-architect { background: #10b981; color: white; }
    .badge-scribe { background: #8b5cf6; color: white; }
    .badge-supervisor { background: #64748b; color: white; }

    /* Source cards */
    .source-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 8px 12px;
        margin: 4px 0;
        font-size: 0.85rem;
    }

    /* Stats */
    .stat-box {
        background: #1e293b;
        border-radius: 8px;
        padding: 12px;
        text-align: center;
        border: 1px solid #334155;
    }
    .stat-number { font-size: 1.5rem; font-weight: 700; color: #6366f1; }
    .stat-label { font-size: 0.75rem; color: #94a3b8; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Agent metadata
# ---------------------------------------------------------------------------
AGENTS = {
    "librarian": {"icon": "📚", "color": "badge-librarian", "desc": "Documentation & Runbooks"},
    "analyst": {"icon": "📊", "color": "badge-analyst", "desc": "Incident Patterns & Trends"},
    "architect": {"icon": "🏗️", "color": "badge-architect", "desc": "Dependencies & Blast Radius"},
    "scribe": {"icon": "📝", "color": "badge-scribe", "desc": "Runbook Generation"},
}

SAMPLE_QUERIES = [
    "What systems are affected if UKG goes down?",
    "Most common FreshService ticket categories this month?",
    "What's the process for Coupa-to-NetSuite PO reconciliation?",
    "Create a runbook for handling Salesforce-NetSuite sync failures",
    "Who owns the Workato integration recipes?",
]

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = "streamlit-default"
if "agent_events" not in st.session_state:
    st.session_state.agent_events = []

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🔮 NEXUS")
    st.caption("Multi-Agent IT Operations Intelligence")
    st.divider()

    # Stats
    try:
        stats = get_collection_stats()
        cols = st.columns(3)
        with cols[0]:
            st.markdown(f'<div class="stat-box"><div class="stat-number">{stats["total_chunks"]:,}</div><div class="stat-label">Knowledge Chunks</div></div>', unsafe_allow_html=True)
        with cols[1]:
            st.markdown('<div class="stat-box"><div class="stat-number">4</div><div class="stat-label">Agents</div></div>', unsafe_allow_html=True)
        with cols[2]:
            st.markdown('<div class="stat-box"><div class="stat-number">4</div><div class="stat-label">Data Sources</div></div>', unsafe_allow_html=True)
    except Exception:
        st.warning("Vector store not initialized. Run `python scripts/ingest.py all` first.")

    st.divider()

    # Agent roster
    st.markdown("### Agents")
    for name, meta in AGENTS.items():
        st.markdown(f'{meta["icon"]} **{name.title()}** — {meta["desc"]}')

    st.divider()

    # Sample queries
    st.markdown("### Quick Queries")
    for q in SAMPLE_QUERIES:
        if st.button(q, key=f"sample_{q[:20]}", use_container_width=True):
            st.session_state.pending_query = q

    st.divider()

    if st.button("Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.agent_events = []
        st.session_state.thread_id = f"streamlit-{id(st.session_state)}"
        st.rerun()

    st.divider()
    st.caption("LangGraph + Claude | ChromaDB RAG")
    st.caption("FreshService + Jira + Confluence")

# ---------------------------------------------------------------------------
# Main chat area
# ---------------------------------------------------------------------------
st.markdown("# 🔮 NEXUS")

# Render chat history
for msg in st.session_state.messages:
    role = msg["role"]
    with st.chat_message(role):
        st.markdown(msg["content"])
        if "sources" in msg and msg["sources"]:
            with st.expander(f"📖 Sources ({len(msg['sources'])})"):
                for src in msg["sources"]:
                    st.markdown(f'`{src.get("source", "?")}` **{src.get("title", "Unknown")}** — _{src.get("content_type", "")}_')
        if "agents_used" in msg and msg["agents_used"]:
            badges = " ".join(
                f'<span class="agent-badge {AGENTS.get(a, {}).get("color", "badge-supervisor")}">{a}</span>'
                for a in msg["agents_used"]
            )
            st.markdown(f"Routed to: {badges}", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Handle input
# ---------------------------------------------------------------------------
pending = st.session_state.pop("pending_query", None)
user_input = st.chat_input("Ask NEXUS a question...") or pending

if user_input:
    # Show user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Run the graph
    with st.chat_message("assistant"):
        status_container = st.status("🔮 **NEXUS is thinking...**", expanded=True)

        agents_used = []
        sources = []

        try:
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            events = list(graph.stream(
                {"messages": [{"role": "user", "content": user_input}]},
                config=config,
                stream_mode="updates",
            ))

            # Process events for agent tracking
            all_messages = []
            for event in events:
                for node_name, output in event.items():
                    if node_name == "supervisor":
                        # Check for routing
                        msgs = output.get("messages", [])
                        for msg in msgs:
                            if isinstance(msg, AIMessage) and msg.tool_calls:
                                for tc in msg.tool_calls:
                                    if tc["name"].startswith("transfer_to_"):
                                        agent = tc["name"].replace("transfer_to_", "")
                                        agents_used.append(agent)
                                        status_container.update(label=f"🔮 Routing to **{agent}**...")
                    elif node_name in AGENTS:
                        status_container.update(label=f"{AGENTS[node_name]['icon']} **{node_name.title()}** is analyzing...")
                        msgs = output.get("messages", [])
                        for msg in msgs:
                            # Collect sources from tool results
                            if isinstance(msg, ToolMessage) and msg.artifact:
                                if isinstance(msg.artifact, list):
                                    sources.extend(msg.artifact)
                    # Collect all messages
                    all_messages.extend(output.get("messages", []))

            # Extract the answer
            answer = _extract_answer(all_messages)
            status_container.update(label="✅ **Done**", state="complete", expanded=False)

            # Display answer
            st.markdown(answer)

            # Deduplicate sources by title
            seen_titles = set()
            unique_sources = []
            for src in sources:
                title = src.get("title", "Unknown")
                if title not in seen_titles:
                    seen_titles.add(title)
                    unique_sources.append(src)

            if unique_sources:
                with st.expander(f"📖 Sources ({len(unique_sources)})"):
                    for src in unique_sources:
                        st.markdown(f'`{src.get("source", "?")}` **{src.get("title", "Unknown")}** — _{src.get("content_type", "")}_')

            if agents_used:
                badges = " ".join(
                    f'<span class="agent-badge {AGENTS.get(a, {}).get("color", "badge-supervisor")}">{a}</span>'
                    for a in agents_used
                )
                st.markdown(f"Routed to: {badges}", unsafe_allow_html=True)

            # Save to history
            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "sources": unique_sources,
                "agents_used": agents_used,
            })

        except Exception as e:
            status_container.update(label="❌ **Error**", state="error")
            st.error(f"Query failed: {e}")

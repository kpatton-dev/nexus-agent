"""Central configuration for NEXUS."""

import os
from dotenv import load_dotenv

load_dotenv()


# LLM Models
CLAUDE_MODEL = "claude-sonnet-4-6"  # primary agent model
CLAUDE_FAST_MODEL = "claude-haiku-4-5-20251001"  # routing/classification

# Vector Store
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "nexus_knowledge")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # local embeddings — no API cost
RAG_TOP_K = 8

# Data Sources
FRESHSERVICE_DOMAIN = os.getenv("FRESHSERVICE_DOMAIN", "")
FRESHSERVICE_API_KEY = os.getenv("FRESHSERVICE_API_KEY", "")

JIRA_URL = os.getenv("JIRA_URL", "")
JIRA_USERNAME = os.getenv("JIRA_USERNAME", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "CCC")

CONFLUENCE_URL = os.getenv("CONFLUENCE_URL", "")
CONFLUENCE_USERNAME = os.getenv("CONFLUENCE_USERNAME", "")
CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN", "")
CONFLUENCE_SPACE_KEY = os.getenv("CONFLUENCE_SPACE_KEY", "IT")

# Paths
KNOWLEDGE_BASE_DIR = os.getenv("KNOWLEDGE_BASE_DIR", "./knowledge_base")

# Known enterprise systems for auto-tagging
KNOWN_SYSTEMS = [
    "Coupa", "NetSuite", "Salesforce", "UKG", "Workato",
    "Five9", "FreshService", "Jira", "Slack", "Okta",
    "Google Workspace", "Zuora", "Expensify", "LogiSense",
    "Domo", "LeanIX", "RemedyForce", "Degreed", "Azure AD",
]

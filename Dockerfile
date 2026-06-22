FROM python:3.12-slim

WORKDIR /app

# System deps for sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY pyproject.toml .
RUN pip install --no-cache-dir -e "." \
    sentence-transformers \
    streamlit \
    python-docx \
    pymupdf \
    pandas \
    openpyxl \
    langchain

# Copy source
COPY src/ src/
COPY scripts/ scripts/
COPY app.py .
COPY .streamlit/ .streamlit/

# Bake in the knowledge base (ChromaDB vectors + raw docs)
COPY chroma_data/ chroma_data/
COPY knowledge_base/ knowledge_base/

# Pre-download the embedding model at build time (avoids cold-start download)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", \
    "--server.port=8501", \
    "--server.address=0.0.0.0", \
    "--server.headless=true", \
    "--browser.gatherUsageStats=false"]

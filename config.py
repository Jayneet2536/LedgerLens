# config.py
import os
from dotenv import load_dotenv
load_dotenv()

CONFIG = {
    "pdf_path": "amzn.pdf",

    # Document identity — used for metadata tagging at ingestion time
    # (main.py) and for metadata-filtered retrieval (retrieval/strategies.py).
    # Change these when you point the pipeline at a different document;
    # you shouldn't need to touch any other file to do that.
    "company": "AMAZON.COM, INC.",
    "fiscal_year": "2025",
    "doc_type": "10-K",

    # Chunking
    "chunking_strategy": "semantic",
    "chunk_size": 1000,
    "chunk_overlap": 200,

    # API keys
    "voyage_api_key": os.getenv("VOYAGE_API_KEY", "your-voyage-key-here"),
    "groq_api_key": os.getenv("GROQ_API_KEY", "your-groq-key-here"),
    "google_api_key": os.getenv("GOOGLE_API_KEY", "your-google-api-key-here"),

    # DB Settings — host/port now come from env vars first. Locally they'll
    # fall back to "localhost" like before; once you docker-compose this,
    # set CHROMA_HOST to the service name (e.g. "chromadb") in your compose
    # file instead of editing this file again.
    "vector_store": "chromadb",
    "chroma_host": os.getenv("CHROMA_HOST", "localhost"),
    "chroma_port": int(os.getenv("CHROMA_PORT", "8000")),
    "collection_name": "financial_10k_collection",

    # Retrieval
    "retrieval_strategy": "hybrid_rrf",  # Options: standard, mmr, hybrid_rrf, metadata_filtered, reranked
    "top_k_results": 5,
}

# Non-fatal heads-up for unset keys — better than discovering it via a
# confusing 401 several minutes into an ingestion or eval run. Doesn't
# block execution since not every run needs every key (e.g. google_api_key
# isn't needed once you're judging with Groq instead of Gemini).
for _key in ("voyage_api_key", "groq_api_key", "google_api_key"):
    if CONFIG[_key].endswith("-here"):
        print(f"[config] Warning: {_key} looks unset (still the placeholder). "
              f"Add it to your .env if this run needs it.")
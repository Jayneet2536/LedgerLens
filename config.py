# config.py
import os
from dotenv import load_dotenv
load_dotenv()

CONFIG = {
    "pdf_path": "amzn.pdf",
    
    # Chunking
    "chunking_strategy": "markdown_structural", 
    "chunk_size": 1000,
    "chunk_overlap": 200,
    
    # API
    "voyage_api_key": os.getenv("VOYAGE_API_KEY", "your-voyage-key-here"),
    "groq_api_key": os.getenv("GROQ_API_KEY", "your-groq-key-here"),
    
    # DB Settings
    "vector_store": "chromadb",
    "chroma_host": "localhost",
    "chroma_port": 8000,

    # Retrieval
    "retrieval_strategy": "hybrid_rrf", # Options: standard, mmr, hybrid_rrf
    "top_k_results": 5
}
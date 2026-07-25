# LedgerLens

LedgerLens is an advanced Retrieval-Augmented Generation (RAG) pipeline designed specifically for financial documents, such as 10-K filings. It leverages multiple extraction, chunking, embedding, and retrieval strategies to accurately answer complex financial questions, ensuring context like tables and forward-looking statements are preserved.

## Features

- **Document Parsing**: Parses PDFs utilizing `UnstructuredPDFLoader` to retain structural elements.
- **Multiple Chunking Strategies**: Choose between `naive`, `recursive`, `markdown_structural`, `markdown_hierarchical`, `semantic`, and `table_page` chunking depending on the complexity of your document.
- **Advanced Retrieval Options**: Features multiple retrieval strategies including standard similarity, MMR (Maximal Marginal Relevance), Hybrid RRF (Reciprocal Rank Fusion with BM25), metadata filtering, and re-ranking.
- **State-of-the-art Models**: Employs Voyage AI for embeddings and Groq for blazing-fast inference with LLMs like Qwen or Llama 3.
- **API & Frontend**: Includes a FastAPI backend with state management for dynamic re-indexing and strategy swapping, along with a Vite-based frontend.
- **Comprehensive Testing**: Run automated smoke tests to compare strategy performance and validate responses.

## Project Structure

- `main.py` - Handles document ingestion, chunking, and embedding into ChromaDB.
- `retrieval_main.py` - Standalone retrieval execution for testing queries.
- `smoke_test.py` - Comprehensive smoke tests for chunking, retrieval, and end-to-end RAG pipeline.
- `config.py` - Configuration settings for models, chunking strategies, and database parameters.
- `api/` - FastAPI backend application to serve the RAG system and manage state.
- `frontend/` - Vite-based web interface for interacting with LedgerLens.
- `chunking/`, `embeddings/`, `retrieval/`, `vectorstore/` - Core modules for the RAG pipeline.

## Getting Started

### 1. Environment Setup

Create a `.env` file in the root directory and add your API keys:

```env
VOYAGE_API_KEY="your-voyage-key-here"
GROQ_API_KEY="your-groq-key-here"
GOOGLE_API_KEY="your-google-api-key-here"
CHROMA_HOST="localhost"
CHROMA_PORT=8000
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Ingest Data

Drop your target PDF (e.g., `amzn.pdf`) into the project directory and run the ingestion pipeline. You can modify `config.py` to adjust chunking parameters and metadata.

```bash
python main.py
```

### 4. Run Smoke Tests

Ensure all components and strategies are functioning correctly:

```bash
python smoke_test.py
```

### 5. Start the API

Start the backend API to interact with the indexed documents:

```bash
uvicorn api.main:app --reload
```

---

## RAG Strategy Comparison Results

Below is a comparison of two different Retrieval-Augmented Generation configurations using Amazon's 10-K document (amzn.pdf). 

- **Config A (Baseline):** `markdown_structural` chunking + `hybrid_rrf` retrieval.
- **Config B (Enhanced):** `semantic` chunking + `hybrid_rrf` retrieval.

| Question | Config A (Vanilla) Result | Config B (Hybrid) Result | Winner |
|---|---|---|---|
| "How many employees did Amazon have as of December 31, 2025?" | Retrieved a broad section on Human Capital. Answered correctly (1.57 million). | Retrieved a highly targeted chunk on workforce size. Answered correctly. | Tie |
| "What were Amazon's cash capital expenditures in 2024 vs 2025, and what does management expect for 2026?" | Retrieved chunks missing 2026 guidance due to hard structural boundaries. Answered only for 2024/2025. | Retrieved a semantically aligned chunk containing past capex and 2026 expectations. Answered fully. | Config B |
| "What is Amazon's Q1 2026 guidance for net sales and operating income?" | Struggled with header splits, separating net sales from operating income. Missed operating income guidance. | Semantic chunking kept the forward-looking statements together as one cohesive topic. Answered correctly. | Config B |
| "What fine did the CNPD impose on Amazon Europe Core S.à r.l., and what happened with the appeals?" | Found the exact legal chunk in both. Both answered correctly. | Found the exact legal chunk in both. Both answered correctly. | Tie |
| "What was Amazon's effective tax rate in 2025 vs 2024, and what were the two primary drivers of change?" | Chunking split the tax rate figures from the driver explanations. Answer was incomplete. | Semantic grouping kept the tax rates and the 2025 Tax Act driver together. Answered fully. | Config B |

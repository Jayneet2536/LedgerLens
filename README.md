# LedgerLens

LedgerLens is an advanced Retrieval-Augmented Generation (RAG) pipeline designed specifically for answering complex queries based on financial documents, such as 10-K filings. 

It implements a comprehensive architecture supporting multiple chunking methodologies, hybrid retrieval strategies, and a FastAPI backend with a React (Vite) frontend.

## 🌟 Key Features

- **Robust Document Parsing:** Utilizes `UnstructuredPDFLoader` to accurately parse PDFs while preserving structural elements like tables and headers.
- **Multiple Chunking Strategies:** Choose from `naive`, `recursive`, `markdown_structural`, `markdown_hierarchical`, `semantic`, and `table_page` depending on the complexity of your document.
- **Advanced Retrieval Options:** Includes standard similarity, MMR (Maximal Marginal Relevance), Hybrid RRF (Reciprocal Rank Fusion with BM25), metadata filtering, and semantic re-ranking.
- **State-of-the-Art Models:** Powered by Voyage AI for embeddings and Groq (Qwen / Llama 3) for blazing-fast inference.
- **Full-Stack Application:** Comes with a FastAPI backend for state management, dynamic re-indexing, and strategy swapping, along with a modern Vite/React-based frontend interface.

## 📂 Project Structure

- `main.py`: Handles document ingestion, chunking, and embedding into ChromaDB.
- `retrieval_main.py`: Standalone script for executing retrieval and testing queries.
- `config.py`: Centralized configuration for models, chunking strategies, and database parameters.
- `api/`: FastAPI backend application.
- `frontend/`: Vite + React web interface.
- `chunking/`, `embeddings/`, `retrieval/`, `vectorstore/`: Core modules of the RAG pipeline.

---

## 🚀 Setup & Installation Instructions

Follow these steps to set up the project locally.

### 1. Prerequisites
- **Python 3.9+**
- **Node.js & npm** (for the frontend)
- **Docker & Docker Compose** (to run the ChromaDB vector database)

### 2. Environment Configuration
Create a `.env` file in the root directory and add your API keys:

```env
VOYAGE_API_KEY="your-voyage-key-here"
GROQ_API_KEY="your-groq-key-here"
GOOGLE_API_KEY="your-google-api-key-here"
CHROMA_HOST="localhost"
CHROMA_PORT=8000
```

### 3. Start the Vector Database
We use ChromaDB for vector storage. Start it using the provided Docker Compose file:
```bash
docker-compose up -d
```
*(This will start ChromaDB on port 8000 and persist data to `./chroma_data`)*

### 4. Install Python Dependencies
Set up your virtual environment (optional but recommended) and install the required Python packages:
```bash
pip install -r requirements.txt
```

### 5. Ingest Data
Drop your target PDF (e.g., `amzn.pdf`) into the project directory and run the ingestion script to chunk the document and store the embeddings in ChromaDB:
```bash
python main.py
```
*(Note: You can tweak chunking parameters and strategies inside `config.py`)*

### 6. Run the Backend API
Start the FastAPI server:
```bash
uvicorn api.main:app --reload
```
*(The API will be available at `http://localhost:8000`)*

### 7. Run the Frontend
Open a new terminal window, navigate to the frontend directory, install dependencies, and start the development server:
```bash
cd frontend
npm install
npm run dev
```
*(The frontend will typically be accessible at `http://localhost:5173`)*

---
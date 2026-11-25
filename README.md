# LedgerLens

LedgerLens answers questions about financial PDFs using a React frontend, FastAPI, Voyage embeddings, Groq, and ChromaDB. It supports multiple chunking and retrieval strategies, including hybrid BM25/vector retrieval and local cross-encoder reranking.

## Run everything with Docker

Install and start Docker Desktop (Linux containers), or Docker Engine with Compose v2+ on Linux. Python and Node are provided by the images.

One-time setup: copy `.env.example` to `.env` and fill in your **VOYAGE_API_KEY** and **GROQ_API_KEY**. In PowerShell:

```powershell
Copy-Item .env.example .env
```

Then start all three services from the repository root with one command:

```bash
docker compose up --build -d
```

After the images have been built, start without rebuilding:

```bash
docker compose up -d
```

If Docker Hub reports a TLS handshake timeout and the application images already exist locally, start entirely from those images:

```bash
docker compose up --no-build --pull never -d
```

Use `--build` when changing application code or dependencies. A fresh build needs access to Docker Hub and the package registries.

Open **http://localhost:8080**. API health is at http://localhost:8080/api/health and API documentation at http://localhost:8080/api/docs.

The first build downloads the PDF/OCR and CPU inference dependencies and can take several minutes. On an empty database, the API automatically indexes the bundled `amzn.pdf`. The UI shows progress; chat becomes available when indexing finishes. Indexing and chat require valid provider keys, internet access, and available provider quota. Google credentials are not required.

The frontend serves a production build through Nginx and proxies `/api/` to the backend. Only the frontend port is published, bound to localhost. The API and database communicate over the Compose network. Both app containers run as non-root users; the API runs one worker because reindex state is held in memory.

## Configuration

Optional settings in `.env`:

```env
APP_PORT=8080
PDF_FILE=./amzn.pdf
```

`PDF_FILE` must point to an existing PDF; it is mounted read-only. After changing it, recreate the backend and use **Reindex** in the UI to replace the existing index. Update document identity (`company`, `fiscal_year`, `doc_type`) in `config.py` for another filing, then rebuild. Chunking and retrieval defaults are also in `config.py`; the UI can switch strategies at runtime.

The `reranked` strategy downloads its Hugging Face model on first use. Model caches persist in the `model_cache` Docker volume. PDF parsing may also download layout models on first use.

## Operations

Reindexing runs as a FastAPI background task. Chat keeps using the current index while a separate collection is built. When the replacement is ready, new chat requests switch to it; in-flight retrievals finish before the old collection is removed. A failed rebuild leaves the current index available. The active collection and its chunking settings are saved in ChromaDB and restored after a restart.

Only one rebuild runs at a time. Chat is unavailable during the first ingestion because no index exists yet. Jobs run in the API process and do not resume automatically if it restarts; the last published index remains available. Keep the API at one worker with this setup.

```bash
# Container status and health
docker compose ps

# Follow application and indexing logs
docker compose logs -f backend

# Stop the app; retain the index and downloaded models
docker compose down

# Start again
docker compose up -d
```

Chroma persists its index in the `chroma_data` Docker volume at `/data`, using [Chroma's current persistence setting](https://cookbook.chromadb.dev/core/configuration/). The older tracked `./chroma_data` snapshot is not mounted or modified. A fresh Docker volume is indexed automatically. `docker compose down -v` deletes the Docker index and model caches; use it only when you intend to reset them.

If startup fails, check `docker compose logs backend chromadb`. Missing keys are reported at startup; provider or PDF errors appear in `/api/reindex-status` and the UI. API health reports connectivity separately from index readiness so the frontend can show ingestion progress.

## Local development

Use Python 3.11 and Node.js 22. Install the PDF system dependencies listed in `Dockerfile` if running ingestion outside Docker.

Start Chroma separately on host port 8001:

```bash
docker run --rm -p 127.0.0.1:8001:8000 -v ledgerlens-dev-chroma:/data chromadb/chroma:1.5.9
```

Set `CHROMA_HOST=localhost` and `CHROMA_PORT=8001` in your root `.env` alongside your provider keys, then:

```bash
pip install -r requirements-runtime.txt
uvicorn api.app:app --reload --port 8000
```

In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

The frontend defaults to `http://127.0.0.1:8000` for local development. `frontend/.env.example` documents the optional build-time override. Docker always builds with the same-origin `/api` URL.

`requirements-runtime.txt` contains the app dependencies used by Docker. `requirements.txt` additionally installs the optional evaluation and other provider integrations.

## Repository layout

- `api/`: chat, health, strategy switching, ingestion, and reindex status.
- `main.py`: document ingestion; `retrieval_main.py`: standalone retrieval.
- `chunking/`, `embeddings/`, `retrieval/`, `vectorstore/`: pipeline components.
- `frontend/`: React UI, production Dockerfile, and Nginx proxy.
- `docker/`: database startup wait and API health probe.
- `Dockerfile`, `docker-compose.yml`: backend image and complete application stack.

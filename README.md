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

## Student demo: Railway backend + Vercel frontend

The repository includes `Dockerfile.railway`, `railway.toml`, and `frontend/vercel.json`. Railway uses a separate image with the bundled PDF and no provider-specific build cache mounts. Startup waits for Chroma, honors `PORT`, and serves the API directly at `/health`, `/chat`, and `/docs`. Local Compose sets `ROOT_PATH=/api` for its Nginx proxy.

### 1. Push to GitHub

Commit and push the changes, including `amzn.pdf`. Keep `.env` untracked; `git check-ignore .env` should print `.env`.

### 2. Deploy ChromaDB on Railway

Create an empty Railway project, then add a Docker-image service using `chromadb/chroma:1.5.9`. Name the service `chromadb`. Add `CHROMA_PERSIST_PATH=/data` and attach a volume mounted at `/data`. Deploy and wait until the database starts. Do not give this service a public domain.

### 3. Deploy the API on Railway

In the same project and environment, add a service from this GitHub repository. Name it `ledgerlens-api`; leave the root directory at the repository root. Railway reads `railway.toml` to select `Dockerfile.railway`, one replica, and the `/health` health check. Leave the custom start command empty.

Add these service variables (replace the two keys):

```env
VOYAGE_API_KEY=your-real-voyage-key
GROQ_API_KEY=your-real-groq-key
CHROMA_HOST=chromadb.railway.internal
CHROMA_PORT=8000
PORT=8000
```

If you choose another database service name, use its actual private hostname for `CHROMA_HOST`. Do not copy the local `.env` wholesale: its `CHROMA_HOST`, `PDF_FILE`, or `ROOT_PATH` may be inappropriate for cloud deployment. `PDF_PATH` and `HF_HOME` are already set in the Railway image. Keep `ROOT_PATH` unset on Railway.

Deploy, then generate a public domain for the API in Settings > Networking, targeting port 8000. Open `https://YOUR-BACKEND-DOMAIN/health` and `/docs`. First-time indexing starts automatically. The UI can connect while it builds; wait for `index_loaded: true` before chatting. The Railway database starts fresh; your local Docker volume is not uploaded.

### 4. Deploy the frontend on Vercel

Import the same GitHub repository. Set Root Directory to `frontend`. The included `vercel.json` selects Vite, `npm ci`, `npm run build`, and the `dist` output directory.

Set `VITE_API_URL=https://YOUR-BACKEND-DOMAIN` for the deployment environment, with no `/api` suffix, then deploy. Put provider API keys only in Railway. If the backend URL changes, update this variable and redeploy Vercel.

Optionally set `CORS_ORIGINS=https://YOUR-PROJECT.vercel.app` on the Railway API and redeploy it. Multiple allowed origins can be comma-separated. Without this variable, the existing wildcard behavior is retained.

### 5. Check the demo

Open the Vercel URL, send a question, change retrieval modes, and rebuild the index while continuing to chat. The local reranker downloads its model the first time it is selected; its cache is temporary on Railway unless additional storage is configured. The Chroma volume retains completed indexes and their active pointer across API redeployments.

Use Railway's trial allocation for the demonstration and monitor remaining credits and memory in its dashboard. If outgoing provider requests are blocked on a Limited Trial, connect/verify your GitHub account. An OOM/exit 137 indicates the workload exceeded the service's memory allowance. Background jobs run in the API process and stop on redeployment, so avoid redeploying during your presentation's reindex demo.

## Repository layout

- `api/`: chat, health, strategy switching, ingestion, and reindex status.
- `main.py`: document ingestion; `retrieval_main.py`: standalone retrieval.
- `chunking/`, `embeddings/`, `retrieval/`, `vectorstore/`: pipeline components.
- `frontend/`: React UI, production Dockerfile, and Nginx proxy.
- `docker/`: database startup wait and API health probe.
- `Dockerfile`, `docker-compose.yml`: backend image and complete application stack.

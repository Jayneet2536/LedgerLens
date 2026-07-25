# RAG Chat Frontend

React + Vite frontend for the existing FastAPI RAG backend.

## Run locally

1. Start the FastAPI backend, usually from the project root:

   ```bash
   uvicorn api.app:app --reload
   ```

2. Install and run the frontend:

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. If your backend is not at `http://localhost:8000`, create `.env` from `.env.example` and update:

   ```bash
   VITE_API_URL=http://localhost:8000
   ```

The app reads `VITE_API_URL` at build time, so production deployments can point to a deployed API without code changes.

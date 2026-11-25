"""Check API availability and database connectivity, including during ingestion."""
import json
import os
import urllib.request

port = os.environ.get("PORT", "8000")
with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=8) as response:
    health = json.load(response)
if not health["chroma_reachable"]:
    raise SystemExit(1)

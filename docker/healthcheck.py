"""Check API availability and database connectivity, including during ingestion."""
import json
import urllib.request

with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=8) as response:
    health = json.load(response)
if not health["chroma_reachable"]:
    raise SystemExit(1)

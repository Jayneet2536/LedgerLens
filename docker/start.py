"""Wait for Chroma before initializing the API and its automatic ingestion."""
import os
import time

import chromadb


def main():
    deadline = time.monotonic() + 120
    while True:
        try:
            chromadb.HttpClient(
                host=os.environ.get("CHROMA_HOST", "chromadb"),
                port=int(os.environ.get("CHROMA_PORT", "8000")),
            ).heartbeat()
            break
        except Exception as exc:
            if time.monotonic() >= deadline:
                raise RuntimeError("Chroma did not become ready within 120 seconds") from exc
            print("Waiting for Chroma...", flush=True)
            time.sleep(2)

    command = [
        "uvicorn", "api.app:app", "--host", "0.0.0.0",
        "--port", os.environ.get("PORT", "8000"), "--workers", "1",
    ]
    root_path = os.environ.get("ROOT_PATH", "").rstrip("/")
    if root_path:
        command.extend(["--root-path", root_path])
    os.execvp(command[0], command)


if __name__ == "__main__":
    main()

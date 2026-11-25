# vectorstore/databases.py
import copy

import chromadb
from chromadb.errors import NotFoundError
from langchain_chroma import Chroma


class VectorStoreFactory:
    @staticmethod
    def resolve_active_config(config: dict):
        """Restore the last successfully published API index after a restart."""
        active_config = copy.deepcopy(config)
        client = chromadb.HttpClient(host=config["chroma_host"], port=config["chroma_port"])
        try:
            metadata = client.get_collection(config["collection_name"] + "__active").metadata or {}
        except NotFoundError:
            return active_config  # Existing installations use the original collection.
        if metadata.get("active_collection"):
            active_config["collection_name"] = metadata["active_collection"]
            for key in ("chunking_strategy", "chunk_size", "chunk_overlap", "company", "fiscal_year", "doc_type"):
                if key in metadata:
                    active_config[key] = metadata[key]
        return active_config

    @staticmethod
    def publish_index(base_collection_name: str, config: dict):
        """Publish only a complete, validated collection; never persist credentials."""
        client = chromadb.HttpClient(host=config["chroma_host"], port=config["chroma_port"])
        registry = client.get_or_create_collection(base_collection_name + "__active")
        metadata = {"active_collection": config["collection_name"]}
        for key in ("chunking_strategy", "chunk_size", "chunk_overlap", "company", "fiscal_year", "doc_type"):
            if key in config:
                metadata[key] = config[key]
        registry.modify(metadata=metadata)

    @staticmethod
    def delete_index(config: dict):
        client = chromadb.HttpClient(host=config["chroma_host"], port=config["chroma_port"])
        try:
            client.delete_collection(config["collection_name"])
        except NotFoundError:
            pass

    @staticmethod
    def create_index(documents, embedding_model, config: dict):
        if config["vector_store"] == "chromadb":
            chroma_client = chromadb.HttpClient(
                host=config["chroma_host"],
                port=config["chroma_port"]
            )
            collection_name = config["collection_name"]

            # Each ingestion run represents a fresh build of the index for
            # whatever chunking/config is currently active — not an
            # incremental append. Chroma.from_documents() get-or-creates the
            # collection by name and just adds to it if it already exists,
            # with no deduplication (fresh random IDs every time). Without
            # this delete, re-running ingestion — or switching chunking
            # strategies to compare them — silently piles new chunks on top
            # of whatever was already indexed.
            try:
                chroma_client.delete_collection(name=collection_name)
            except Exception:
                pass  # no existing collection yet (first run) — fine

            return Chroma.from_documents(
                documents=documents,
                embedding=embedding_model,
                client=chroma_client,
                collection_name=collection_name
            )
        else:
            raise ValueError("Unsupported vector store")

    @staticmethod
    def get_existing_index(embedding_model, config: dict):
        """Loads the existing database for retrieval without inserting new data."""
        if config["vector_store"] == "chromadb":
            chroma_client = chromadb.HttpClient(
                host=config["chroma_host"],
                port=config["chroma_port"]
            )
            return Chroma(
                client=chroma_client,
                collection_name=config["collection_name"],
                embedding_function=embedding_model
            )
        else:
            raise ValueError("Unsupported vector store")

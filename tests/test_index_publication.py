"""Optional integration test against a dedicated, disposable Chroma server."""
import os
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

import chromadb
from chromadb.errors import NotFoundError
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from api.state import ApiServiceState
from vectorstore.databases import VectorStoreFactory


class LocalEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text):
        return [1.0, 0.0, 0.0]


@unittest.skipUnless(os.getenv("TEST_CHROMA_HOST"), "Requires a dedicated test Chroma server")
class IndexPublicationTests(unittest.TestCase):
    def test_completed_index_is_restored_and_old_collection_is_removed(self):
        config = {
            "collection_name": "reindex_test_" + uuid4().hex,
            "chroma_host": os.environ["TEST_CHROMA_HOST"], "chroma_port": 8000,
            "vector_store": "chromadb", "chunking_strategy": "recursive",
            "chunk_size": 1000, "chunk_overlap": 200, "retrieval_strategy": "standard",
            "top_k_results": 1, "voyage_api_key": "test", "groq_api_key": "test",
        }
        embeddings = LocalEmbeddings()
        client = chromadb.HttpClient(host=config["chroma_host"], port=8000)
        created_names = [config["collection_name"], config["collection_name"] + "__active"]

        def ingest(config):
            return VectorStoreFactory.create_index(
                [Document(page_content="New filing")], embeddings, config
            )

        try:
            VectorStoreFactory.create_index([Document(page_content="Old filing")], embeddings, config)
            with patch("api.state.EmbeddingFactory.get_embedding_model", return_value=embeddings), patch(
                "api.state.ChatGroq", return_value=Mock()
            ):
                state = ApiServiceState(config)
                state.initialize()
                self.assertEqual(state.documents[0].page_content, "Old filing")
                next_config = state.prepare_reindex_config("naive", 800, 100)
                created_names.append(next_config["collection_name"])
                with patch("api.state.run_ingestion", side_effect=ingest):
                    state.run_reindex(next_config)
                self.assertEqual(state.status, "idle", state.status_detail)
                with self.assertRaises(NotFoundError):
                    client.get_collection(config["collection_name"])
                registry = client.get_collection(config["collection_name"] + "__active")
                self.assertNotIn("voyage_api_key", registry.metadata)
                restarted = ApiServiceState(config)
                restarted.initialize()
                self.assertEqual(restarted.config["collection_name"], next_config["collection_name"])
                self.assertEqual(restarted.config["chunking_strategy"], "naive")
                self.assertEqual(restarted.config["chunk_size"], 800)
                self.assertEqual(restarted.documents[0].page_content, "New filing")
                self.assertTrue(restarted.index_loaded)
        finally:
            for name in created_names:
                try:
                    client.delete_collection(name)
                except NotFoundError:
                    pass

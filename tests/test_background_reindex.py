import copy
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from langchain_core.documents import Document

from api.app import app, get_service_state
from api.state import ApiServiceState, NoIndexLoadedError, ReindexInProgressError
from vectorstore.databases import VectorStoreFactory


CONFIG = {
    "collection_name": "test_index", "chroma_host": "unused", "chroma_port": 8000,
    "vector_store": "chromadb", "chunking_strategy": "recursive",
    "chunk_size": 1000, "chunk_overlap": 200, "retrieval_strategy": "standard",
    "top_k_results": 5, "voyage_api_key": "test", "groq_api_key": "test",
    "company": "Test", "fiscal_year": "2025", "doc_type": "10-K",
}


def ready_state():
    state = ApiServiceState(CONFIG)
    state.embedding_model = Mock()
    state.vector_db = Mock()
    state.documents = [Document(page_content="Old filing")]
    state.retriever = Mock(invoke=Mock(return_value=state.documents))
    state.llm = Mock(invoke=Mock(return_value=SimpleNamespace(content="Answer")))
    state.index_loaded = True
    return state


class BackgroundReindexTests(unittest.TestCase):
    def setUp(self):
        self.state = ready_state()
        self.publish = patch.object(VectorStoreFactory, "publish_index").start()
        self.delete = patch.object(VectorStoreFactory, "delete_index").start()
        self.addCleanup(patch.stopall)

    def prepare(self):
        return self.state.prepare_reindex_config("naive", None, None)

    def new_index(self):
        documents = [Document(page_content="New filing")]
        retriever = Mock(invoke=Mock(return_value=documents))
        return Mock(), documents, retriever

    def test_fastapi_background_job_allows_chat_and_rejects_duplicate_job(self):
        started, finish = threading.Event(), threading.Event()

        def ingest(config):
            self.assertNotEqual(config["collection_name"], CONFIG["collection_name"])
            started.set()
            if not finish.wait(5):
                raise RuntimeError("Test job timed out")

        app.dependency_overrides[get_service_state] = lambda: self.state
        self.addCleanup(app.dependency_overrides.clear)
        client = TestClient(app)
        with patch("api.state.run_ingestion", side_effect=ingest), patch.object(
            self.state, "_load_index_and_retriever", return_value=self.new_index()
        ), ThreadPoolExecutor(max_workers=1) as executor:
            job = executor.submit(client.post, "/reindex", json={"chunking_strategy": "naive"})
            try:
                self.assertTrue(started.wait(3))
                response = client.post("/chat", json={"message": "Question"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["sources"][0]["content"], "Old filing")
                self.assertEqual(client.post("/reindex", json={}).status_code, 409)
                self.publish.assert_not_called()
            finally:
                finish.set()
            self.assertEqual(job.result(timeout=3).status_code, 202)
        self.assertEqual(self.state.chat("Question").sources[0].content, "New filing")
        self.assertEqual(self.state.status, "idle")

    def test_inflight_retrieval_keeps_old_collection_until_it_finishes(self):
        started, finish = threading.Event(), threading.Event()

        def retrieve(question):
            started.set()
            if not finish.wait(5):
                raise RuntimeError("Test retrieval timed out")
            return [Document(page_content="Old filing")]

        self.state.retriever.invoke.side_effect = retrieve
        with ThreadPoolExecutor(max_workers=1) as executor:
            chat = executor.submit(self.state.chat, "Question")
            try:
                self.assertTrue(started.wait(3))
                next_config = self.prepare()
                with patch("api.state.run_ingestion"), patch.object(
                    self.state, "_load_index_and_retriever", return_value=self.new_index()
                ):
                    self.state.run_reindex(next_config)
                self.delete.assert_not_called()
                self.assertEqual(self.state.chat("Question").sources[0].content, "New filing")
            finally:
                finish.set()
            self.assertEqual(chat.result(timeout=3).sources[0].content, "Old filing")
        self.delete.assert_called_once_with(CONFIG)

    def test_failed_ingestion_preserves_active_index_and_cleans_staging(self):
        next_config = self.prepare()
        with patch("api.state.run_ingestion", side_effect=RuntimeError("Provider failed")):
            self.state.run_reindex(next_config)
        self.assertEqual(self.state.status, "error")
        self.assertEqual(self.state.status_detail, "Provider failed")
        self.assertEqual(self.state.config, CONFIG)
        self.assertEqual(self.state.chat("Question").sources[0].content, "Old filing")
        self.publish.assert_not_called()
        self.delete.assert_called_once_with(next_config)
        self.assertNotEqual(self.prepare()["collection_name"], next_config["collection_name"])

    def test_empty_index_is_not_published(self):
        next_config = self.prepare()
        with patch("api.state.run_ingestion"), patch.object(
            self.state, "_load_index_and_retriever", return_value=(Mock(), [], None)
        ):
            self.state.run_reindex(next_config)
        self.assertEqual(self.state.status, "error")
        self.assertEqual(self.state.config, CONFIG)
        self.publish.assert_not_called()

    def test_publication_failure_keeps_old_index_and_complete_staging(self):
        next_config = self.prepare()
        self.publish.side_effect = RuntimeError("Database unavailable")
        with patch("api.state.run_ingestion"), patch.object(
            self.state, "_load_index_and_retriever", return_value=self.new_index()
        ):
            self.state.run_reindex(next_config)
        self.assertEqual(self.state.status, "error")
        self.assertEqual(self.state.chat("Question").sources[0].content, "Old filing")
        # A timed-out publication may have committed remotely. Keep the valid collection.
        self.delete.assert_not_called()

    def test_first_ingestion_requires_an_index_before_chat(self):
        self.state.index_loaded = False
        self.prepare()
        with self.assertRaises(NoIndexLoadedError):
            self.state.chat("Question")
        with self.assertRaises(ReindexInProgressError):
            self.prepare()

    def test_retrieval_error_releases_collection_lease(self):
        self.state.retriever.invoke.side_effect = RuntimeError("Retrieval failed")
        with self.assertRaises(RuntimeError):
            self.state.chat("Question")
        self.assertEqual(self.state._readers, {})

    def test_initialize_restores_published_index_configuration(self):
        restored = copy.deepcopy(CONFIG)
        restored.update(collection_name="test_index__completed", chunking_strategy="naive")
        with patch.object(VectorStoreFactory, "resolve_active_config", return_value=restored), patch(
            "api.state.EmbeddingFactory.get_embedding_model"
        ), patch("api.state.ChatGroq"), patch.object(
            self.state, "_load_index_and_retriever", return_value=self.new_index()
        ) as load:
            self.state.initialize()
        self.assertEqual(self.state.config, restored)
        self.assertEqual(load.call_args.args[1], restored)
        self.assertTrue(self.state.index_loaded)


if __name__ == "__main__":
    unittest.main()

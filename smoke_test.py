"""
Smoke tests for the RAG pipeline — run this before wrapping anything in an API.
No RAGAS, no paid LLM judge. Just: does every strategy actually work, do
different strategies behave differently, and does the chatbot admit when it
doesn't know something.

Usage:
    python smoke_test.py                    # run everything
    python smoke_test.py --skip-chunking
    python smoke_test.py --skip-retrieval
    python smoke_test.py --skip-e2e
    python smoke_test.py --skip-cache-review
"""
import argparse
import json
import random
import time
import traceback

from config import CONFIG
from chunking.splitters import ChunkingFactory
from embeddings.models import EmbeddingFactory
from vectorstore.databases import VectorStoreFactory
from retrieval.strategies import RetrieverFactory


# Small inline sample so the chunking sweep is fast/cheap — doesn't need to
# re-parse the full 10-K PDF. Deliberately includes headers + a table so
# markdown/table-aware strategies have something to chew on.
SAMPLE_MARKDOWN = """
# Item 1. Business

## Overview
Amazon.com, Inc. is a company that focuses on e-commerce, cloud computing,
digital streaming, and artificial intelligence. The company was founded in
1994 and is headquartered in Seattle, Washington.

## Segments
The Company has three reportable segments: North America, International,
and AWS. Table 1 below summarizes segment revenue for fiscal year 2025.

| Segment       | Revenue ($B) |
|---------------|--------------|
| North America | 350          |
| International | 140          |
| AWS           | 110          |

## Risk Factors
The Company faces intense competition, and its business is subject to
numerous risks including fluctuations in foreign exchange rates.
"""

# 'table_page' intentionally excluded here — it needs a real PDF path, not a
# raw string, so it isn't a fit for this fast in-memory sweep.
CHUNKING_STRATEGIES = [
    "naive", "recursive", "markdown_structural",
    "markdown_hierarchical", "semantic",
]

RETRIEVAL_STRATEGIES = ["standard", "mmr", "hybrid_rrf", "metadata_filtered", "reranked"]

TEST_QUERY = "What segments does the company report revenue in?"
OFF_TOPIC_QUERY = "What is the capital of France?"

# Rough chars-per-token estimate for English text (no model-specific
# tokenizer needed for a sanity check). Groq's qwen/qwen3.6-27b hit a hard
# 413 at ~10k tokens for a single request (limit: 8000) — this budget
# leaves headroom for the question, prompt scaffolding, and the model's
# own response within that ceiling. Tune MAX_CONTEXT_TOKENS to whatever
# model/tier you're actually running against.
MAX_CONTEXT_TOKENS = 4000
CHARS_PER_TOKEN = 4


def build_bounded_context(retrieved_docs, max_tokens=MAX_CONTEXT_TOKENS):
    """Join retrieved chunks into a context string, stopping once the
    (estimated) token budget is used up. Prefers dropping whole low-ranked
    chunks over truncating mid-sentence — a half-cut chunk hands the model
    an incomplete, potentially misleading fragment instead of just one
    less (lower-relevance) chunk. Assumes retrieved_docs is already ordered
    by relevance, which holds for every current retrieval strategy, so
    what gets dropped is specifically the least-relevant material."""
    max_chars = max_tokens * CHARS_PER_TOKEN
    parts = []
    total_chars = 0
    for doc in retrieved_docs:
        content = doc.page_content
        if total_chars + len(content) <= max_chars:
            parts.append(content)
            total_chars += len(content)
        elif not parts:
            # Even the single highest-ranked chunk alone exceeds the
            # budget — send a truncated version of it rather than nothing.
            parts.append(content[: max_chars - total_chars])
            break
        else:
            # This (lower-ranked) chunk doesn't fit whole. Drop it and
            # stop — everything after it is ranked even lower and won't
            # fit either.
            break
    return "\n\n".join(parts)


def test_chunking_strategies():
    print("\n=== TIER 1: Chunking strategy sanity check ===")
    results = {}
    for strategy in CHUNKING_STRATEGIES:
        test_config = {**CONFIG, "chunking_strategy": strategy}
        try:
            start = time.time()
            chunks = ChunkingFactory.get_chunks(SAMPLE_MARKDOWN, test_config)
            elapsed = time.time() - start

            assert len(chunks) > 0, "produced zero chunks"
            assert all(hasattr(c, "page_content") for c in chunks), "not all Document objects"
            assert all(len(c.page_content.strip()) > 0 for c in chunks), "found an empty chunk"

            print(f"  [PASS] {strategy:22s} -> {len(chunks)} chunks in {elapsed:.2f}s")
            results[strategy] = True
        except Exception as e:
            print(f"  [FAIL] {strategy:22s} -> {type(e).__name__}: {e}")
            traceback.print_exc()
            results[strategy] = False
    return results


def test_retrieval_strategies(vector_db, docs_for_bm25):
    print("\n=== TIER 2: Retrieval strategy sanity check ===")
    results = {}
    previews = {}
    for strategy in RETRIEVAL_STRATEGIES:
        test_config = {**CONFIG, "retrieval_strategy": strategy}
        try:
            start = time.time()
            retriever = RetrieverFactory.get_retriever(vector_db, docs_for_bm25, test_config)
            retrieved = retriever.invoke(TEST_QUERY)
            elapsed = time.time() - start

            assert len(retrieved) > 0, "returned zero documents"
            preview = retrieved[0].page_content[:100].replace("\n", " ")
            print(f"  [PASS] {strategy:18s} -> {len(retrieved)} docs in {elapsed:.2f}s")
            print(f"           top result: {preview!r}")
            results[strategy] = True
            previews[strategy] = preview
        except Exception as e:
            print(f"  [FAIL] {strategy:18s} -> {type(e).__name__}: {e}")
            traceback.print_exc()
            results[strategy] = False

    # Cheap check that strategies aren't all silently returning the same
    # thing (e.g. BM25 not actually contributing to hybrid_rrf).
    unique_previews = len(set(previews.values()))
    if unique_previews == 1 and len(previews) > 1:
        print("  [WARN] Every strategy returned the same top result — "
              "worth double-checking they're actually behaving differently.")

    return results


def test_end_to_end(vector_db, docs_for_bm25):
    """Real retrieve -> generate round trip on one in-scope and one
    out-of-scope query, using whatever retrieval_strategy is set in CONFIG."""
    print("\n=== TIER 4: End-to-end round trip (in-scope + adversarial query) ===")
    try:
        from langchain_groq import ChatGroq
    except ImportError:
        print("  [SKIP] langchain_groq not available.")
        return

    retriever = RetrieverFactory.get_retriever(vector_db, docs_for_bm25, CONFIG)
    llm = ChatGroq(api_key=CONFIG["groq_api_key"], model="qwen/qwen3.6-27b", temperature=0.0)

    for label, query in [("in-scope", TEST_QUERY), ("off-topic", OFF_TOPIC_QUERY)]:
        retrieved_docs = retriever.invoke(query)
        context_str = build_bounded_context(retrieved_docs)
        prompt = f"Context:\n{context_str}\n\nQuestion: {query}\nAnswer:"
        answer = llm.invoke(prompt).content

        print(f"\n  --- {label} query ---")
        print(f"  Q: {query}")
        print(f"  ({len(retrieved_docs)} docs retrieved, context capped to ~{MAX_CONTEXT_TOKENS} tokens)")
        print(f"  A: {answer[:300]}")
        if label == "off-topic":
            hedge_words = ["don't know", "doesn't contain", "no information", "not mentioned", "unable to"]
            if not any(w in answer.lower() for w in hedge_words):
                print("  [WARN] Off-topic answer doesn't look like a hedge/refusal — "
                      "check it isn't hallucinating instead of admitting it doesn't know.")


def eyeball_generation_cache(limit=5):
    """Free manual-review helper: prints a handful of already-generated
    Q/A pairs from generation_cache.json (from your earlier eval runs) so
    you can spot-check quality without spending a single additional API call."""
    print("\n=== TIER 3: Manual spot-check of existing generation_cache.json (free) ===")
    try:
        with open("generation_cache.json", "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("  No generation_cache.json found — run the generation phase first.")
        return

    sample = random.sample(data, min(limit, len(data)))
    for i, item in enumerate(sample, 1):
        print(f"\n  --- Sample {i}/{len(sample)} ---")
        print(f"  Q: {item['question']}")
        print(f"  A: {item['answer'][:300]}")
        print(f"  Ground truth: {item['ground_truth'][:200]}")
        print(f"  # retrieved contexts: {len(item['contexts'])}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-chunking", action="store_true")
    parser.add_argument("--skip-retrieval", action="store_true")
    parser.add_argument("--skip-e2e", action="store_true")
    parser.add_argument("--skip-cache-review", action="store_true")
    args = parser.parse_args()

    chunk_results, retrieval_results = {}, {}

    if not args.skip_chunking:
        chunk_results = test_chunking_strategies()

    vector_db, all_docs = None, None
    if not args.skip_retrieval or not args.skip_e2e:
        print("\nLoading existing vector index (run main.py first if this fails)...")
        embeddings = EmbeddingFactory.get_embedding_model(CONFIG)
        vector_db = VectorStoreFactory.get_existing_index(embeddings, CONFIG)

        from langchain_core.documents import Document
        chroma_data = vector_db.get()
        all_docs = [
            Document(page_content=text, metadata=meta or {})
            for text, meta in zip(chroma_data["documents"], chroma_data["metadatas"])
        ]

    if not args.skip_retrieval:
        retrieval_results = test_retrieval_strategies(vector_db, all_docs)

    if not args.skip_cache_review:
        eyeball_generation_cache()

    if not args.skip_e2e:
        test_end_to_end(vector_db, all_docs)

    print("\n=== SUMMARY ===")
    for name, results in [("Chunking", chunk_results), ("Retrieval", retrieval_results)]:
        if results:
            passed = sum(results.values())
            status = "OK" if passed == len(results) else "CHECK FAILURES ABOVE"
            print(f"  {name}: {passed}/{len(results)} strategies passed — {status}")


if __name__ == "__main__":
    main()
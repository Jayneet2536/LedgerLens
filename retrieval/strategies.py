# retrieval/strategies.py
from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder


class RetrieverFactory:
    @staticmethod
    def get_retriever(vector_db, documents_for_keyword_search, config: dict):
        strategy = config["retrieval_strategy"]
        k = config["top_k_results"]

        if strategy == "standard":
            # Basic Vector Search (Cosine Similarity)
            return vector_db.as_retriever(search_kwargs={"k": k})

        elif strategy == "mmr":
            # Max Marginal Relevance (Diversity)
            return vector_db.as_retriever(
                search_type="mmr",
                search_kwargs={"k": k, "fetch_k": 20, "lambda_mult": 0.5}
            )

        elif strategy == "hybrid_rrf":
            # Hybrid Search with Reciprocal Rank Fusion
            vector_retriever = vector_db.as_retriever(search_kwargs={"k": k})

            keyword_retriever = BM25Retriever.from_documents(documents_for_keyword_search)
            keyword_retriever.k = k

            ensemble_retriever = EnsembleRetriever(
                retrievers=[vector_retriever, keyword_retriever],
                weights=[0.5, 0.5]
            )
            return ensemble_retriever

        elif strategy == "metadata_filtered":
            # Pulled from config instead of hardcoded, so this strategy
            # works for whatever document you point the pipeline at without
            # editing this file.
            return vector_db.as_retriever(
                search_kwargs={"k": k, "filter": {"company": config["company"]}}
            )

        elif strategy == "reranked":
            model = HuggingFaceCrossEncoder(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2")
            compressor = CrossEncoderReranker(model=model, top_n=k)
            # Fetch a wider candidate pool than we need so reranking has
            # something to work with. Guards against top_n > fetch_k if
            # top_k_results is ever configured above the old hardcoded 20.
            fetch_k = max(20, k * 4)
            base_retriever = vector_db.as_retriever(search_kwargs={"k": fetch_k})
            return ContextualCompressionRetriever(
                base_compressor=compressor, base_retriever=base_retriever
            )

        else:
            raise ValueError(f"Unknown retrieval strategy: {strategy}")
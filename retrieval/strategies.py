# retrieval/strategies.py
from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever

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
            # 1. Initialize the Dense Retriever (Voyage AI Vectors)
            vector_retriever = vector_db.as_retriever(search_kwargs={"k": k})
            
            # 2. Initialize the Sparse Retriever (BM25 Keyword Search)
            keyword_retriever = BM25Retriever.from_documents(documents_for_keyword_search)
            keyword_retriever.k = k
            
            # 3. Fuse them using the EnsembleRetriever (which uses RRF by default)
            ensemble_retriever = EnsembleRetriever(
                retrievers=[vector_retriever, keyword_retriever],
                weights=[0.5, 0.5] # Weigh both engines equally
            )
            return ensemble_retriever
            
        else:
            raise ValueError(f"Unknown retrieval strategy: {strategy}")
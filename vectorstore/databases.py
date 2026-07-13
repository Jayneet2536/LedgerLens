# vectorstore/databases.py
import chromadb
from langchain_chroma import Chroma

class VectorStoreFactory:
    @staticmethod
    def create_index(documents, embedding_model, config: dict):
        if config["vector_store"] == "chromadb":
            chroma_client = chromadb.HttpClient(
                host=config["chroma_host"], 
                port=config["chroma_port"]
            )
            return Chroma.from_documents(
                documents=documents,
                embedding=embedding_model,
                client=chroma_client,
                collection_name="financial_10k_collection"
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
                collection_name="financial_10k_collection",
                embedding_function=embedding_model
            )
        else:
            raise ValueError("Unsupported vector store")
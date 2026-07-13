from config import CONFIG
from chunking.splitters import ChunkingFactory
from embeddings.models import EmbeddingFactory
from vectorstore.databases import VectorStoreFactory
from langchain_community.document_loaders import UnstructuredPDFLoader

def run_ingestion():
    print(f"***Ingestion: {CONFIG['chunking_strategy']}***")
    
    #Parse PDF using Unstructured
    print("Parsing PDF...")
    loader = UnstructuredPDFLoader(CONFIG["pdf_path"], mode="elements")
    docs = loader.load()
    raw_markdown = "\n\n".join([doc.page_content for doc in docs])
    
    #Chunking 
    print("Chunking...")
    chunks = ChunkingFactory.get_chunks(raw_markdown, CONFIG)
    print(f"Generated {len(chunks)} document chunks.")
    
    #Embedding Selection
    print("Initializing embedding model...")
    embeddings = EmbeddingFactory.get_embedding_model(CONFIG)
    
    #Indexing
    print(f"Indexing chunks inside {CONFIG['vector_store']}...")
    vector_db = VectorStoreFactory.create_index(chunks, embeddings, CONFIG)
    
    print("***Ingestion Complete!***")

if __name__ == "__main__":
    run_ingestion()
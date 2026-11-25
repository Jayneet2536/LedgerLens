from config import CONFIG
from chunking.splitters import ChunkingFactory
from embeddings.models import EmbeddingFactory
from vectorstore.databases import VectorStoreFactory
from langchain_community.document_loaders import UnstructuredPDFLoader


def run_ingestion(config: dict = None):
    active_config = config or CONFIG
    print(f"***Ingestion: {active_config['chunking_strategy']}***")

    # Parse PDF using Unstructured — once. The parsed elements are reused
    # below for the 'table_page' strategy instead of re-parsing the PDF a
    # second time.
    print("Parsing PDF...")
    loader = UnstructuredPDFLoader(active_config["pdf_path"], mode="elements")
    docs = loader.load()
    raw_markdown = "\n\n".join([doc.page_content for doc in docs])

    # Chunking
    print("Chunking...")
    chunks = ChunkingFactory.get_chunks(
        raw_markdown,
        active_config,
        pdf_path=active_config["pdf_path"],
        elements=docs,
    )
    print(f"Generated {len(chunks)} document chunks.")

    # Metadata Injection — pulled from CONFIG, so pointing this pipeline at
    # a different document only requires editing config.py.
    for chunk in chunks:
        chunk.metadata.update({
            "company": active_config["company"],
            "fiscal_year": active_config["fiscal_year"],
            "doc_type": active_config["doc_type"],
        })

    # Embedding Selection
    print("Initializing embedding model...")
    embeddings = EmbeddingFactory.get_embedding_model(active_config)

    # Indexing
    print(f"Indexing chunks inside {active_config['vector_store']}...")
    vector_db = VectorStoreFactory.create_index(chunks, embeddings, active_config)

    print("***Ingestion Complete!***")
    return vector_db


if __name__ == "__main__":
    vector_db = run_ingestion()
    print(f"\nIndexed chunks: {vector_db._collection.count()}")

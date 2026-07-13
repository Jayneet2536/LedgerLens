# retrieval_main.py
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from config import CONFIG
from embeddings.models import EmbeddingFactory
from vectorstore.databases import VectorStoreFactory
from retrieval.strategies import RetrieverFactory

def execute_retrieval():
    print(f"--- Launching Retrieval with Strategy: {CONFIG['retrieval_strategy']} ---")
    
    # 1. Initialize Models and Database
    llm = ChatGroq(api_key=CONFIG["groq_api_key"], model="openai/gpt-oss-120b", temperature=0.0)
    embeddings = EmbeddingFactory.get_embedding_model(CONFIG)
    vector_db = VectorStoreFactory.get_existing_index(embeddings, CONFIG)
    
    print("Fetching existing chunks from ChromaDB to initialize BM25...")
    # PULL ALL DOCS DIRECTLY FROM DOCKER
    from langchain_core.documents import Document
    chroma_data = vector_db.get()
    
    # Reconstruct standard LangChain Document objects from the database data
    all_docs = [
        Document(page_content=text, metadata=meta or {}) 
        for text, meta in zip(chroma_data['documents'], chroma_data['metadatas'])
    ]
    print(f"Loaded {len(all_docs)} chunks into the BM25 Keyword engine.")

    # 2. Dynamic Retriever Selection via Factory
    retriever = RetrieverFactory.get_retriever(vector_db, all_docs, CONFIG)

    # 3. Define the Prompt
    template = """You are a senior financial analyst. Answer the question based ONLY on the following context.
    Context: {context}
    Question: {question}
    Answer:"""
    prompt = ChatPromptTemplate.from_template(template)

    # 4. Build LCEL Chain
    rag_chain = (
        {"context": retriever | (lambda docs: "\n\n".join(doc.page_content for doc in docs)), 
         "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    
    # 5. Execute
    question = "What are the macroeconomic risks?"
    answer = rag_chain.invoke(question)
    print(f"Answer:\n{answer}")

if __name__ == "__main__":
    execute_retrieval()
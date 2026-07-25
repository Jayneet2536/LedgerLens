from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter
from langchain_core.documents import Document
from langchain_experimental.text_splitter import SemanticChunker
from embeddings.models import EmbeddingFactory
from langchain_community.document_loaders import UnstructuredPDFLoader


class ChunkingFactory:

    @staticmethod
    def _split_by_markdown_headers(raw_markdown_text: str, headers_to_split_on: list, size: int, overlap: int):
        """Shared by markdown_structural and markdown_hierarchical — they only
        differ in which header levels/labels they split on."""
        md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on, strip_headers=False)
        md_splits = md_splitter.split_text(raw_markdown_text)

        recursive_splitter = RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap)
        return recursive_splitter.split_documents(md_splits)

    @staticmethod
    def get_chunks(raw_markdown_text: str, config: dict, pdf_path: str = None, elements: list = None):
        """
        elements: optional pre-parsed list of Documents from
        UnstructuredPDFLoader(mode="elements"). Pass this in from main.py
        (which already loads the PDF once to build raw_markdown_text) so the
        'table_page' strategy doesn't parse the same PDF a second time.
        Falls back to loading from pdf_path if elements isn't provided.
        """
        strategy = config["chunking_strategy"]
        size = config["chunk_size"]
        overlap = config["chunk_overlap"]

        if strategy == "naive" or strategy == "recursive":
            splitter = RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap)
            # Wraps plain text into standard LangChain Document objects
            return splitter.create_documents([raw_markdown_text])

        elif strategy == "markdown_structural":
            headers_to_split_on = [("#", "Part"), ("##", "Item"), ("###", "Topic")]
            return ChunkingFactory._split_by_markdown_headers(raw_markdown_text, headers_to_split_on, size, overlap)

        elif strategy == "markdown_hierarchical":
            headers_to_split_on = [("#", "Header 1"), ("##", "Header 2"), ("###", "Header 3"), ("####", "Header 4")]
            return ChunkingFactory._split_by_markdown_headers(raw_markdown_text, headers_to_split_on, size, overlap)

        elif strategy == "semantic":
            embeddings = EmbeddingFactory.get_embedding_model(config)
            semantic_chunker = SemanticChunker(embeddings)
            return semantic_chunker.create_documents([raw_markdown_text])

        elif strategy == "table_page":
            if elements is not None:
                docs = elements
            else:
                if not pdf_path:
                    raise ValueError("table_page strategy needs either 'elements' or 'pdf_path'")
                loader = UnstructuredPDFLoader(pdf_path, mode="elements")
                docs = loader.load()

            final_chunks = []
            current_page_text = []
            current_page_num = None  # None until we've seen the first element

            def flush_page(page_num_for_metadata):
                """Split whatever body text has accumulated for the given
                page into size-limited chunks, tagged with that page number."""
                if not current_page_text:
                    return []
                page_content = "\n\n".join(current_page_text)
                splitter = RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap)
                return splitter.create_documents(
                    [page_content],
                    metadatas=[{"page_number": page_num_for_metadata}],
                )

            for doc in docs:
                element_type = doc.metadata.get("category", "")
                page_num = doc.metadata.get("page_number", 1)

                # Page boundary changed: flush the PREVIOUS page's text (if
                # any) and advance the tracker regardless of whether there
                # was text to flush. The original version only advanced
                # current_page_num inside the "if current_page_text" branch,
                # so a page containing only tables (no body text) would never
                # update the tracker and subsequent page boundaries would be
                # computed against a stale page number.
                if current_page_num is not None and page_num != current_page_num:
                    final_chunks.extend(flush_page(current_page_num))
                    current_page_text = []
                current_page_num = page_num

                if element_type.lower() == "table":
                    doc.metadata["element_type"] = "table"
                    final_chunks.append(doc)
                else:
                    current_page_text.append(doc.page_content)

            # Flush whatever's left after the loop ends
            final_chunks.extend(flush_page(current_page_num))

            return final_chunks

        else:
            raise ValueError(f"Unknown chunking strategy: {strategy}")
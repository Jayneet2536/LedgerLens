from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter

class ChunkingFactory:
    @staticmethod
    def get_chunks(raw_markdown_text: str, config: dict):
        strategy = config["chunking_strategy"]
        size = config["chunk_size"]
        overlap = config["chunk_overlap"]
        
        if strategy == "naive" or strategy == "recursive":
            splitter = RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap)
            # Wraps plain text into standard LangChain Document objects
            return splitter.create_documents([raw_markdown_text])
            
        elif strategy == "markdown_structural":
            headers_to_split_on = [("#", "Part"), ("##", "Item"), ("###", "Topic")]
            md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on, strip_headers=False)
            md_splits = md_splitter.split_text(raw_markdown_text)
            
            # Chain with size limiter
            recursive_splitter = RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap)
            return recursive_splitter.split_documents(md_splits)
            
        else:
            raise ValueError(f"Unknown chunking strategy: {strategy}")
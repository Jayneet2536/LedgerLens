from langchain_voyageai import VoyageAIEmbeddings

class EmbeddingFactory:
    @staticmethod
    def get_embedding_model(config: dict):
        return VoyageAIEmbeddings(
            voyage_api_key=config["voyage_api_key"], 
            model="voyage-finance-2" 
        )
        
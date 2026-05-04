from llama_index.core.embeddings import BaseEmbedding

from llm_code_cache.vector.embedding_config import EmbeddingConfig
from llm_code_cache.vector.enums import EmbedProvider


def make_embed_model(config: EmbeddingConfig) -> BaseEmbedding:
    if config.provider == EmbedProvider.HUGGINGFACE:
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding
        return HuggingFaceEmbedding(model_name=config.model_name)
    if config.provider == EmbedProvider.BEDROCK:
        from llama_index.embeddings.bedrock import BedrockEmbedding
        return BedrockEmbedding(
            model_name=config.model_name,
            region_name=config.aws_region,
        )
    raise ValueError(f"Unknown embedding provider: {config.provider}")

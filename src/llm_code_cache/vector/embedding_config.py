from dataclasses import dataclass

from llm_code_cache.vector.enums import EmbedProvider


@dataclass
class EmbeddingConfig:
    provider: EmbedProvider
    model_name: str
    aws_region: str | None = None

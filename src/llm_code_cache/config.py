"""Top-level configuration loaded from environment variables.

Bundles graph, vector, and embedding configs into a single object the MCP
server (and other entry points) can construct once at startup.
"""
import os
from dataclasses import dataclass

from llm_code_cache.graph import GraphConfig
from llm_code_cache.vector import EmbedProvider, VectorConfig
from llm_code_cache.vector.embedding_config import EmbeddingConfig

DEFAULT_TABLE_NAME = "code_chunks"
DEFAULT_HF_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_HF_EMBED_DIM = 384


@dataclass
class AppConfig:
    graph: GraphConfig
    vector: VectorConfig
    embedding: EmbeddingConfig
    embed_dim: int

    @classmethod
    def from_env(cls) -> AppConfig:
        return cls(
            graph=_graph_from_env(),
            vector=_vector_from_env(),
            embedding=_embedding_from_env(),
            embed_dim=int(os.environ.get("EMBED_DIM", DEFAULT_HF_EMBED_DIM)),
        )


def _graph_from_env() -> GraphConfig:
    return GraphConfig(
        uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        user=os.environ.get("NEO4J_USER", "neo4j"),
        password=os.environ.get("NEO4J_PASSWORD", "password"),
        database=os.environ.get("NEO4J_DB", "neo4j"),
    )


def _vector_from_env() -> VectorConfig:
    return VectorConfig(
        database=os.environ.get("PG_DATABASE", "llmcache"),
        host=os.environ.get("PG_HOST", "localhost"),
        port=int(os.environ.get("PG_PORT", "5432")),
        user=os.environ.get("PG_USER", "llmcache"),
        password=os.environ.get("PG_PASSWORD", "password"),
        table_name=os.environ.get("PG_TABLE_NAME", DEFAULT_TABLE_NAME),
    )


def _embedding_from_env() -> EmbeddingConfig:
    provider = EmbedProvider(os.environ.get("EMBED_PROVIDER", EmbedProvider.HUGGINGFACE.value))
    return EmbeddingConfig(
        provider=provider,
        model_name=os.environ.get("EMBED_MODEL_NAME", DEFAULT_HF_MODEL),
        aws_region=os.environ.get("AWS_REGION"),
    )

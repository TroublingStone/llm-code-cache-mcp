import pytest

from llm_code_cache.config import AppConfig
from llm_code_cache.vector.enums import EmbedProvider


@pytest.fixture
def clean_env(monkeypatch):
    for var in [
        "NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD", "NEO4J_DB",
        "PG_DATABASE", "PG_HOST", "PG_PORT", "PG_USER", "PG_PASSWORD", "PG_TABLE_NAME",
        "EMBED_PROVIDER", "EMBED_MODEL_NAME", "EMBED_DIM", "AWS_REGION",
    ]:
        monkeypatch.delenv(var, raising=False)


def test_from_env_uses_defaults_when_unset(clean_env):
    cfg = AppConfig.from_env()
    assert cfg.graph.uri == "bolt://localhost:7687"
    assert cfg.graph.user == "neo4j"
    assert cfg.graph.database == "neo4j"
    assert cfg.vector.host == "localhost"
    assert cfg.vector.port == 5432
    assert cfg.vector.table_name == "code_chunks"
    assert cfg.embedding.provider is EmbedProvider.HUGGINGFACE
    assert cfg.embedding.model_name == "BAAI/bge-small-en-v1.5"
    assert cfg.embed_dim == 384


def test_from_env_reads_overrides(clean_env, monkeypatch):
    monkeypatch.setenv("NEO4J_URI", "bolt://example:9999")
    monkeypatch.setenv("PG_PORT", "6543")
    monkeypatch.setenv("PG_TABLE_NAME", "my_chunks")
    monkeypatch.setenv("EMBED_PROVIDER", "bedrock")
    monkeypatch.setenv("EMBED_MODEL_NAME", "amazon.titan-embed-text-v2:0")
    monkeypatch.setenv("EMBED_DIM", "1024")
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    cfg = AppConfig.from_env()

    assert cfg.graph.uri == "bolt://example:9999"
    assert cfg.vector.port == 6543
    assert cfg.vector.table_name == "my_chunks"
    assert cfg.embedding.provider is EmbedProvider.BEDROCK
    assert cfg.embedding.model_name == "amazon.titan-embed-text-v2:0"
    assert cfg.embedding.aws_region == "us-east-1"
    assert cfg.embed_dim == 1024


def test_from_env_unknown_provider_raises(clean_env, monkeypatch):
    monkeypatch.setenv("EMBED_PROVIDER", "openai")
    with pytest.raises(ValueError):
        AppConfig.from_env()

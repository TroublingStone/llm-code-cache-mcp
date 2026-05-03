import os
import socket
from dataclasses import dataclass

import psycopg2
import pytest

from llm_code_cache.vector.store import VectorStore

TEST_TABLE_NAME = "test_vectors"
EMBED_DIM = 384


@dataclass
class PGConfig:
    database: str
    host: str
    port: int
    user: str
    password: str
    table_name: str


@pytest.fixture(scope="session")
def pg_config() -> PGConfig:
    return PGConfig(
        database=os.environ.get("PG_DATABASE", "llmcache"),
        host=os.environ.get("PG_HOST", "localhost"),
        port=int(os.environ.get("PG_PORT", "5432")),
        user=os.environ.get("PG_USER", "llmcache"),
        password=os.environ.get("PG_PASSWORD", "password"),
        table_name=TEST_TABLE_NAME,
    )


@pytest.fixture(scope="session")
def _postgres_available(pg_config) -> None:
    """Skip the whole integration suite if postgres is unreachable."""
    try:
        with socket.create_connection((pg_config.host, pg_config.port), timeout=2):
            pass
    except OSError as exc:
        pytest.skip(f"postgres not running at {pg_config.host}:{pg_config.port}: {exc}")


@pytest.fixture(scope="session")
def embed_model():
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding

    return HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")


def _drop_test_table(pg_config: PGConfig) -> None:
    # llama-index prefixes table names with "data_".
    full_name = f"data_{pg_config.table_name}"
    conn = psycopg2.connect(
        dbname=pg_config.database,
        host=pg_config.host,
        port=pg_config.port,
        user=pg_config.user,
        password=pg_config.password,
    )
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f'DROP TABLE IF EXISTS "{full_name}"')
    finally:
        conn.close()


@pytest.fixture
def vector_store(pg_config, embed_model, _postgres_available):
    _drop_test_table(pg_config)
    store = VectorStore(config=pg_config, embed_dim=EMBED_DIM, embed_model=embed_model)
    store.connect()
    yield store
    _drop_test_table(pg_config)

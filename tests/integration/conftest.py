import os
import socket
from pathlib import Path
from textwrap import dedent
from urllib.parse import urlparse

import psycopg2
import pytest

from llm_code_cache.graph import GraphConfig
from llm_code_cache.graph.store import GraphStore
from llm_code_cache.ingest.parser import parse_repo
from llm_code_cache.vector import VectorConfig
from llm_code_cache.vector.store import VectorStore

TEST_TABLE_NAME = "test_vectors"
EMBED_DIM = 384

SAMPLE_REPO_NAME = "test-repo"

SAMPLE_FILES: dict[str, str] = {
    "src/auth.py": dedent(
        '''
        from src.utils import sha256_hex

        def authenticate(token: str) -> bool:
            """Validate a JWT token by recomputing its signature."""
            digest = sha256_hex(token)
            return verify_signature(digest)


        def verify_signature(digest: str) -> bool:
            """Compare a digest against the configured trusted signature."""
            return bool(digest)
        '''
    ).lstrip(),
    "src/utils.py": dedent(
        '''
        import hashlib


        def sha256_hex(data: str) -> str:
            """Return the SHA-256 hex digest of a string."""
            return hashlib.sha256(data.encode()).hexdigest()
        '''
    ).lstrip(),
    "src/repo.py": dedent(
        '''
        from src.auth import authenticate


        class BaseRepo:
            """Abstract base class for all persistence repositories."""


        class UserRepo(BaseRepo):
            """Persistence layer for user records in the database."""

            def find_by_token(self, token: str):
                """Look up a user account by their authentication token."""
                if authenticate(token):
                    return {"ok": True}
                return None
        '''
    ).lstrip(),
}


@pytest.fixture
def sample_repo_name() -> str:
    return SAMPLE_REPO_NAME


@pytest.fixture
def sample_repo(tmp_path) -> tuple[Path, list[Path]]:
    paths: list[Path] = []
    for rel, content in SAMPLE_FILES.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        paths.append(p)
    return tmp_path, paths


@pytest.fixture
def parsed_sample_repo(sample_repo):
    root, paths = sample_repo
    return parse_repo(paths, root)



@pytest.fixture(scope="session")
def pg_config() -> VectorConfig:
    return VectorConfig(
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


def _drop_test_table(pg_config: VectorConfig) -> None:
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



@pytest.fixture(scope="session")
def graph_config() -> GraphConfig:
    return GraphConfig(
        uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        user=os.environ.get("NEO4J_USER", "neo4j"),
        password=os.environ.get("NEO4J_PASSWORD", "password"),
        database=os.environ.get("NEO4J_DB", "neo4j"),
    )


@pytest.fixture(scope="session")
def _neo4j_available(graph_config) -> None:
    parsed = urlparse(graph_config.uri)
    host = parsed.hostname or "localhost"
    port = parsed.port or 7687
    try:
        with socket.create_connection((host, port), timeout=2):
            pass
    except OSError as exc:
        pytest.skip(f"neo4j not running at {host}:{port}: {exc}")


def _wipe_neo4j(store: GraphStore, database: str) -> None:
    with store.driver.session(database=database) as session:
        session.execute_write(lambda tx: tx.run("MATCH (n) DETACH DELETE n"))


@pytest.fixture
def graph_store(graph_config, _neo4j_available):
    store = GraphStore(graph_config)
    store.connect()
    _wipe_neo4j(store, graph_config.database)
    yield store
    _wipe_neo4j(store, graph_config.database)
    store.close()

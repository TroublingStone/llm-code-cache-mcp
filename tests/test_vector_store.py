from unittest.mock import MagicMock, patch

import pytest

from llm_code_cache.ingest.enums import NodeKind
from llm_code_cache.ingest.models import Metadata
from llm_code_cache.vector.models import VectorHit
from llm_code_cache.vector.store import VectorStore


@pytest.fixture
def pg_config():
    cfg = MagicMock()
    cfg.database = "testdb"
    cfg.host = "localhost"
    cfg.port = 5432
    cfg.user = "u"
    cfg.password = "p"
    cfg.table_name = "vectors"
    return cfg


@pytest.fixture
def embed_model():
    return MagicMock(name="embed_model")


@pytest.fixture
def store(pg_config, embed_model):
    return VectorStore(config=pg_config, embed_dim=384, embed_model=embed_model)


@pytest.fixture
def connected_store(store):
    """A VectorStore with PGVectorStore + VectorStoreIndex patched out."""
    with patch("llm_code_cache.vector.store.PGVectorStore") as pg_cls, patch(
        "llm_code_cache.vector.store.VectorStoreIndex"
    ) as index_cls:
        fake_index = MagicMock(name="VectorStoreIndex")
        index_cls.from_vector_store.return_value = fake_index
        pg_cls.from_params.return_value = MagicMock(name="PGVectorStore")

        store.connect()
        yield store, pg_cls, index_cls, fake_index


def test_connect_passes_config_to_pgvector(store, pg_config):
    with patch("llm_code_cache.vector.store.PGVectorStore") as pg_cls:
        store.connect()

    pg_cls.from_params.assert_called_once_with(
        database=pg_config.database,
        host=pg_config.host,
        port=pg_config.port,
        user=pg_config.user,
        password=pg_config.password,
        table_name=pg_config.table_name,
        embed_dim=384,
    )


def test_connection_property_raises_before_connect(store):
    with pytest.raises(RuntimeError, match="connect"):
        _ = store.connection


def test_serialize_metadata_shape(store):
    md = Metadata(
        repo="r",
        path="src/a.py",
        qualified_name="r.src.a.fn",
        name="fn",
        kind=NodeKind.FUNCTION,
        start_line=1,
        end_line=5,
    )
    out = store._serialize_metadata(md)

    assert out == {
        "qualified_name": "r.src.a.fn",
        "repo": "r",
        "path": "src/a.py",
        "name": "fn",
        "kind": "function",
        "start_line": 1,
        "end_line": 5,
    }


def test_chunk_to_text_node_uses_qualified_name_as_id(store, sample_chunks):
    chunk = sample_chunks[0]
    text_node = store._chunk_to_text_node(chunk)

    assert text_node.id_ == chunk.metadata.qualified_name
    assert text_node.text == chunk.embed_text
    assert text_node.metadata == store._serialize_metadata(chunk.metadata)


def test_upsert_chunks_empty_short_circuits(connected_store):
    store, _pg_cls, _index_cls, fake_index = connected_store

    store.upsert_chunks([])

    fake_index.insert_nodes.assert_not_called()


def test_upsert_chunks_calls_insert_nodes(connected_store, sample_chunks):
    store, _pg_cls, _index_cls, fake_index = connected_store

    store.upsert_chunks(sample_chunks)

    fake_index.insert_nodes.assert_called_once()
    nodes_arg = fake_index.insert_nodes.call_args.args[0]
    assert len(nodes_arg) == len(sample_chunks)
    assert {n.id_ for n in nodes_arg} == {c.metadata.qualified_name for c in sample_chunks}


def test_get_retriever_caches_per_top_k(connected_store):
    store, _pg_cls, _index_cls, fake_index = connected_store
    fake_index.as_retriever.side_effect = [MagicMock(name="r5"), MagicMock(name="r10")]

    r_a = store._get_retriever(5)
    r_b = store._get_retriever(5)
    r_c = store._get_retriever(10)

    assert r_a is r_b
    assert r_c is not r_a
    calls = fake_index.as_retriever.call_args_list
    assert len(calls) == 2
    assert calls[0].kwargs == {"similarity_top_k": 5}
    assert calls[1].kwargs == {"similarity_top_k": 10}


def test_search_maps_results_to_vector_hits(connected_store):
    store, _pg_cls, _index_cls, fake_index = connected_store

    fake_node = MagicMock()
    fake_node.metadata = {
        "qualified_name": "r.src.a.fn",
        "repo": "r",
        "path": "src/a.py",
        "name": "fn",
        "kind": "function",
        "start_line": 1,
        "end_line": 5,
    }
    fake_node.score = 0.91
    fake_node.node.get_content.return_value = "def fn(): ..."

    fake_retriever = MagicMock()
    fake_retriever.retrieve.return_value = [fake_node]
    fake_index.as_retriever.return_value = fake_retriever

    hits = store.search("query", top_k=3)

    fake_retriever.retrieve.assert_called_once_with("query")
    assert len(hits) == 1
    hit = hits[0]
    assert isinstance(hit, VectorHit)
    assert hit.qualified_name == "r.src.a.fn"
    assert hit.score == 0.91
    assert hit.kind == NodeKind.FUNCTION
    assert hit.source == "def fn(): ..."


def test_vector_hit_from_node():
    fake_node = MagicMock()
    fake_node.metadata = {
        "qualified_name": "r.src.b.Klass",
        "repo": "r",
        "path": "src/b.py",
        "name": "Klass",
        "kind": "class",
        "start_line": 2,
        "end_line": 8,
    }
    fake_node.score = 0.42
    fake_node.node.get_content.return_value = "class Klass: ..."

    hit = VectorHit.from_node(fake_node)

    assert hit.qualified_name == "r.src.b.Klass"
    assert hit.score == 0.42
    assert hit.repo == "r"
    assert hit.path == "src/b.py"
    assert hit.name == "Klass"
    assert hit.kind == NodeKind.CLASS
    assert hit.start_line == 2
    assert hit.end_line == 8
    assert hit.source == "class Klass: ..."

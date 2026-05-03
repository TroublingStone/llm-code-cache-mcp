import pytest

from llm_code_cache.ingest.enums.node_kind import NodeKind
from llm_code_cache.vector.models import VectorHit

pytestmark = pytest.mark.integration


def test_connect_succeeds(vector_store):
    assert vector_store.connection is not None


def test_upsert_then_search_jwt(vector_store, sample_chunks):
    vector_store.upsert_chunks(sample_chunks)

    hits = vector_store.search("JWT token validation", top_k=2)

    assert len(hits) >= 1
    assert hits[0].qualified_name.endswith(".authenticate")


def test_upsert_then_search_user_repo(vector_store, sample_chunks):
    vector_store.upsert_chunks(sample_chunks)

    hits = vector_store.search("database user lookup", top_k=2)

    assert len(hits) >= 1
    assert hits[0].qualified_name.endswith(".UserRepository")


def test_vector_hit_fields_populated(vector_store, sample_chunks):
    vector_store.upsert_chunks(sample_chunks)

    hits = vector_store.search("hash digest", top_k=1)

    assert len(hits) == 1
    hit = hits[0]
    assert isinstance(hit, VectorHit)
    assert hit.qualified_name == "myrepo.src.utils.compute_hash"
    assert hit.repo == "myrepo"
    assert hit.path == "src/utils.py"
    assert hit.name == "compute_hash"
    assert hit.kind == NodeKind.FUNCTION
    assert hit.start_line == 1
    assert hit.end_line == 4
    assert hit.score > 0
    assert hit.source

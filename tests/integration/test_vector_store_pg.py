import pytest

from llm_code_cache.ingest.chunker import chunk_nodes
from llm_code_cache.ingest.enums import NodeKind
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


# --- full ingest pipeline tests (parse_repo -> chunk_nodes -> upsert -> search) ---


def test_pipeline_only_embeddable_kinds_are_chunked(parsed_sample_repo, sample_repo_name):
    chunks = list(chunk_nodes(parsed_sample_repo.nodes, sample_repo_name))

    # File nodes are not embeddable; Function/Method/Class are.
    kinds = {c.metadata.kind for c in chunks}
    assert NodeKind.FILE not in kinds
    assert kinds <= {NodeKind.FUNCTION, NodeKind.METHOD, NodeKind.CLASS}
    qns = {c.metadata.qualified_name for c in chunks}
    assert {
        "src.auth.authenticate",
        "src.auth.verify_signature",
        "src.utils.sha256_hex",
        "src.repo.BaseRepo",
        "src.repo.UserRepo",
        "src.repo.UserRepo.find_by_token",
    } == qns


def test_pipeline_search_finds_correct_top_hit(vector_store, parsed_sample_repo, sample_repo_name):
    chunks = list(chunk_nodes(parsed_sample_repo.nodes, sample_repo_name))
    vector_store.upsert_chunks(chunks)

    hits = vector_store.search("validate JWT token signature", top_k=3)
    assert hits[0].qualified_name == "src.auth.authenticate"

    hits = vector_store.search("SHA-256 hex digest of a string", top_k=3)
    assert hits[0].qualified_name == "src.utils.sha256_hex"

    hits = vector_store.search("look up user account by authentication token", top_k=3)
    assert hits[0].qualified_name == "src.repo.UserRepo.find_by_token"


def test_pipeline_idempotent_reupsert_does_not_duplicate(vector_store, parsed_sample_repo, sample_repo_name):
    chunks = list(chunk_nodes(parsed_sample_repo.nodes, sample_repo_name))

    vector_store.upsert_chunks(chunks)
    vector_store.upsert_chunks(chunks)

    hits = vector_store.search("authenticate user", top_k=10)
    qns = [h.qualified_name for h in hits]
    # Node id_= qualified_name; second upsert overwrites, never duplicates.
    assert len(qns) == len(set(qns))

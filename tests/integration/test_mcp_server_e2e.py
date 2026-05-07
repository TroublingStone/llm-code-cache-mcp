"""End-to-end MCP server tests against real Neo4j and pgvector.

Drives the FastMCP tool functions directly with a Context whose
lifespan_context holds the same connected stores the tools would receive
from the lifespan ctx manager. Exercises the full query path
(ingest → graph + vector → tool dispatch → Pydantic models).
"""
from types import SimpleNamespace

import pytest

from llm_code_cache.ingest.chunker import chunk_nodes
from llm_code_cache.ingest.enums import NodeKind
from llm_code_cache.mcp_server import server
from llm_code_cache.mcp_server.server import ServerState
from llm_code_cache.query.enums import UsageKind
from llm_code_cache.query.models import DefinitionResult, SemanticHit, Usage

pytestmark = pytest.mark.integration


@pytest.fixture
def indexed_stores(graph_store, vector_store, parsed_sample_repo, sample_repo_name):
    graph_store.write_parse_result(parsed_sample_repo)
    chunks = list(chunk_nodes(parsed_sample_repo.nodes, sample_repo_name))
    vector_store.upsert_chunks(chunks)
    return graph_store, vector_store


@pytest.fixture
def ctx(indexed_stores):
    graph, vector = indexed_stores
    state = ServerState(graph=graph, vector=vector)
    return SimpleNamespace(request_context=SimpleNamespace(lifespan_context=state))


def test_find_definition_returns_pydantic_result(ctx):
    result = server.find_definition(ctx, "src.auth.authenticate")

    assert isinstance(result, DefinitionResult)
    assert result.qualified_name == "src.auth.authenticate"
    assert result.kind is NodeKind.FUNCTION
    assert "def authenticate" in result.source
    assert result.docstring is not None and "JWT" in result.docstring


def test_find_definition_unknown_symbol_returns_none(ctx):
    assert server.find_definition(ctx, "does.not.exist") is None


def test_find_usages_returns_imported_by(ctx):
    # In v0 textual CALLS resolve to Unresolved stubs (not back to real nodes),
    # but `from src.auth import authenticate` produces an IMPORTS edge whose
    # target matches the real qualified_name and thus shows up here.
    usages = server.find_usages(ctx, "src.auth.authenticate")

    assert all(isinstance(u, Usage) for u in usages)
    importers = [u for u in usages if u.usage_kind is UsageKind.IMPORTED_BY]
    assert any(u.qualified_name == "src.repo" for u in importers)


def test_find_usages_unknown_symbol_returns_empty(ctx):
    assert server.find_usages(ctx, "does.not.exist") == []


def test_semantic_query_returns_ranked_hits_with_graph_augmentation(ctx):
    hits = server.semantic_query(ctx, "validate JWT token signature", top_k=3)

    assert hits, "expected at least one hit"
    assert all(isinstance(h, SemanticHit) for h in hits)
    assert hits[0].qualified_name == "src.auth.authenticate"
    assert hits[0].docstring is not None and "JWT" in hits[0].docstring


def test_semantic_query_top_k_respected(ctx):
    hits = server.semantic_query(ctx, "anything", top_k=2)
    assert len(hits) <= 2

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from llm_code_cache.ingest.enums import NodeKind
from llm_code_cache.mcp_server import server
from llm_code_cache.mcp_server.server import ServerState
from llm_code_cache.query.enums import UsageKind
from llm_code_cache.query.models import DefinitionResult, SemanticHit, Usage


def _ctx(graph=None, vector=None):
    state = ServerState(graph=graph or MagicMock(), vector=vector or MagicMock())
    return SimpleNamespace(request_context=SimpleNamespace(lifespan_context=state))


def test_find_definition_delegates_to_query_layer(monkeypatch):
    expected = DefinitionResult(
        qualified_name="pkg.mod.fn",
        name="fn",
        kind=NodeKind.FUNCTION,
        file_path="pkg/mod.py",
        start_line=1,
        end_line=3,
        source="def fn(): ...",
    )
    spy = MagicMock(return_value=expected)
    monkeypatch.setattr(server, "_find_definition", spy)

    graph = MagicMock(name="graph")
    result = server.find_definition(_ctx(graph=graph), "pkg.mod.fn")

    spy.assert_called_once_with(graph, "pkg.mod.fn")
    assert result is expected


def test_find_definition_returns_none_when_missing(monkeypatch):
    monkeypatch.setattr(server, "_find_definition", MagicMock(return_value=None))
    assert server.find_definition(_ctx(), "missing.symbol") is None


def test_find_usages_delegates_to_query_layer(monkeypatch):
    usage = Usage(
        qualified_name="pkg.mod.caller",
        name="caller",
        kind=NodeKind.FUNCTION,
        usage_kind=UsageKind.CALLED_BY,
        file_path="pkg/mod.py",
        start_line=10,
        end_line=12,
    )
    spy = MagicMock(return_value=[usage])
    monkeypatch.setattr(server, "_find_usages", spy)

    graph = MagicMock(name="graph")
    result = server.find_usages(_ctx(graph=graph), "pkg.mod.fn")

    spy.assert_called_once_with(graph, "pkg.mod.fn")
    assert result == [usage]


def test_find_usages_empty_list_when_no_references(monkeypatch):
    monkeypatch.setattr(server, "_find_usages", MagicMock(return_value=[]))
    assert server.find_usages(_ctx(), "pkg.mod.fn") == []


def test_semantic_query_delegates_with_top_k(monkeypatch):
    hit = SemanticHit(
        qualified_name="pkg.mod.fn",
        score=0.91,
        name="fn",
        kind=NodeKind.FUNCTION,
        file_path="pkg/mod.py",
        start_line=1,
        end_line=3,
        source="def fn(): ...",
    )
    spy = MagicMock(return_value=[hit])
    monkeypatch.setattr(server, "_semantic_query", spy)

    graph = MagicMock(name="graph")
    vector = MagicMock(name="vector")
    result = server.semantic_query(_ctx(graph=graph, vector=vector), "validate jwt", top_k=7)

    spy.assert_called_once_with(vector, graph, "validate jwt", top_k=7)
    assert result == [hit]


def test_semantic_query_default_top_k(monkeypatch):
    spy = MagicMock(return_value=[])
    monkeypatch.setattr(server, "_semantic_query", spy)

    server.semantic_query(_ctx(), "anything")

    assert spy.call_args.kwargs == {"top_k": 5}


def test_tools_registered_on_fastmcp():
    names = {t.name for t in server.mcp._tool_manager.list_tools()}
    assert {"find_definition", "find_usages", "semantic_query"} <= names


def test_lifespan_connects_and_closes_stores(monkeypatch):
    fake_graph = MagicMock(name="GraphStore")
    fake_vector = MagicMock(name="VectorStore")

    monkeypatch.setattr(server.AppConfig, "from_env", staticmethod(MagicMock()))
    monkeypatch.setattr(server, "make_embed_model", MagicMock())
    monkeypatch.setattr(server, "GraphStore", MagicMock(return_value=fake_graph))
    monkeypatch.setattr(server, "VectorStore", MagicMock(return_value=fake_vector))

    async def _drive():
        async with server.lifespan(server.mcp) as state:
            assert state.graph is fake_graph
            assert state.vector is fake_vector
            fake_graph.connect.assert_called_once()
            fake_vector.connect.assert_called_once()
            fake_graph.close.assert_not_called()

    asyncio.run(_drive())
    fake_graph.close.assert_called_once()


def test_lifespan_closes_graph_when_vector_connect_fails(monkeypatch):
    fake_graph = MagicMock(name="GraphStore")
    fake_vector = MagicMock(name="VectorStore")
    fake_vector.connect.side_effect = RuntimeError("pg down")

    monkeypatch.setattr(server.AppConfig, "from_env", staticmethod(MagicMock()))
    monkeypatch.setattr(server, "make_embed_model", MagicMock())
    monkeypatch.setattr(server, "GraphStore", MagicMock(return_value=fake_graph))
    monkeypatch.setattr(server, "VectorStore", MagicMock(return_value=fake_vector))

    async def _drive():
        async with server.lifespan(server.mcp):
            pass

    with pytest.raises(RuntimeError, match="pg down"):
        asyncio.run(_drive())

    fake_graph.close.assert_called_once()

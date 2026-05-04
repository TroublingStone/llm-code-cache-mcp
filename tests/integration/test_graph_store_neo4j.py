import pytest

from llm_code_cache.graph import TraversalDirection
from llm_code_cache.ingest import EdgeKind, NodeKind

pytestmark = pytest.mark.integration


def test_get_definition_function_returns_full_record(graph_store, parsed_sample_repo):
    graph_store.write_parse_result(parsed_sample_repo)

    defn = graph_store.get_definition("src.auth.authenticate")

    assert defn is not None
    assert defn.qualified_name == "src.auth.authenticate"
    assert defn.name == "authenticate"
    assert defn.kind == NodeKind.FUNCTION
    assert defn.docstring is not None and "JWT" in defn.docstring
    assert defn.start_line >= 1
    assert defn.end_line >= defn.start_line
    assert "def authenticate" in defn.source


def test_get_definition_class_returns_full_record(graph_store, parsed_sample_repo):
    graph_store.write_parse_result(parsed_sample_repo)

    defn = graph_store.get_definition("src.repo.UserRepo")

    assert defn is not None
    assert defn.kind == NodeKind.CLASS
    assert defn.docstring is not None and "user records" in defn.docstring


def test_get_definition_unknown_returns_none(graph_store, parsed_sample_repo):
    graph_store.write_parse_result(parsed_sample_repo)

    assert graph_store.get_definition("does.not.exist") is None


def test_get_definition_filters_unresolved_stubs(graph_store, parsed_sample_repo):
    graph_store.write_parse_result(parsed_sample_repo)

    # `verify_signature` is a textual CALLS target; it lands as :Unresolved alongside
    # the real `src.auth.verify_signature` Function node. find_definition must filter stubs.
    assert graph_store.get_definition("verify_signature") is None
    real = graph_store.get_definition("src.auth.verify_signature")
    assert real is not None
    assert real.kind == NodeKind.FUNCTION


def test_neighbors_defined_in_method_to_class(graph_store, parsed_sample_repo):
    graph_store.write_parse_result(parsed_sample_repo)

    nbrs = graph_store.neighbors(
        "src.repo.UserRepo.find_by_token",
        edge_kinds=[EdgeKind.DEFINED_IN],
        direction=TraversalDirection.OUTGOING,
    )

    assert len(nbrs) == 1
    assert nbrs[0].qualified_name == "src.repo.UserRepo"
    assert nbrs[0].kind == NodeKind.CLASS
    assert nbrs[0].edge_kind == EdgeKind.DEFINED_IN


def test_neighbors_calls_creates_unresolved_stubs(graph_store, parsed_sample_repo):
    graph_store.write_parse_result(parsed_sample_repo)

    nbrs = graph_store.neighbors(
        "src.auth.authenticate",
        edge_kinds=[EdgeKind.CALLS],
        direction=TraversalDirection.OUTGOING,
    )

    qns = sorted(n.qualified_name for n in nbrs)
    assert qns == ["sha256_hex", "verify_signature"]
    # Textual CALLS targets land as :Unresolved stubs (kind=None).
    assert all(n.kind is None for n in nbrs)
    assert all(n.edge_kind == EdgeKind.CALLS for n in nbrs)


def test_neighbors_inherits_from_creates_unresolved_stub(graph_store, parsed_sample_repo):
    graph_store.write_parse_result(parsed_sample_repo)

    nbrs = graph_store.neighbors(
        "src.repo.UserRepo",
        edge_kinds=[EdgeKind.INHERITS_FROM],
        direction=TraversalDirection.OUTGOING,
    )

    assert len(nbrs) == 1
    # Parser emits the textual base name; v1 resolution rewrites to src.repo.BaseRepo.
    assert nbrs[0].qualified_name == "BaseRepo"
    assert nbrs[0].kind is None


def test_neighbors_imports_resolves_when_target_matches_real_qname(graph_store, parsed_sample_repo):
    graph_store.write_parse_result(parsed_sample_repo)

    nbrs = graph_store.neighbors(
        "src.auth",
        edge_kinds=[EdgeKind.IMPORTS],
        direction=TraversalDirection.OUTGOING,
    )

    # `from src.utils import sha256_hex` produces target `src.utils.sha256_hex`,
    # which matches the real Function node — should resolve, not create a stub.
    assert len(nbrs) == 1
    assert nbrs[0].qualified_name == "src.utils.sha256_hex"
    assert nbrs[0].kind == NodeKind.FUNCTION


def test_neighbors_depth_2_traverses_multi_hop_path(graph_store, parsed_sample_repo):
    graph_store.write_parse_result(parsed_sample_repo)

    nbrs = graph_store.neighbors(
        "src.auth.authenticate",
        edge_kinds=[EdgeKind.CALLS, EdgeKind.DEFINED_IN],
        direction=TraversalDirection.BOTH,
        depth=2,
    )

    qns = {n.qualified_name for n in nbrs}
    # 1-hop: src.auth (DEFINED_IN), :Unresolved sha256_hex/verify_signature stubs (CALLS).
    # 2-hop: from src.auth back along DEFINED_IN to src.auth.verify_signature (sibling).
    assert "src.auth" in qns
    assert "src.auth.verify_signature" in qns


def test_idempotent_rewrite_preserves_edge_count(graph_store, parsed_sample_repo):
    graph_store.write_parse_result(parsed_sample_repo)
    nbrs1 = graph_store.neighbors(
        "src.auth.authenticate",
        edge_kinds=[EdgeKind.CALLS],
        direction=TraversalDirection.OUTGOING,
    )

    graph_store.write_parse_result(parsed_sample_repo)
    nbrs2 = graph_store.neighbors(
        "src.auth.authenticate",
        edge_kinds=[EdgeKind.CALLS],
        direction=TraversalDirection.OUTGOING,
    )

    assert {n.qualified_name for n in nbrs1} == {n.qualified_name for n in nbrs2}
    assert len(nbrs1) == len(nbrs2)

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from llm_code_cache.cli import app
from llm_code_cache.ingest.enums import NodeKind
from llm_code_cache.ingest.models import Node, ParseResult


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def repo_dir(tmp_path: Path) -> Path:
    repo = tmp_path / "myrepo"
    repo.mkdir()
    (repo / "a.py").write_text("def hello():\n    return 1\n")
    return repo


def _function_node(qualified_name: str = "myrepo.a.hello") -> Node:
    return Node(
        path="/tmp/myrepo/a.py",
        qualified_name=qualified_name,
        name=qualified_name.rsplit(".", 1)[-1],
        kind=NodeKind.FUNCTION,
        start_line=1,
        end_line=2,
        source="def hello():\n    return 1\n",
        docstring=None,
    )


@pytest.fixture
def patched_pipeline(repo_dir: Path):
    """Patch every external collaborator the CLI touches."""
    fake_graph = MagicMock(name="GraphStore")
    fake_vector = MagicMock(name="VectorStore")
    parent = MagicMock()
    parent.attach_mock(fake_graph, "graph")
    parent.attach_mock(fake_vector, "vector")

    with (
        patch("llm_code_cache.cli.AppConfig") as app_config_cls,
        patch("llm_code_cache.cli.make_embed_model") as make_embed,
        patch("llm_code_cache.cli.GraphStore", return_value=fake_graph) as graph_cls,
        patch("llm_code_cache.cli.VectorStore", return_value=fake_vector) as vector_cls,
        patch("llm_code_cache.cli.walk_repo") as walk,
        patch("llm_code_cache.cli.parse_file") as parse,
        patch("llm_code_cache.cli.make_ts_parser") as ts,
    ):
        app_config_cls.from_env.return_value = MagicMock(graph=MagicMock(), vector=MagicMock(), embedding=MagicMock(), embed_dim=384)
        make_embed.return_value = MagicMock(name="embed_model")
        ts.return_value = MagicMock(name="ts_parser")
        walk.return_value = [repo_dir / "a.py"]
        parse.return_value = ParseResult(nodes=[_function_node()], edges=[])
        yield {
            "parent": parent,
            "graph": fake_graph,
            "vector": fake_vector,
            "graph_cls": graph_cls,
            "vector_cls": vector_cls,
            "walk": walk,
            "parse": parse,
        }


def test_index_runs_full_pipeline(runner, repo_dir, patched_pipeline):
    p = patched_pipeline

    result = runner.invoke(app, [str(repo_dir)])

    assert result.exit_code == 0, result.output
    p["graph"].connect.assert_called_once()
    p["vector"].connect.assert_called_once()
    p["graph"].write_parse_result.assert_called_once()
    p["vector"].upsert_chunks.assert_called_once()
    p["vector"].close.assert_called_once()
    p["graph"].close.assert_called_once()


def test_index_does_not_clear_by_default(runner, repo_dir, patched_pipeline):
    runner.invoke(app, [str(repo_dir)])

    patched_pipeline["graph"].clear_repo.assert_not_called()
    patched_pipeline["vector"].clear_repo.assert_not_called()


def test_index_clear_flag_clears_both_stores_before_writing(runner, repo_dir, patched_pipeline):
    p = patched_pipeline

    result = runner.invoke(app, [str(repo_dir), "--clear"])

    assert result.exit_code == 0, result.output
    method_order = [name for name, _, _ in p["parent"].mock_calls if name]
    clear_graph_idx = method_order.index("graph.clear_repo")
    clear_vector_idx = method_order.index("vector.clear_repo")
    write_idx = method_order.index("graph.write_parse_result")
    upsert_idx = method_order.index("vector.upsert_chunks")
    assert clear_graph_idx < write_idx
    assert clear_vector_idx < upsert_idx
    p["graph"].clear_repo.assert_called_once_with("myrepo")
    p["vector"].clear_repo.assert_called_once_with("myrepo")


def test_index_repo_name_override_propagates_to_chunks(runner, repo_dir, patched_pipeline):
    p = patched_pipeline

    result = runner.invoke(app, [str(repo_dir), "--repo-name", "custom"])

    assert result.exit_code == 0, result.output
    chunks = p["vector"].upsert_chunks.call_args.args[0]
    assert chunks, "expected at least one chunk to be produced"
    assert all(c.metadata.repo == "custom" for c in chunks)


def test_index_skips_files_that_fail_to_parse(runner, repo_dir, patched_pipeline, caplog):
    p = patched_pipeline
    good_path = repo_dir / "good.py"
    bad_path = repo_dir / "bad.py"
    good_path.write_text("x = 1\n")
    bad_path.write_text("x = 1\n")
    p["walk"].return_value = [good_path, bad_path]

    def parse_side_effect(path, _root, _ts):
        if path == bad_path:
            raise RuntimeError("synthetic parse failure")
        return ParseResult(nodes=[_function_node("myrepo.good.hello")], edges=[])

    p["parse"].side_effect = parse_side_effect

    with caplog.at_level("WARNING", logger="llm_code_cache.cli"):
        result = runner.invoke(app, [str(repo_dir)])

    assert result.exit_code == 0, result.output
    p["graph"].write_parse_result.assert_called_once()
    written = p["graph"].write_parse_result.call_args.args[0]
    assert len(written.nodes) == 1
    assert any("synthetic parse failure" in rec.message for rec in caplog.records)


def test_index_handles_empty_repo(runner, repo_dir, patched_pipeline):
    p = patched_pipeline
    p["walk"].return_value = []

    result = runner.invoke(app, [str(repo_dir)])

    assert result.exit_code == 0, result.output
    p["graph"].write_parse_result.assert_called_once()
    written = p["graph"].write_parse_result.call_args.args[0]
    assert written.nodes == [] and written.edges == []
    p["vector"].upsert_chunks.assert_called_once_with([])


def test_index_closes_stores_even_if_pipeline_raises(runner, repo_dir, patched_pipeline):
    p = patched_pipeline
    p["graph"].write_parse_result.side_effect = RuntimeError("db down")

    result = runner.invoke(app, [str(repo_dir)])

    assert result.exit_code != 0
    p["vector"].close.assert_called_once()
    p["graph"].close.assert_called_once()

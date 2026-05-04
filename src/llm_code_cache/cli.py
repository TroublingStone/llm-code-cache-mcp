"""Index a Python repository into the graph + vector stores.

Mirrors the MCP server's store-init pattern: AppConfig.from_env() drives both
GraphStore and VectorStore, then runs the ingest pipeline (walker → parser →
chunker → graph + vector writes) once over the target repo.
"""
import logging
from pathlib import Path

import typer

from llm_code_cache.config import AppConfig
from llm_code_cache.graph.store import GraphStore
from llm_code_cache.ingest.chunker import chunk_nodes
from llm_code_cache.ingest.models import ParseResult
from llm_code_cache.ingest.parser import make_ts_parser, parse_file
from llm_code_cache.ingest.walker import walk_repo
from llm_code_cache.vector.embeddings import make_embed_model
from llm_code_cache.vector.store import VectorStore

logger = logging.getLogger(__name__)
app = typer.Typer(help="Index a Python repository into the code-cache stores.")


@app.command()
def index(
    repo_path: Path = typer.Argument(..., exists=True, file_okay=False, resolve_path=True),
    repo_name: str | None = typer.Option(None, "--repo-name", help="Override the derived repo identifier."),
    clear: bool = typer.Option(
        False,
        "--clear",
        help="Drop existing graph + vector data for this repo before writing.",
    ),
) -> None:
    """Walk repo_path, parse Python files, and write graph + vector data."""
    # TODO(v1): incremental indexing scoped to a git diff.
    repo = repo_name or repo_path.name
    config = AppConfig.from_env()
    embed_model = make_embed_model(config.embedding)
    graph = GraphStore(config.graph)
    vector = VectorStore(config.vector, config.embed_dim, embed_model)
    graph.connect()
    try:
        vector.connect()
        if clear:
            graph.clear_repo(repo)
            vector.clear_repo(repo)
        _run_pipeline(repo_path, repo, graph, vector)
    finally:
        vector.close()
        graph.close()


def _run_pipeline(repo_root: Path, repo: str, graph: GraphStore, vector: VectorStore) -> None:
    paths = walk_repo(repo_root)
    ts_parser = make_ts_parser()
    merged_nodes = []
    merged_edges = []
    skipped = 0
    for path in paths:
        try:
            result = parse_file(path, repo_root, ts_parser)
        except Exception as exc:  # noqa: BLE001 — per-file boundary, log and continue
            logger.warning("skipped %s: %s", path, exc)
            skipped += 1
            continue
        merged_nodes.extend(result.nodes)
        merged_edges.extend(result.edges)
    graph.write_parse_result(ParseResult(nodes=merged_nodes, edges=merged_edges))
    chunks = list(chunk_nodes(merged_nodes, repo))
    vector.upsert_chunks(chunks)
    logger.info(
        "indexed repo=%s files=%d skipped=%d nodes=%d edges=%d chunks=%d",
        repo,
        len(paths) - skipped,
        skipped,
        len(merged_nodes),
        len(merged_edges),
        len(chunks),
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app()


if __name__ == "__main__":
    main()

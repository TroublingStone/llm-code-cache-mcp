"""Smoke test for GraphStore against the local docker-compose Neo4j.

Runs end-to-end: parse a tiny synthetic repo, write to Neo4j, query back.
Prints results so a human (or agent) can eyeball the round-trip.
"""

from __future__ import annotations

import logging
import shutil
import sys
import tempfile
from pathlib import Path
from textwrap import dedent

from llm_code_cache.graph import GraphConfig, TraversalDirection
from llm_code_cache.graph.store import GraphStore
from llm_code_cache.ingest import EdgeKind, NodeKind
from llm_code_cache.ingest.parser import parse_repo

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("smoke")


SAMPLE_FILES: dict[str, str] = {
    "src/auth.py": dedent(
        '''
        from src.utils import sha256_hex

        def authenticate(token: str) -> bool:
            """Validate a JWT token."""
            digest = sha256_hex(token)
            return verify_signature(digest)


        def verify_signature(digest: str) -> bool:
            return bool(digest)
        '''
    ).lstrip(),
    "src/utils.py": dedent(
        '''
        import hashlib


        def sha256_hex(data: str) -> str:
            """Return SHA-256 hex digest of a string."""
            return hashlib.sha256(data.encode()).hexdigest()
        '''
    ).lstrip(),
    "src/repo.py": dedent(
        '''
        from src.auth import authenticate


        class BaseRepo:
            """Base class for all repos."""


        class UserRepo(BaseRepo):
            """Persistence for users."""

            def find_by_token(self, token: str):
                """Look up a user by token."""
                if authenticate(token):
                    return {"ok": True}
                return None
        '''
    ).lstrip(),
}


def materialize_repo(root: Path) -> list[Path]:
    paths: list[Path] = []
    for rel, content in SAMPLE_FILES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        paths.append(p)
    return paths


def banner(msg: str) -> None:
    print()
    print("=" * 72)
    print(f" {msg}")
    print("=" * 72)


def main() -> int:
    config = GraphConfig(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="password",
    )
    store = GraphStore(config)

    repo_root = Path(tempfile.mkdtemp(prefix="smoke-graph-"))
    try:
        banner(f"materialize repo at {repo_root}")
        paths = materialize_repo(repo_root)
        for p in paths:
            print(f"  {p.relative_to(repo_root)}  ({p.stat().st_size}B)")

        banner("parse repo")
        result = parse_repo(paths, repo_root)
        print(f"  nodes: {len(result.nodes)}")
        print(f"  edges: {len(result.edges)}")
        for n in result.nodes:
            print(f"    {n.kind:8s} {n.qualified_name}")
        for e in result.edges:
            print(f"    {e.kind:14s} {e.source}  ->  {e.target}")

        banner("connect graph store + ensure constraints")
        store.connect()

        banner("write parse result")
        store.write_parse_result(result)

        banner("get_definition for src.auth.authenticate")
        defn = store.get_definition("src.auth.authenticate")
        if defn is None:
            print("  MISS")
        else:
            print(f"  qualified_name = {defn.qualified_name}")
            print(f"  kind           = {defn.kind}")
            print(f"  file_path      = {defn.file_path}")
            print(f"  lines          = {defn.start_line}..{defn.end_line}")
            print(f"  docstring      = {defn.docstring!r}")
            print(f"  decorators     = {defn.decorators}")
            print(f"  source[:80]    = {defn.source[:80]!r}")

        banner("get_definition for src.repo.UserRepo")
        defn = store.get_definition("src.repo.UserRepo")
        if defn is None:
            print("  MISS")
        else:
            print(f"  qualified_name = {defn.qualified_name}")
            print(f"  kind           = {defn.kind}")
            print(f"  parent_class   = {defn.parent_class}")
            print(f"  docstring      = {defn.docstring!r}")

        banner("neighbors: CALLS outgoing from src.auth.authenticate")
        nbrs = store.neighbors(
            "src.auth.authenticate",
            edge_kinds=[EdgeKind.CALLS],
            direction=TraversalDirection.OUTGOING,
        )
        print(f"  count = {len(nbrs)}")
        for nb in nbrs:
            print(f"    -> {nb.kind:8s} {nb.qualified_name}  via {nb.edge_kind}")

        banner("neighbors: CALLS incoming to src.auth.authenticate")
        nbrs = store.neighbors(
            "src.auth.authenticate",
            edge_kinds=[EdgeKind.CALLS],
            direction=TraversalDirection.INCOMING,
        )
        print(f"  count = {len(nbrs)}")
        for nb in nbrs:
            print(f"    <- {nb.kind:8s} {nb.qualified_name}  via {nb.edge_kind}")

        banner("neighbors: DEFINED_IN outgoing from src.repo.UserRepo.find_by_token")
        nbrs = store.neighbors(
            "src.repo.UserRepo.find_by_token",
            edge_kinds=[EdgeKind.DEFINED_IN],
            direction=TraversalDirection.OUTGOING,
        )
        print(f"  count = {len(nbrs)}")
        for nb in nbrs:
            print(f"    -> {nb.kind:8s} {nb.qualified_name}  via {nb.edge_kind}")

        banner("neighbors: INHERITS_FROM outgoing from src.repo.UserRepo")
        nbrs = store.neighbors(
            "src.repo.UserRepo",
            edge_kinds=[EdgeKind.INHERITS_FROM],
            direction=TraversalDirection.OUTGOING,
        )
        print(f"  count = {len(nbrs)}")
        for nb in nbrs:
            print(f"    -> {nb.kind:8s} {nb.qualified_name}  via {nb.edge_kind}")

        banner("neighbors: IMPORTS outgoing from src.auth (file)")
        nbrs = store.neighbors(
            "src.auth",
            edge_kinds=[EdgeKind.IMPORTS],
            direction=TraversalDirection.OUTGOING,
        )
        print(f"  count = {len(nbrs)}")
        for nb in nbrs:
            print(f"    -> {nb.kind:8s} {nb.qualified_name}  via {nb.edge_kind}")

        banner("neighbors: depth=2 BOTH (CALLS|DEFINED_IN) from src.auth.authenticate")
        nbrs = store.neighbors(
            "src.auth.authenticate",
            edge_kinds=[EdgeKind.CALLS, EdgeKind.DEFINED_IN],
            direction=TraversalDirection.BOTH,
            depth=2,
        )
        print(f"  count = {len(nbrs)}")
        for nb in nbrs:
            print(f"    ~~ {nb.kind:8s} {nb.qualified_name}  via {nb.edge_kind} ({nb.direction})")

        banner("get_definition for unknown symbol (expect None)")
        miss = store.get_definition("does.not.exist")
        print(f"  result = {miss!r}")

        banner("idempotent re-write")
        store.write_parse_result(result)
        nbrs2 = store.neighbors(
            "src.auth.authenticate",
            edge_kinds=[EdgeKind.CALLS],
            direction=TraversalDirection.OUTGOING,
        )
        print(f"  CALLS-out count after re-write = {len(nbrs2)} (expected same as first write)")

        banner("DONE")
        return 0
    finally:
        store.close()
        shutil.rmtree(repo_root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())

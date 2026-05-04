from dataclasses import dataclass

from llm_code_cache.graph.enums import TraversalDirection
from llm_code_cache.ingest.enums import EdgeKind, NodeKind


@dataclass
class GraphConfig:
    uri: str          # e.g. "bolt://localhost:7687"
    user: str         # e.g. "neo4j"
    password: str     # from env
    database: str = "neo4j"  # default DB name; usually fine

@dataclass
class GraphDefinitionRecord:
    qualified_name: str
    name: str
    kind: NodeKind
    docstring: str | None
    parent_class: str | None
    decorators: list[str]
    # file context, joined from DEFINED_IN
    file_path: str
    start_line: int
    end_line: int
    source: str

@dataclass
class GraphNeighborRecord:
    qualified_name: str          # the neighbor's identifier
    name: str
    # kind is None for :Unresolved stubs (textual edge targets the v0 parser couldn't
    # resolve to a real node). The v1 resolution pass replaces these with real kinds.
    kind: NodeKind | None
    edge_kind: EdgeKind          # how this neighbor relates: CALLS, IMPORTS, INHERITS_FROM, DECORATED_BY
    direction: TraversalDirection
    # file context, useful for display
    file_path: str
    start_line: int
    end_line: int

from dataclasses import dataclass

from llm_code_cache.graph.enums import TraversalDirection
from llm_code_cache.ingest.enums import EdgeKind, NodeKind


@dataclass
class GraphConfig:
    uri: str
    user: str
    password: str
    database: str = "neo4j"

@dataclass
class GraphDefinitionRecord:
    qualified_name: str
    name: str
    kind: NodeKind
    docstring: str | None
    parent_class: str | None
    decorators: list[str]
    file_path: str
    start_line: int
    end_line: int
    source: str

@dataclass
class GraphNeighborRecord:
    # Real nodes set qualified_name + kind; :Unresolved stubs set text_ref instead.
    # Invariant: (qualified_name is None) == (kind is None) == (text_ref is not None).
    # The v1 resolver promotes text_ref to a canonical qualified_name and assigns a
    # real kind, dropping the :Unresolved label.
    qualified_name: str | None
    text_ref: str | None
    name: str
    kind: NodeKind | None
    edge_kind: EdgeKind          # how this neighbor relates: CALLS, IMPORTS, INHERITS_FROM, DECORATED_BY
    direction: TraversalDirection
    file_path: str
    start_line: int
    end_line: int

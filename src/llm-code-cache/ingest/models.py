from dataclasses import dataclass

from ingest.enums.node_kind import NodeKind
from ingest.enums.edge_kind import EdgeKind

@dataclass
class Node:
    path: str
    qualified_name: str
    name: str
    kind: NodeKind
    start_line: int
    end_line: int
    source: str
    parent_class: str | None = None
    docstring: str | None = None

@dataclass
class Edge:
    source: str
    target: str
    kind: EdgeKind
    
@dataclass
class ParseResult:
    nodes: list[Node]
    edges: list[Edge]

@dataclass
class Metadata:
    repo: str
    path: str
    qualified_name: str
    name: str
    kind: NodeKind
    start_line: int
    end_line: int
    # source is intentionally excluded: it duplicates embed_text and bloats vector DB metadata.
    # If source is needed at retrieval time, implement it as a lazy property: read
    # path[start_line:end_line] from disk on demand. A read failure means the file changed
    # and the chunk is stale — trigger reindex.

    @classmethod
    def from_node(cls, node: Node, repo: str) -> "Metadata":
        return cls(
            repo=repo,
            path=node.path,
            qualified_name=node.qualified_name,
            name=node.name,
            kind=node.kind,
            start_line=node.start_line,
            end_line=node.end_line,
        )

@dataclass
class Chunk:
    embed_text: str
    metadata: Metadata

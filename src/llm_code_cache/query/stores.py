from typing import Protocol

from llm_code_cache.graph import GraphDefinitionRecord, GraphNeighborRecord, TraversalDirection
from llm_code_cache.ingest.enums import EdgeKind
from llm_code_cache.vector import VectorHit


class GraphStoreProtocol(Protocol):
    def get_definition(self, qualified_name: str) -> GraphDefinitionRecord | None: ...

    def neighbors(
        self,
        qualified_name: str,
        edge_kinds: list[EdgeKind],
        direction: TraversalDirection,
        depth: int = 1,
    ) -> list[GraphNeighborRecord]: ...


class VectorStoreProtocol(Protocol):
    def search(self, query: str, top_k: int = 5) -> list[VectorHit]: ...

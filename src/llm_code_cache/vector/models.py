from dataclasses import dataclass

from llama_index.core.schema import NodeWithScore

from llm_code_cache.ingest.enums.node_kind import NodeKind


@dataclass
class VectorHit:
    qualified_name: str
    score: float
    repo: str
    path: str
    name: str
    kind: NodeKind
    start_line: int
    end_line: int
    source: str

    @classmethod
    def from_node(cls, node_with_score: NodeWithScore) -> "VectorHit":
        md = node_with_score.metadata
        return cls(
            qualified_name=md["qualified_name"],
            score=node_with_score.score or 0.0,
            repo=md["repo"],
            path=md["path"],
            name=md["name"],
            kind=NodeKind(md["kind"]),
            start_line=md["start_line"],
            end_line=md["end_line"],
            # TODO(v1): read raw source from disk via path[start_line:end_line]; this returns the embed_text
            source=node_with_score.node.get_content(),
        )
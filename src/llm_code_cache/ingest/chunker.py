from typing import Iterable
from ingest.constants import MAX_EMBED_TOKENS, TOKEN_ESTIMATE_DIVISOR
from ingest.enums.node_kind import NodeKind
from ingest.models import Chunk, Metadata, Node

EMBEDDABLE_KINDS = {NodeKind.FUNCTION, NodeKind.METHOD, NodeKind.CLASS}


def build_embed_text(node: Node) -> str: # TODO: handle additional context, parent classes, abstract classes, overrides
    parts = []
    parts.append(f"File: {node.path}")
    if node.parent_class:
        parts.append(f"Class: {node.parent_class}")
    if node.docstring:
        parts.append(f"Docstring: {node.docstring}")
    parts.append(node.source)
    return "\n\n".join(parts)


def estimate_tokens(text: str) -> int:
    return len(text) // TOKEN_ESTIMATE_DIVISOR  # TODO: just a heuristic estimate, add robust logic later


def chunk_nodes(nodes: Iterable[Node], repo: str) -> Iterable[Chunk]:
    chunks = []
    for node in nodes:
        if node.kind in EMBEDDABLE_KINDS:
            embed_node_text = build_embed_text(node)
            if estimate_tokens(embed_node_text) > MAX_EMBED_TOKENS:
                continue  # TODO: add handling for oversized objects
            node_chunk = Chunk(embed_node_text, Metadata.from_node(node, repo))
            chunks.append(node_chunk)
    return chunks

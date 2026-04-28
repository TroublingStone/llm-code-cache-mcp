from typing import Iterable
from ingest.enums.node_kind import NodeKind
from ingest.models import Metadata, Node, Chunk

EMBEDDABLE_KINDS = {NodeKind.FUNCTION, NodeKind.METHOD, NodeKind.CLASS}
MAX_EMBED_TOKENS = 1500


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
    return len(text)//3 # TODO: just a heauristic estimete, add robest logic later

def chunk_nodes(nodes: Iterable[Node], repo: str) -> Iterable[Chunk]:
    chunks = []
    for node in nodes:
        if node.kind in EMBEDDABLE_KINDS:
            embed_node_text: str = build_embed_text(node)
            if estimate_tokens(embed_node_text) > MAX_EMBED_TOKENS:
                continue # TODO: add handling for oversized objects
            node_chunk: Chunk = Chunk(embed_node_text, Metadata.from_node(node, repo))
            chunks.append(node_chunk)
    return chunks
            


from typing import Iterable

from llm_code_cache.ingest.constants import (
    EMBEDDABLE_KINDS,
    MAX_EMBED_TOKENS,
    TOKEN_ESTIMATE_DIVISOR,
)
from llm_code_cache.ingest.models import Chunk, Metadata, Node


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
        if node.kind in EMBEDDABLE_KINDS and estimate_tokens(text := build_embed_text(node)) <= MAX_EMBED_TOKENS:  # TODO(v1): log + handle oversized nodes
            chunks.append(Chunk(text, Metadata.from_node(node, repo)))
    return chunks

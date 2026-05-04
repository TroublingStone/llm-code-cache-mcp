import logging

from llm_code_cache.query.models import SemanticHit
from llm_code_cache.query.stores import GraphStoreProtocol
from llm_code_cache.vector import VectorHit

logger = logging.getLogger(__name__)


def enrich_with_definition(hit: VectorHit, graph: GraphStoreProtocol) -> SemanticHit:
    """Pivot a vector hit into the graph for structural context.

    Cross-store identity invariant guarantees the graph node exists; if it
    doesn't, the stores are out of sync (e.g. stale vector entry after a
    reindex). Log and return a SemanticHit without graph fields rather than
    failing the whole query.
    """
    record = graph.get_definition(hit.qualified_name)
    if record is None:
        logger.warning(
            "vector hit missing graph node: qualified_name=%s (stores out of sync?)",
            hit.qualified_name,
        )
        return _to_semantic_hit(hit)
    return _to_semantic_hit(
        hit,
        docstring=record.docstring,
        parent_class=record.parent_class,
        decorators=record.decorators,
    )


def _to_semantic_hit(
    hit: VectorHit,
    *,
    docstring: str | None = None,
    parent_class: str | None = None,
    decorators: list[str] | None = None,
) -> SemanticHit:
    return SemanticHit(
        qualified_name=hit.qualified_name,
        score=hit.score,
        name=hit.name,
        kind=hit.kind,
        file_path=hit.path,
        start_line=hit.start_line,
        end_line=hit.end_line,
        source=hit.source,
        docstring=docstring,
        parent_class=parent_class,
        decorators=decorators or [],
    )

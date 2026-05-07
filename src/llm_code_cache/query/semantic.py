from llm_code_cache.query.augmentation import enrich_with_definition
from llm_code_cache.query.models import SemanticHit
from llm_code_cache.query.stores import GraphStoreProtocol, VectorStoreProtocol


def semantic_query(
    vector: VectorStoreProtocol,
    graph: GraphStoreProtocol,
    query: str,
    top_k: int = 5,
) -> list[SemanticHit]:
    hits = vector.search(query, top_k=top_k)
    # TODO(v1): batch graph fetches to avoid N+1 (one get_definition per hit).
    return [enrich_with_definition(h, graph) for h in hits]

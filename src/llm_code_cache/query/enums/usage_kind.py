from enum import StrEnum

from llm_code_cache.ingest.enums import EdgeKind


class UsageKind(StrEnum):
    """How a neighbor uses the queried symbol.

    Always describes an *incoming* edge: "X is CALLED_BY caller", "X is
    IMPORTED_BY file", etc. DECORATES is the inverse-named case: a
    DECORATED_BY edge points decorated -> decorator-text, so an incoming
    DECORATED_BY edge means *this node is the decorator* and the neighbor
    is the decorated thing.
    """

    CALLED_BY = "called_by"
    IMPORTED_BY = "imported_by"
    SUBCLASSED_BY = "subclassed_by"
    DECORATES = "decorates"


EDGE_TO_USAGE: dict[EdgeKind, UsageKind] = {
    EdgeKind.CALLS: UsageKind.CALLED_BY,
    EdgeKind.IMPORTS: UsageKind.IMPORTED_BY,
    EdgeKind.INHERITS_FROM: UsageKind.SUBCLASSED_BY,
    EdgeKind.DECORATED_BY: UsageKind.DECORATES,
}

USAGE_EDGE_KINDS: list[EdgeKind] = list(EDGE_TO_USAGE.keys())

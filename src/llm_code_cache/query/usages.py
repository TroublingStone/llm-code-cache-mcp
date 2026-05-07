from llm_code_cache.graph import GraphNeighborRecord, TraversalDirection
from llm_code_cache.query.enums import EDGE_TO_USAGE, USAGE_EDGE_KINDS
from llm_code_cache.query.models import Usage
from llm_code_cache.query.stores import GraphStoreProtocol


def find_usages(graph: GraphStoreProtocol, qualified_name: str) -> list[Usage]:
    records = graph.neighbors(
        qualified_name=qualified_name,
        edge_kinds=USAGE_EDGE_KINDS,
        direction=TraversalDirection.INCOMING,
        depth=1,
    )
    return [_to_usage(r) for r in records]


def _to_usage(record: GraphNeighborRecord) -> Usage:
    return Usage(
        qualified_name=record.qualified_name,
        text_ref=record.text_ref,
        name=record.name,
        kind=record.kind,
        usage_kind=EDGE_TO_USAGE[record.edge_kind],
        file_path=record.file_path,
        start_line=record.start_line,
        end_line=record.end_line,
    )

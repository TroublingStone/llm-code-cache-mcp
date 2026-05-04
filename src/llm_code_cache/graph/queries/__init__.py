from pathlib import Path

_QUERIES_DIR = Path(__file__).parent


def _load(name: str) -> str:
    return (_QUERIES_DIR / name).read_text(encoding="utf-8").strip()


def _load_statements(name: str) -> list[str]:
    """Load a multi-statement .cypher file and split on `;`."""
    raw = (_QUERIES_DIR / name).read_text(encoding="utf-8")
    return [stmt.strip() for stmt in raw.split(";") if stmt.strip()]


CONSTRAINTS: list[str] = _load_statements("constraints.cypher")
# TODO(v1): per-repo indexes (e.g. on n.repo) land here when the cross-repo
# schema is decided (DESIGN.md Open Questions). Node has no repo field today.
INDEXES: list[str] = _load_statements("indexes.cypher")
CLEAR_REPO: str = _load("clear_repo.cypher")
FIND_DEFINITION: str = _load("find_definition.cypher")

_UPSERT_NODES_TEMPLATE: str = _load("upsert_nodes.cypher")
_UPSERT_EDGES_TEMPLATE: str = _load("upsert_edges.cypher")
_GET_NEIGHBORS_TEMPLATE: str = _load("get_neighbors.cypher")


def upsert_nodes_query(label: str) -> str:
    return _UPSERT_NODES_TEMPLATE.replace("__LABEL__", label)


def upsert_edges_query(rel_type: str) -> str:
    return _UPSERT_EDGES_TEMPLATE.replace("__REL_TYPE__", rel_type)


def get_neighbors_query(
    arrow_left: str, arrow_right: str, rel_types: str, depth_clause: str
) -> str:
    return _GET_NEIGHBORS_TEMPLATE.format(
        arrow_left=arrow_left,
        arrow_right=arrow_right,
        rel_types=rel_types,
        depth_clause=depth_clause,
    )

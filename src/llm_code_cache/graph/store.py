import logging
from collections import defaultdict
from dataclasses import asdict

from neo4j import Driver, GraphDatabase, Record

from llm_code_cache.graph import queries
from llm_code_cache.graph.enums import EdgeField, NodeField, NodeProperty, TraversalDirection
from llm_code_cache.graph.models import GraphConfig, GraphDefinitionRecord, GraphNeighborRecord
from llm_code_cache.ingest import Edge, EdgeKind, Node, NodeKind, ParseResult

logger = logging.getLogger(__name__)

_BATCH_SIZE = 1000
_MAX_DEPTH = 10
_DIRECTION_ARROWS: dict[TraversalDirection, tuple[str, str]] = {
    TraversalDirection.OUTGOING: ("-", "->"),
    TraversalDirection.INCOMING: ("<-", "-"),
    TraversalDirection.BOTH:     ("-", "-"),
}


class GraphStore:
    def __init__(self, config: GraphConfig) -> None:
        self._config = config
        self._driver: Driver | None = None

    def connect(self) -> None:
        self._driver = GraphDatabase.driver(
            self._config.uri,
            auth=(self._config.user, self._config.password),
        )
        self._driver.verify_connectivity()
        logger.info("graph store connected: uri=%s", self._config.uri)
        self.ensure_constraints()

    @property
    def driver(self) -> Driver:
        if self._driver is None:
            raise RuntimeError("GraphStore.connect() must be called first")
        return self._driver

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def ensure_constraints(self) -> None:
        """Create uniqueness constraints and indexes. Idempotent."""
        with self.driver.session(database=self._config.database) as session:
            for statement in queries.CONSTRAINTS + queries.INDEXES:
                session.execute_write(lambda tx, s=statement: tx.run(s))
        logger.info(
            "ensured graph constraints: constraints=%d indexes=%d",
            len(queries.CONSTRAINTS),
            len(queries.INDEXES),
        )

    def clear_repo(self, repo: str) -> None:
        with self.driver.session(database=self._config.database) as session:
            session.execute_write(lambda tx: tx.run(queries.CLEAR_REPO, repo=repo))
        logger.info("cleared repo from graph: repo=%s", repo)

    def write_parse_result(self, result: ParseResult) -> None:
        if not result.nodes and not result.edges:
            return
        self._write_nodes(result.nodes)
        self._write_edges(result.edges)
        logger.info(
            "wrote graph: nodes=%d edges=%d",
            len(result.nodes),
            len(result.edges),
        )

    def _write_nodes(self, nodes: list[Node]) -> None:
        by_label: dict[str, list[Node]] = defaultdict(list)
        for n in nodes:
            by_label[n.kind.capitalize()].append(n)

        with self.driver.session(database=self._config.database) as session:
            for label, label_nodes in by_label.items():
                self._upsert_nodes_for_label(session, label, label_nodes)

    def _upsert_nodes_for_label(self, session, label, nodes):
        query = queries.upsert_nodes_query(label)
        for i in range(0, len(nodes), _BATCH_SIZE):
            batch = nodes[i : i + _BATCH_SIZE]
            payload = [self._node_to_dict(n) for n in batch]
            session.execute_write(lambda tx, p=payload: tx.run(query, nodes=p))

    def _node_to_dict(self, node: Node) -> dict:
        props = asdict(node)
        qn = props.pop(NodeProperty.QUALIFIED_NAME)
        props.pop(NodeField.KIND)
        return {NodeProperty.QUALIFIED_NAME: qn, NodeField.PROPS: props}

    def _write_edges(self, edges: list[Edge]) -> None:
        by_kind: dict[str, list[Edge]] = defaultdict(list)
        for edge in edges:
            by_kind[edge.kind.upper()].append(edge)

        with self.driver.session(database=self._config.database) as session:
            for rel_type, kind_edges in by_kind.items():
                self._upsert_edges_for_kind(session, rel_type, kind_edges)

    def _upsert_edges_for_kind(self, session, rel_type: str, edges: list[Edge]) -> None:
        query = queries.upsert_edges_query(rel_type)
        for i in range(0, len(edges), _BATCH_SIZE):
            batch = edges[i : i + _BATCH_SIZE]
            payload = [{EdgeField.SOURCE: edge.source, EdgeField.TARGET: edge.target} for edge in batch]
            session.execute_write(lambda tx, p=payload: tx.run(query, edges=p))

    def get_definition(self, qualified_name: str) -> GraphDefinitionRecord | None:
        with self.driver.session(database=self._config.database) as session:
            record = session.execute_read(lambda tx: tx.run(queries.FIND_DEFINITION, qn=qualified_name).single())
        if record is None:
            return None
        return self._to_definition_record(record)

    def _to_definition_record(self, record: Record) -> GraphDefinitionRecord:
        node = record["n"]
        file = record["f"]
        return GraphDefinitionRecord(
            qualified_name=node[NodeProperty.QUALIFIED_NAME],
            name=node[NodeProperty.NAME],
            kind=NodeKind(record["labels"][0].lower()),
            docstring=node.get(NodeProperty.DOCSTRING),
            parent_class=node.get(NodeProperty.PARENT_CLASS),
            decorators=node.get(NodeProperty.DECORATORS, []),
            file_path=(file or node)[NodeProperty.PATH],
            start_line=node[NodeProperty.START_LINE],
            end_line=node[NodeProperty.END_LINE],
            source=node[NodeProperty.SOURCE],
        )

    def neighbors(
        self,
        qualified_name: str,
        edge_kinds: list[EdgeKind],
        direction: TraversalDirection,
        depth: int = 1,
    ) -> list[GraphNeighborRecord]:
        if not edge_kinds:
            return []
        if depth < 1 or depth > _MAX_DEPTH:
            raise ValueError(f"depth must be between 1 and {_MAX_DEPTH}, got {depth}")

        # At depth>1, edge_kind on each neighbor record is the type of the LAST
        # relationship in the traversal path; intermediate hops are not surfaced.
        rel_types = "|".join(k.upper() for k in edge_kinds)
        arrow_left, arrow_right = _DIRECTION_ARROWS[direction]
        depth_clause = "" if depth == 1 else f"*1..{depth}"

        query = queries.get_neighbors_query(
            arrow_left=arrow_left,
            arrow_right=arrow_right,
            rel_types=rel_types,
            depth_clause=depth_clause,
        )

        with self.driver.session(database=self._config.database) as session:
            records = session.execute_read(
                lambda tx: list(tx.run(query, qn=qualified_name))
            )
        return [self._to_neighbor_record(r, direction) for r in records]

    def _to_neighbor_record(self, record, direction: TraversalDirection) -> GraphNeighborRecord:
        node = record["neighbor"]
        file = record["f"]
        labels = record["labels"]

        if "Unresolved" in labels:
            text_ref: str | None = node[NodeProperty.TEXT_REF]
            qualified_name: str | None = None
            kind: NodeKind | None = None
            name = text_ref.rsplit(".", 1)[-1]
        else:
            qualified_name = node[NodeProperty.QUALIFIED_NAME]
            text_ref = None
            kind = NodeKind(labels[0].lower())
            name = node.get(NodeProperty.NAME) or qualified_name.rsplit(".", 1)[-1]
        return GraphNeighborRecord(
            qualified_name=qualified_name,
            text_ref=text_ref,
            name=name,
            kind=kind,
            edge_kind=EdgeKind(record["edge_type"].lower()),
            direction=direction,
            file_path=file[NodeProperty.PATH] if file is not None else node.get(NodeProperty.PATH, ""),
            start_line=node.get(NodeProperty.START_LINE, 0),
            end_line=node.get(NodeProperty.END_LINE, 0),
        )

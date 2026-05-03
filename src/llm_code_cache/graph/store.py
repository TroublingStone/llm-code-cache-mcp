import logging
from collections import defaultdict
from dataclasses import asdict

from neo4j import Driver, GraphDatabase

from llm_code_cache.graph import queries
from llm_code_cache.graph.enums.traversal_direction import TraversalDirection
from llm_code_cache.graph.models import GraphConfig, GraphDefinitionRecord, GraphNeighborRecord
from llm_code_cache.ingest.enums.edge_kind import EdgeKind
from llm_code_cache.ingest.models import Edge, Node, ParseResult

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000

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
        for i in range(0, len(nodes), BATCH_SIZE):
            batch = nodes[i:i + BATCH_SIZE]
            payload = [self._node_to_dict(n) for n in batch]
            session.execute_write(lambda tx, p=payload: tx.run(query, nodes=p))

    def _node_to_dict(self, node: Node) -> dict:
        d = asdict(node)
        qn = d.pop("qualified_name")
        d.pop("kind")
        return {"qualified_name": qn, "props": d}

    def _write_edges(self, edges: list[Edge]) -> None:
        by_kind: dict[str, list[Edge]] = defaultdict(list)
        for e in edges:
            by_kind[e.kind.upper()].append(e)
    
        with self.driver.session(database=self._config.database) as session:
            for rel_type, kind_edges in by_kind.items():
                self._upsert_edges_for_kind(session, rel_type, kind_edges)
    
    
    def _upsert_edges_for_kind(
        self, session, rel_type: str, edges: list[Edge]
    ) -> None:
        query = queries.upsert_edges_query(rel_type)
        for i in range(0, len(edges), BATCH_SIZE):
            batch = edges[i:i + BATCH_SIZE]
            payload = [{"source": e.source, "target": e.target} for e in batch]
            session.execute_write(lambda tx, p=payload: tx.run(query, edges=p))

    def get_definition(self, qualified_name: str) -> GraphDefinitionRecord | None: ...
    def neighbors(
        self,
        qualified_name: str,
        edge_kinds: list[EdgeKind],
        direction: TraversalDirection,
        depth: int = 1,
    ) -> list[GraphNeighborRecord]: ...
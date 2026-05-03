from pathlib import Path

from llm_code_cache.ingest.constants import SOURCE_ENCODING, TS_DEFINITION_TYPES
from llm_code_cache.ingest.enums.edge_kind import EdgeKind
from llm_code_cache.ingest.enums.node_kind import NodeKind
from llm_code_cache.ingest.enums.ts_field_name import TSFieldName
from llm_code_cache.ingest.enums.ts_node_type import TSNodeType
from llm_code_cache.ingest.models import Edge, Node, ParseResult
from tree_sitter import Language
from tree_sitter import Node as TSNode
from tree_sitter import Parser as TSParser
from tree_sitter_python import language as _ts_py_lang

_PY_LANGUAGE = Language(_ts_py_lang())


def _unwrap(node: TSNode) -> tuple[TSNode | None, TSNode]:
    ntype = node.type
    if ntype in TS_DEFINITION_TYPES:
        return node, node
    elif ntype == TSNodeType.DECORATED_DEF:
        return node.child_by_field_name(TSFieldName.DEFINITION), node
    return None, node


def _process_function(
    defn: TSNode,
    outer: TSNode,
    path: Path,
    repo_root: Path,
    source: bytes,
    parent_qname: str,
    parent_class: str | None,
) -> tuple[Node, list[Edge]]:
    fn = extract_function(defn, path, repo_root, source, parent_class)
    fn.decorators, dec_edges = extract_decorators(outer, fn.qualified_name, source)
    return fn, [
        *dec_edges,
        Edge(fn.qualified_name, parent_qname, EdgeKind.DEFINED_IN),
        *extract_calls(defn, fn.qualified_name, source),
    ]


def _process_class(
    defn: TSNode,
    outer: TSNode,
    path: Path,
    repo_root: Path,
    source: bytes,
    file_qname: str,
) -> tuple[Node, list[Edge]]:
    cls, cls_edges = extract_class(defn, path, repo_root, source)
    cls.decorators, dec_edges = extract_decorators(outer, cls.qualified_name, source)
    return cls, [
        *cls_edges,
        *dec_edges,
        Edge(cls.qualified_name, file_qname, EdgeKind.DEFINED_IN),
    ]


def parse_file(path: Path, repo_root: Path, ts_parser: TSParser) -> ParseResult:
    source = path.read_bytes()
    tree = ts_parser.parse(source)
    file_node = extract_file_node(path, repo_root, source)
    nodes: list[Node] = [file_node]
    edges: list[Edge] = []
    file_qname = file_node.qualified_name

    for child in tree.root_node.named_children:
        if child.type in (TSNodeType.IMPORT, TSNodeType.IMPORT_FROM):
            edges.extend(extract_imports(child, file_qname, source))
            continue

        defn, outer = _unwrap(child)
        if defn is None:
            continue

        if defn.type == TSNodeType.FUNCTION_DEF:
            fn, fn_edges = _process_function(defn, outer, path, repo_root, source, file_qname, None)
            nodes.append(fn)
            edges.extend(fn_edges)

        elif defn.type == TSNodeType.CLASS_DEF:
            cls, cls_edges = _process_class(defn, outer, path, repo_root, source, file_qname)
            nodes.append(cls)
            edges.extend(cls_edges)
            body = defn.child_by_field_name(TSFieldName.BODY)
            if body:
                for item in body.named_children:
                    mdefn, mouter = _unwrap(item)
                    if mdefn is None or mdefn.type != TSNodeType.FUNCTION_DEF:
                        continue
                    m, m_edges = _process_function(mdefn, mouter, path, repo_root, source, cls.qualified_name, cls.name)
                    nodes.append(m)
                    edges.extend(m_edges)
    return ParseResult(nodes, edges)


def parse_repo(file_paths: list[Path], repo_root: Path) -> ParseResult:
    """Parse a whole repo by walking parse_file across files and merging results.

    Builds and reuses one TSParser across all files (parser construction is cheap
    but reuse is cleaner). Aggregates nodes and edges into a single ParseResult.
    """
    ts_parser = make_ts_parser()
    all_nodes: list[Node] = []
    all_edges: list[Edge] = []
    for path in file_paths:
        result = parse_file(path, repo_root, ts_parser)
        all_nodes.extend(result.nodes)
        all_edges.extend(result.edges)
    return ParseResult(all_nodes, all_edges)


def extract_file_node(path: Path, repo_root: Path, source: bytes) -> Node:
    """Build the File node. One per parsed file.

    Other nodes link to it via DEFINED_IN.
    """
    line_count = source.count(b"\n") + 1
    qname = qualified_name(path, repo_root, [])
    return Node(
        path=str(path),
        qualified_name=qname,
        name=path.stem,
        kind=NodeKind.FILE,
        start_line=1,
        end_line=line_count,
        source="",
    )


def extract_function(
    ts_node: TSNode,
    file_path: Path,
    repo_root: Path,
    source: bytes,
    parent_class: str | None,
) -> Node:
    """Extract a function or method node.

    Decorator edges and names are handled externally in parse_file via
    extract_decorators on the decorated_definition wrapper node.
    """
    name = node_text(ts_node.child_by_field_name(TSFieldName.NAME), source)
    kind = NodeKind.METHOD if parent_class else NodeKind.FUNCTION
    parts = [parent_class, name] if parent_class else [name]
    qname = qualified_name(file_path, repo_root, parts)
    doc = get_docstring(ts_node, source)

    node = Node(
        path=str(file_path),
        qualified_name=qname,
        name=name,
        kind=kind,
        start_line=ts_node.start_point[0] + 1,
        end_line=ts_node.end_point[0] + 1,
        source=node_text(ts_node, source),
        parent_class=parent_class,
        docstring=doc,
    )
    return node


def extract_decorators(
    ts_node: TSNode, decorated_qualified_name: str, source: bytes
) -> tuple[list[str], list[Edge]]:
    """Walk decorator nodes attached to a function/class definition.

    Returns:
      - list of raw decorator strings for storage on the decorated node
      - list of DECORATED_BY edges from decorated_qualified_name to each decorator
    """
    decorators: list[str] = []
    edges: list[Edge] = []
    for child in ts_node.children:
        if child.type != TSNodeType.DECORATOR:
            continue
        name_node = child.named_children[0] if child.named_children else None
        if name_node:
            text = node_text(name_node, source)
            decorators.append(text)
            edges.append(
                Edge(decorated_qualified_name, text, EdgeKind.DECORATED_BY)
            )
    return decorators, edges


def _inherits_from_edges(qname: str, ts_node: TSNode, source: bytes) -> list[Edge]:
    args = ts_node.child_by_field_name(TSFieldName.SUPERCLASSES)
    return [
        Edge(qname, node_text(base, source), EdgeKind.INHERITS_FROM)
        for base in (args.named_children if args else [])
        if base.type in (TSNodeType.IDENTIFIER, TSNodeType.ATTRIBUTE)
    ]


def extract_class(
    ts_node: TSNode, file_path: Path, repo_root: Path, source: bytes
) -> tuple[Node, list[Edge]]:
    name = node_text(ts_node.child_by_field_name(TSFieldName.NAME), source)
    qname = qualified_name(file_path, repo_root, [name])
    edges = _inherits_from_edges(qname, ts_node, source)

    doc = get_docstring(ts_node, source)
    node = Node(
        path=str(file_path),
        qualified_name=qname,
        name=name,
        kind=NodeKind.CLASS,
        start_line=ts_node.start_point[0] + 1,
        end_line=ts_node.end_point[0] + 1,
        source=node_text(ts_node, source),
        docstring=doc,
    )
    return node, edges


def extract_calls(
    ts_node: TSNode, enclosing_qualified_name: str, source: bytes
) -> list[Edge]:
    body = ts_node.child_by_field_name(TSFieldName.BODY)
    if not body:
        return []
    edges: list[Edge] = []
    stack: list[TSNode] = list(body.named_children)
    while stack:
        node = stack.pop()
        if node.type in TS_DEFINITION_TYPES or node.type == TSNodeType.DECORATED_DEF:
            continue
        if node.type == TSNodeType.CALL:
            func = node.child_by_field_name(TSFieldName.FUNCTION)
            if func:
                # TODO(v1): resolve textual callee name to qualified_name
                edges.append(Edge(enclosing_qualified_name, node_text(func, source), EdgeKind.CALLS))
        stack.extend(node.named_children)
    return edges


def _import_name_node(child: TSNode) -> TSNode | None:
    if child.type == TSNodeType.DOTTED_NAME:
        return child
    if child.type == TSNodeType.ALIASED_IMPORT:
        return child.child_by_field_name(TSFieldName.NAME)
    return None  # TODO(v1): handle wildcard_import (from x import *)


def _plain_import_edges(
    ts_node: TSNode, file_qualified_name: str, source: bytes
) -> list[Edge]:
    edges: list[Edge] = []
    for child in ts_node.named_children:
        name_node = _import_name_node(child)
        if name_node:
            edges.append(Edge(file_qualified_name, node_text(name_node, source), EdgeKind.IMPORTS))
    return edges


def _from_import_edges(
    ts_node: TSNode, file_qualified_name: str, source: bytes
) -> list[Edge]:
    module_node = ts_node.child_by_field_name(TSFieldName.MODULE_NAME)
    module_name = node_text(module_node, source) if module_node else ""
    edges: list[Edge] = []
    for child in ts_node.named_children:
        if child is module_node:
            continue
        name_node = _import_name_node(child)
        if name_node is None:
            continue
        name = node_text(name_node, source)
        edges.append(Edge(file_qualified_name, f"{module_name}.{name}" if module_name else name, EdgeKind.IMPORTS))
    return edges


def extract_imports(
    ts_node: TSNode, file_qualified_name: str, source: bytes
) -> list[Edge]:
    if ts_node.type == TSNodeType.IMPORT:
        return _plain_import_edges(ts_node, file_qualified_name, source)
    if ts_node.type == TSNodeType.IMPORT_FROM:
        return _from_import_edges(ts_node, file_qualified_name, source)
    return []


def get_docstring(ts_node: TSNode, source: bytes) -> str | None:
    """Return the first-statement string literal of a function/class body, if any."""
    body = ts_node.child_by_field_name(TSFieldName.BODY)
    if not body or not body.named_children:
        return None
    first = body.named_children[0]
    if first.type == TSNodeType.EXPRESSION_STMT and first.named_children and first.named_children[0].type == TSNodeType.STRING:
        return node_text(first.named_children[0], source)
    return None


def node_text(ts_node: TSNode, source: bytes) -> str:
    """Slice the original source bytes for an AST node and decode to str."""
    return source[ts_node.start_byte:ts_node.end_byte].decode(SOURCE_ENCODING)


def qualified_name(file_path: Path, repo_root: Path, parts: list[str]) -> str:
    """Compose the canonical symbol identifier for vector metadata and graph node ID.

    Example: 'src.auth.validators.EmailValidator.check'.
    Path components are joined with dots, dropping the .py extension.
    """
    rel = file_path.relative_to(repo_root)
    module_parts = list(rel.with_suffix("").parts)
    return ".".join(module_parts + parts)


def make_ts_parser() -> TSParser:
    """Construct a tree-sitter Parser configured for Python. Cheap; safe to reuse."""
    return TSParser(language=_PY_LANGUAGE)

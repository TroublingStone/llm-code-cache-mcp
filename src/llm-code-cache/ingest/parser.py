from pathlib import Path

from ingest.enums.edge_kind import EdgeKind
from ingest.enums.node_kind import NodeKind
from ingest.models import Edge, Node, ParseResult
from tree_sitter import Language
from tree_sitter import Node as TSNode
from tree_sitter import Parser as TSParser
from tree_sitter_python import language as _ts_py_lang

_PY_LANGUAGE = Language(_ts_py_lang())

_DEFINITION_TYPES = frozenset({"function_definition", "class_definition"})


def _unwrap(node: TSNode) -> tuple[TSNode | None, TSNode]:
    """Return (definition_node, outer_node) for a top-level or class-body child.

    For a decorated_definition, outer is the wrapper (holds decorator children)
    and definition is the inner function_definition or class_definition.
    For a bare function/class definition, both are the same node.
    Returns (None, node) for any other node type.
    """
    if node.type == "decorated_definition":
        inner = next(
            (c for c in node.named_children if c.type in _DEFINITION_TYPES),
            None,
        )
        return inner, node
    if node.type in _DEFINITION_TYPES:
        return node, node
    return None, node


def parse_file(path: Path, repo_root: Path, ts_parser: TSParser) -> ParseResult:
    """Parse a single file and return its nodes + edges.

    ParseResult has two fields: nodes (list[Node]) and edges (list[Edge]).
    Both lists may be empty if the file is empty or has only whitespace.
    Raises on syntax errors in v0; later we'll log and skip.
    """
    source = path.read_bytes()
    tree = ts_parser.parse(source)

    file_node = extract_file_node(path, repo_root)
    nodes: list[Node] = [file_node]
    edges: list[Edge] = []
    file_qname = file_node.qualified_name

    for child in tree.root_node.named_children:
        if child.type in ("import_statement", "import_from_statement"):
            edges.extend(extract_imports(child, file_qname, source))
            continue

        defn, outer = _unwrap(child)
        if defn is None:
            continue

        if defn.type == "function_definition":
            fn, fn_edges = extract_function(
                defn, path, repo_root, source, parent_class=None
            )
            nodes.append(fn)
            edges.extend(fn_edges)
            edges.extend(extract_decorators(outer, fn.qualified_name, source)[1])
            edges.append(Edge(fn.qualified_name, file_qname, EdgeKind.DEFINED_IN))
            edges.extend(extract_calls(defn, fn.qualified_name, source))

        elif defn.type == "class_definition":
            cls, cls_edges = extract_class(defn, path, repo_root, source)
            nodes.append(cls)
            edges.extend(cls_edges)
            edges.extend(extract_decorators(outer, cls.qualified_name, source)[1])
            edges.append(Edge(cls.qualified_name, file_qname, EdgeKind.DEFINED_IN))

            body = defn.child_by_field_name("body")
            if body:
                for item in body.named_children:
                    mdefn, mouter = _unwrap(item)
                    if mdefn is None or mdefn.type != "function_definition":
                        continue
                    m, m_edges = extract_function(
                        mdefn, path, repo_root, source, parent_class=cls.name
                    )
                    nodes.append(m)
                    edges.extend(m_edges)
                    _, dec_edges = extract_decorators(mouter, m.qualified_name, source)
                    edges.extend(dec_edges)
                    edges.append(
                        Edge(m.qualified_name, cls.qualified_name, EdgeKind.DEFINED_IN)
                    )
                    edges.extend(extract_calls(mdefn, m.qualified_name, source))

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


def extract_file_node(path: Path, repo_root: Path) -> Node:
    """Build the File node. One per parsed file.

    Other nodes link to it via DEFINED_IN.
    """
    source_bytes = path.read_bytes()
    line_count = source_bytes.count(b"\n") + 1
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
) -> tuple[Node, list[Edge]]:
    """Extract a function or method node.

    Decorator edges are handled externally in parse_file via extract_decorators
    on the decorated_definition wrapper node. Returns the function Node and an
    empty edge list (reserved for future intra-function edges).
    """
    name = node_text(ts_node.child_by_field_name("name"), source)
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
    return node, []


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
        if child.type == "decorator":
            name_node = child.named_children[0] if child.named_children else None
            if name_node:
                text = node_text(name_node, source)
                decorators.append(text)
                edges.append(
                    Edge(decorated_qualified_name, text, EdgeKind.DECORATED_BY)
                )
    return decorators, edges


def extract_class(
    ts_node: TSNode, file_path: Path, repo_root: Path, source: bytes
) -> tuple[Node, list[Edge]]:
    """Extract a class node from a class_definition AST node.

    Returns the class Node plus any INHERITS_FROM edges to base classes.
    Note: inheritance edges may point to unresolved names in v0 (e.g., 'BaseValidator'
    rather than a fully-qualified target). Resolution happens later.
    """
    name = node_text(ts_node.child_by_field_name("name"), source)
    qname = qualified_name(file_path, repo_root, [name])
    edges: list[Edge] = []

    args = ts_node.child_by_field_name("superclasses")
    if args:
        for base in args.named_children:
            if base.type in ("identifier", "attribute"):
                edges.append(
                    Edge(qname, node_text(base, source), EdgeKind.INHERITS_FROM)
                )

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
    """Walk a function/method body and emit CALLS edges for every call site.

    v0: edges record the *textual* callee name (e.g., 'helpers.check_format'),
    not the resolved target. A later resolution pass rewrites these.
    """
    edges: list[Edge] = []

    def walk(node: TSNode) -> None:
        if node.type == "call":
            func = node.child_by_field_name("function")
            if func:
                edges.append(
                    Edge(
                        enclosing_qualified_name,
                        node_text(func, source),
                        EdgeKind.CALLS,
                    )
                )
        for child in node.named_children:
            walk(child)

    body = ts_node.child_by_field_name("body")
    if body:
        walk(body)
    return edges


def extract_imports(
    ts_node: TSNode, file_qualified_name: str, source: bytes
) -> list[Edge]:
    """Walk top-level import statements and emit IMPORTS edges from the file."""
    edges: list[Edge] = []

    if ts_node.type == "import_statement":
        for child in ts_node.named_children:
            if child.type == "dotted_name":
                edges.append(
                    Edge(
                        file_qualified_name, node_text(child, source), EdgeKind.IMPORTS
                    )
                )
            elif child.type == "aliased_import":
                name_node = child.child_by_field_name("name")
                if name_node:
                    edges.append(
                        Edge(
                            file_qualified_name,
                            node_text(name_node, source),
                            EdgeKind.IMPORTS,
                        )
                    )

    elif ts_node.type == "import_from_statement":
        module = ts_node.child_by_field_name("module_name")
        module_name = node_text(module, source) if module else ""
        for child in ts_node.named_children:
            if child == module:
                continue
            if child.type == "dotted_name":
                imported = node_text(child, source)
                target = f"{module_name}.{imported}" if module_name else imported
                edges.append(Edge(file_qualified_name, target, EdgeKind.IMPORTS))
            elif child.type == "aliased_import":
                name_node = child.child_by_field_name("name")
                if name_node:
                    imported = node_text(name_node, source)
                    target = f"{module_name}.{imported}" if module_name else imported
                    edges.append(Edge(file_qualified_name, target, EdgeKind.IMPORTS))

    return edges


def get_docstring(ts_node: TSNode, source: bytes) -> str | None:
    """Return the first-statement string literal of a function/class body, if any."""
    body = ts_node.child_by_field_name("body")
    if not body or not body.named_children:
        return None
    first = body.named_children[0]
    if first.type == "expression_statement":
        expr = first.named_children[0] if first.named_children else None
        if expr and expr.type == "string":
            return node_text(expr, source)
    return None


def node_text(ts_node: TSNode, source: bytes) -> str:
    """Slice the original source bytes for an AST node and decode to str."""
    return source[ts_node.start_byte:ts_node.end_byte].decode("utf-8")


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

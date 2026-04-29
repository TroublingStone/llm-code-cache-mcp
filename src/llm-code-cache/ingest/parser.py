from pathlib import Path
from tree_sitter import Node as TSNode, Parser as TSParser

from ingest.models import Node, Edge, ParseResult
from ingest.enums.node_kind import NodeKind
from ingest.enums.edge_kind import EdgeKind



def parse_file(path: Path, repo_root: Path, ts_parser: TSParser) -> ParseResult:
    """Parse a single file and return its nodes + edges.

    ParseResult has two fields: nodes (list[Node]) and edges (list[Edge]).
    Both lists may be empty if the file is empty or has only whitespace.
    Raises on syntax errors in v0; later we'll log and skip.
    """
    ...


def parse_repo(file_paths: list[Path], repo_root: Path) -> ParseResult:
    """Parse a whole repo by walking parse_file across files and merging results.

    Builds and reuses one TSParser across all files (parser construction is cheap
    but reuse is cleaner). Aggregates nodes and edges into a single ParseResult.
    """
    ...



def extract_file_node(path: Path, repo_root: Path) -> Node:
    """Build the File node. One per parsed file. Other nodes link to it via DEFINED_IN."""
    ...


def extract_function(
    ts_node: TSNode, file_path: Path, source: bytes, parent_class: str | None
) -> tuple[Node, list[Edge]]:
    """...

    Now also extracts @decorators above the function. Returns the function Node
    plus DECORATED_BY edges (one per decorator). Decorator names are unresolved
    text references in v0; resolution pass rewrites them later.
    """
    ...

def extract_decorators(
    ts_node: TSNode, decorated_qualified_name: str, source: bytes
) -> tuple[list[str], list[Edge]]:
    """Walk decorator nodes attached to a function/class definition.

    Returns:
      - list of raw decorator strings (e.g. ['app.route("/users/<id>")', 'require_auth'])
        for storage on the decorated node
      - list of DECORATED_BY edges from decorated_qualified_name to each decorator's name
    """
    ...

def extract_class(ts_node: TSNode, file_path: Path, source: bytes) -> tuple[Node, list[Edge]]:
    """Extract a class node from a class_definition AST node.

    Returns the class Node plus any INHERITS_FROM edges to base classes.
    Note: inheritance edges may point to unresolved names in v0 (e.g., 'BaseValidator'
    rather than a fully-qualified target). Resolution happens later.
    """
    ...


def extract_calls(
    ts_node: TSNode, enclosing_qualified_name: str, source: bytes
) -> list[Edge]:
    """Walk a function/method body and emit CALLS edges for every call site.

    v0: edges record the *textual* callee name (e.g., 'helpers.check_format'),
    not the resolved target. A later resolution pass rewrites these.
    """
    ...


def extract_imports(ts_node: TSNode, file_qualified_name: str, source: bytes) -> list[Edge]:
    """Walk top-level import statements and emit IMPORTS edges from the file."""
    ...



def get_docstring(ts_node: TSNode, source: bytes) -> str | None:
    """Return the first-statement string literal of a function/class body, if any."""
    ...


def node_text(ts_node: TSNode, source: bytes) -> str:
    """Slice the original source bytes for an AST node and decode to str."""
    ...


def qualified_name(file_path: Path, repo_root: Path, parts: list[str]) -> str:
    """Compose the canonical symbol identifier used as both vector metadata
    and graph node ID. Example: 'src.auth.validators.EmailValidator.check'.
    Path components are joined with dots, dropping the .py extension.
    """
    ...


def make_ts_parser() -> TSParser:
    """Construct a tree-sitter Parser configured for Python. Cheap; safe to reuse."""
    parser = TSParser(_PY_LANGUAGE)
    return parser
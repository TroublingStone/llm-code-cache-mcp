"""FastMCP stdio server exposing the three v0 query primitives.

Thin adapter: each tool unwraps the connected stores from the lifespan
context and delegates to ``llm_code_cache.query``. Tool docstrings are
prompt engineering for the calling agent — keep them precise.
"""
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import Context, FastMCP

from llm_code_cache.config import AppConfig
from llm_code_cache.graph.store import GraphStore
from llm_code_cache.query import DefinitionResult, SemanticHit, Usage
from llm_code_cache.query import find_definition as _find_definition
from llm_code_cache.query import find_usages as _find_usages
from llm_code_cache.query import semantic_query as _semantic_query
from llm_code_cache.vector.embeddings import make_embed_model
from llm_code_cache.vector.store import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class ServerState:
    graph: GraphStore
    vector: VectorStore


@asynccontextmanager
async def lifespan(_server: FastMCP) -> AsyncIterator[ServerState]:
    config = AppConfig.from_env()
    embed_model = make_embed_model(config.embedding)
    graph = GraphStore(config.graph)
    vector = VectorStore(config.vector, config.embed_dim, embed_model)
    graph.connect()
    try:
        vector.connect()
        logger.info("mcp server ready")
        yield ServerState(graph=graph, vector=vector)
    finally:
        vector.close()
        graph.close()


mcp = FastMCP(
    "llm-code-cache",
    instructions=(
        "Persistent structural and semantic knowledge of a Python codebase. "
        "Use these tools instead of grepping when you need symbol-level facts: "
        "definitions, callers/importers/subclasses, or natural-language code search."
    ),
    lifespan=lifespan,
)


def _state(ctx: Context) -> ServerState:
    return ctx.request_context.lifespan_context


@mcp.tool()
def find_definition(ctx: Context, qualified_name: str) -> DefinitionResult | None:
    """Resolve a fully-qualified Python symbol to its definition.

    Input: a canonical ``qualified_name`` such as ``pkg.module.Class.method``
    or ``pkg.module.function``. Returns the source, file path, line range,
    docstring, parent class, and decorators of the definition, or ``None`` if
    no symbol with that exact name is indexed.

    Use when you already know the identifier and want the canonical
    definition. If you only have a fuzzy description (e.g. "the JWT
    validator"), call ``semantic_query`` first to obtain a qualified_name,
    then call this tool.
    """
    return _find_definition(_state(ctx).graph, qualified_name)


@mcp.tool()
def find_usages(ctx: Context, qualified_name: str) -> list[Usage]:
    """List incoming references to a Python symbol.

    Returns callers (CALLS), importers (IMPORTS), subclasses
    (INHERITS_FROM), and decorator users (DECORATED_BY) of the given
    ``qualified_name``. Each entry includes the calling/importing symbol's
    location so you can navigate to it.

    Use to scope blast-radius before changing a function or class, or to
    find existing usage patterns of an API. Requires an exact
    ``qualified_name``; obtain one from ``find_definition`` or
    ``semantic_query``. Note: in v0, references to symbols that haven't
    been resolved yet appear as ``text_ref`` entries instead of full
    ``qualified_name`` matches.
    """
    return _find_usages(_state(ctx).graph, qualified_name)


@mcp.tool()
def semantic_query(ctx: Context, query: str, top_k: int = 5) -> list[SemanticHit]:
    """Search the indexed codebase by natural-language description.

    Input: a free-form description such as "JWT token validation" or
    "database connection pool setup". Returns up to ``top_k`` ranked hits
    over indexed functions, methods, and classes, each with source,
    docstring, parent class, decorators, and a ``qualified_name`` you can
    pass to ``find_definition`` or ``find_usages``.

    Use when you don't know the exact symbol name. Prefer
    ``find_definition``/``find_usages`` once you have a qualified_name —
    they are precise; this is fuzzy.
    """
    state = _state(ctx)
    return _semantic_query(state.vector, state.graph, query, top_k=top_k)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

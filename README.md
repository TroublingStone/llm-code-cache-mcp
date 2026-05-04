# Codebase Intelligence MCP Server

> Hybrid Graph + vector RAG over codebases, exposed as MCP tools for AI coding agents.
> Designed to give agents the structural fluency with private code that they already have with public code.

**Status:** In active development.

---

## The Problem

AI coding agents are remarkably good at navigating *open-source* code. They've seen Django, React, and the Python standard library during pretraining, and they reason fluently about them.

They are remarkably *bad* at navigating private code. The internal library that twenty services in your company depend on? The agent has never seen it. It hallucinates parameter names, invents methods that don't exist, misses required setup, and confidently misuses functions whose real behavior is documented only in the library's own source.

This isn't a model-quality problem. It's an *information* problem: the relevant code isn't in pretraining data, and it doesn't fit in a single agent session's context window. Every session starts cold. Every agent rediscovers the same internal API badly. Every time.

This project addresses that gap.

## The Approach

Two ideas, combined:

**1. Treat code structure as a queryable knowledge base, not as text to reread per session.**
Parse codebases once into a persistent graph (functions, classes, calls, imports, inheritance) plus a parallel vector index. Queries against this knowledge base are deterministic, fast, and don't consume the agent's context window. The work is done at index time and amortized over thousands of queries.

**2. Expose this as an MCP server so any agent can use it.**
Any MCP-compatible agent — Claude Code, Cursor, others — can use the tools without project-specific integration.

The architectural pattern, generalized: **domain-aware Graph + vector RAG, exposed as composable MCP tools.** Code is the first instance; the same pattern applies to legal documents, medical records, or any domain where relationships carry meaning beyond text similarity.

## Why Hybrid Retrieval

Vector search alone fails on structural questions ("what calls this function transitively?"). Graph traversal alone fails on semantic questions ("find code that handles authentication"). Real questions about code mix both shapes.

| Question | Right tool |
|---|---|
| "Find code that handles database connections" | Vector — agent doesn't know what to look for by name |
| "What functions does `process_order` eventually call?" | Graph — precise traversal of `CALLS` edges |
| "If I change the signature of `validate`, what breaks?" | Graph — transitive caller analysis |
| "Find similar functions to `process_order` that might refactor together" | Hybrid — vector for similarity, graph to scope by module |

The agent picks per query. Tool descriptions are written so the right choice is unambiguous.

## Status

v0, in active development. End-to-end pipeline runs and the MCP server starts; not yet hardened or used in anger.

What works today:
- Single-repo, Python-only indexing via a CLI (`llm-code-cache-index`).
- One parser feeds both stores: Neo4j for `File`/`Function`/`Method`/`Class` nodes and `CALLS`/`IMPORTS`/`DEFINED_IN`/`INHERITS_FROM`/`DECORATED_BY` edges; pgvector for embeddings of functions, methods, and classes.
- Three MCP tools over stdio: `find_definition`, `find_usages`, `semantic_query`.
- Cross-store identity: every vector hit's `qualified_name` is a real graph node, so semantic results can be pivoted into structural traversals.
- Swappable embedding backend: HuggingFace local (default) or Amazon Bedrock Titan via env config.

Known limitations:
- Symbol resolution is textual. A call like `helper.validate(...)` records `helper.validate` as the edge target, not `utils.helpers.validate`. A resolution pass is planned for v1; until then, `find_usages` is approximate.
- No incremental indexing; every run is a full reindex of the target tree.
- The MCP server has been verified via its underlying query layer but has not been driven by a live MCP client yet (Inspector, Claude Code, etc.).
- Multi-language, cross-repo indexing, watch mode, composite tools, and HTTP transport are explicitly out of scope for v0.

See [CLAUDE.md](./CLAUDE.md) for the full v0 scope and [DESIGN.md](./DESIGN.md) for architectural reasoning.

## Quickstart

Prerequisites: Docker (with `docker compose`), [`uv`](https://docs.astral.sh/uv/), Python 3.14+.

```bash
# 1. Start Neo4j + Postgres (pgvector) via docker-compose
docker compose up -d

# 2. Install dependencies into a local .venv
uv sync --extra dev

# 3. Index a Python repository (use --clear on subsequent runs to drop stale data)
uv run llm-code-cache-index ./path/to/repo --clear

# 4. Run the MCP server (stdio transport; foreground)
uv run llm-code-cache-mcp
```

To register the server with an MCP client (e.g. Claude Desktop, Claude Code), add an entry like:

```json
{
  "mcpServers": {
    "llm-code-cache": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/llm-code-cache-mcp", "llm-code-cache-mcp"]
    }
  }
}
```

Defaults assume the docker-compose services on `localhost` with the credentials shipped in `docker-compose.yml`. Override via environment variables (`NEO4J_URI`, `NEO4J_PASSWORD`, `PG_HOST`, `EMBED_PROVIDER`, `EMBED_MODEL_NAME`, `AWS_REGION`, …); see `src/llm_code_cache/config.py` for the full list.

## MCP Tools

| Tool | Use when | Returns |
|---|---|---|
| `find_definition(qualified_name)` | You already know the canonical name (e.g. `pkg.module.Class.method`) and want its source. | Source, file path, line range, docstring, parent class, decorators. |
| `find_usages(qualified_name)` | You need callers, importers, subclasses, or decorator users of a known symbol. | List of incoming references with location. v0 references are textual; expect false positives for common names. |
| `semantic_query(query, top_k=5)` | You only have a fuzzy description ("JWT validation"). | Ranked hits with `qualified_name` you can hand to the other two tools. |

Tool docstrings in the MCP server are deliberate: they instruct the calling agent on which tool to pick. Composite tools (e.g. blast-radius analysis) are deferred until observed usage justifies them.

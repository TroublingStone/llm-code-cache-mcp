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

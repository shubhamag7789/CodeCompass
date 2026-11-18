# Changelog

All notable changes to RepoMind are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-07-18

First public release: the local, offline‑first MVP.

### Added
- **Repository analyzer** (`analyzer.py`) — builds a knowledge graph (directories, files, classes, functions, methods, imports, calls, inheritance, tests, external dependencies) plus a repository summary, primary components, architecture layers, and detected entry points.
- **Language parsing** — Python via the `ast` module; JavaScript, TypeScript, JSX, TSX, and Java via lightweight parsers.
- **API map** — detection for FastAPI, Flask, Express, Next.js route handlers, and Spring.
- **Onboarding guide** — auto‑generated "where to start" guide.
- **Change impact analysis** — per‑node affected files, APIs, and tests with a Low/Medium/High risk rating (2‑hop reverse dependency walk).
- **Zero‑dependency code search** (`retrieval.py`) — in‑process **lexical** BM25 index with identifier‑aware tokenization and structural boosts (no embeddings).
- **Repository‑aware AI chat** (`assistant.py`) — retrieval‑grounded answers with file + line citations, and a local extractive fallback when no key is configured.
- **Multi‑turn conversations** (`conversation.py`) — in‑process, capped conversation memory with follow‑up reference resolution (`it`, `that function`, `this module`) and context‑aware retrieval.
- **Optional OpenRouter integration** (`integrations/llm.py`) — standard‑library `urllib` client, active only when `OPENROUTER_API_KEY` is set.
- **Dashboard + JSON API** (`server.py`, `static/`) — standard‑library HTTP server with `/api/analysis`, `/api/impact`, `/api/analyze`, `/api/ask`, `/api/chat`, and a vanilla HTML/CSS/JS UI (Overview, Graph, APIs, Impact, Guide).
- **CLI** — `repomind analyze` and `repomind serve` (plus `python -m repomind`).
- **Optional integration boundaries** — Neo4j (`graph_store.py`) and Qdrant (`vector_store.py`) stubs documenting future, opt‑in backends.
- **Test suite** — standard‑library `unittest` covering the analyzer, retrieval, assistant/LLM wiring, and multi‑turn conversations.

### Notes
- No third‑party dependencies (`pyproject.toml` declares `dependencies = []`).
- No external infrastructure required; no LLM key required.

[0.1.0]: https://github.com/Philipcyrus/RepoMind/releases/tag/v0.1.0

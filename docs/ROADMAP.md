# Roadmap

RepoMind's guiding constraint never changes: **zero third‑party dependencies and an offline‑first default.** Every item below must degrade gracefully with no configuration and add no required infrastructure.

## ✅ v0.1.0 — Local MVP (current)

Shipped and covered by the test suite:

- Repository analyzer → knowledge graph (`analyzer.py`)
- Repository summary, components, architecture layers, entry points
- API map (FastAPI, Flask, Express, Next.js, Spring)
- Onboarding guide generation
- Change impact analysis (2‑hop reverse dependency walk + risk rating)
- Zero‑dependency BM25 code search — lexical, no embeddings (`retrieval.py`)
- Repository‑aware AI chat with citations + local extractive fallback (`assistant.py`)
- Multi‑turn conversations with reference resolution (`conversation.py`)
- Optional OpenRouter integration (`integrations/llm.py`)
- Stdlib dashboard + JSON API (`server.py`, `static/`)

## 🔜 Near term

- **Symbol‑boundary chunking** for retrieval — chunk on function/class boundaries (using the analyzer's existing line numbers) for more precise snippets.
- **More API frameworks** and improved route detection (path params, method extraction edge cases).
- **Richer dashboard** — clickable graph navigation into the Impact and API views.
- **CLI `ask` command** — one‑shot question answering from the terminal (reusing `assistant.py`).

## 🧭 Optional integrations (behind existing boundaries)

These activate only when a user opts in; the MVP never requires them.

- **Embeddings layer (Qdrant)** — implement `integrations/vector_store.py` behind the current `search()` contract for true semantic matching beyond keyword/identifier overlap.
- **Graph export (Neo4j)** — implement `integrations/graph_store.py` to export very large graphs for external querying.
- **Additional LLM providers** — the `integrations/llm.py` boundary can host more providers alongside OpenRouter.

## 🌐 Longer term

- **Deeper analysis** — cross‑file call‑graph precision, GraphQL/gRPC detection.
- **GitHub App** — one‑click analysis, repository syncing, and continuous updates.
- **Docs sync** — keep generated onboarding/architecture docs aligned with the code over time.

## Explicitly out of scope for the core MVP

To protect the zero‑infrastructure promise, the default install will **not** require: Docker, a database, Redis, a message queue (e.g. Celery), a web framework (e.g. FastAPI), or authentication infrastructure (e.g. JWT). Such tools may appear only as **optional**, clearly‑gated integrations.

> Have an idea? Open a [feature request](https://github.com/Philipcyrus/RepoMind/issues/new/choose).

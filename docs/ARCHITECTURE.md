# Architecture

This document describes how RepoMind v0.1.0 actually works, module by module. It reflects the code in `repomind/` — not aspirational design.

## Design principles

1. **Zero third‑party dependencies.** `pyproject.toml` declares `dependencies = []`. Everything runs on the Python 3.11+ standard library (`ast`, `re`, `http.server`, `urllib`, `threading`, `uuid`, `json`, `hashlib`).
2. **Offline‑first.** No Neo4j, Qdrant, Docker, database, or queue is required. No LLM key is required.
3. **Graceful enhancement.** Optional integrations (currently OpenRouter) light up when configured and degrade cleanly when not.
4. **Single artifact.** Analysis is a plain JSON file (`.repomind/analysis.json`); the search index is a sibling (`.repomind/index.json`).

## High‑level pipeline

```
Repository ──► analyzer.py ──► analysis.json ──► server.py ──► static/ dashboard
                    │                                  ▲
                    └──► retrieval.py ──► index.json ──┘
                                          │
                        assistant.py / conversation.py (grounded answers)
                                          │
                            integrations/llm.py (optional OpenRouter)
```

## Modules

### `cli.py` — command line
`argparse`‑based. Two subcommands:

- `analyze <target> [--output PATH] [--json]` — analyzes a local path or a GitHub URL. If the target looks like a URL, it shallow‑clones with `git` into a temporary directory (cleaned up afterward). Writes `analysis.json` and builds/writes `index.json`.
- `serve [--analysis PATH] [--host HOST] [--port PORT]` — starts the dashboard server.

Console entry point: `repomind = repomind.cli:main` (see `pyproject.toml`). `python -m repomind` routes through `__main__.py`.

### `analyzer.py` — parsing and the knowledge graph
The core. `analyze_repository(target)` returns a dict with:

- `repository`, `summary` (headline, languages, primary components, entry points, architecture layers, stats),
- `components`, `files`, `apis`,
- `nodes` and `relationships` (the knowledge graph),
- `onboarding` (generated guide),
- `impact_index` (see below).

**Parsers:**
- **Python** — parsed with the `ast` module (imports, classes, functions, methods, calls, inheritance, and decorator‑based routes for FastAPI/Flask). Falls back to a regex scan on `SyntaxError`.
- **JavaScript / TypeScript / JSX / TSX** — lightweight regex extraction of imports, classes, functions, `app/router/server.<method>(...)` routes, Next.js `route.*` handlers, and call names.
- **Java** — regex extraction of imports, classes, inheritance, `@…Mapping` routes, and methods.

**Graph model:** node types `Repository`, `Directory`, `File`, `Class`, `Function`, `Method`, `API`, `ExternalDependency`; relationship types include `CONTAINS`, `IMPORTS`, `CALLS`, `EXTENDS`, `TESTS`.

**Impact index:** `_build_impact_index` performs a **2‑hop reverse‑dependency walk** over the graph for every File/Class/Function/Method/API node, producing affected files, affected APIs, affected tests, and a `Low`/`Medium`/`High` risk rating.

### `retrieval.py` — zero‑dependency code search (lexical BM25)
`build_index(root)` chunks source files into overlapping line windows (`CHUNK_LINES` / `CHUNK_STEP`, capped by `MAX_CHUNKS`) and stores them in `index.json`. `SearchIndex` provides `search(query, k)` using:

- **BM25** ranking (`_BM25_K1`, `_BM25_B`),
- **identifier‑aware tokenization** (`tokenize` splits `camelCase` and `snake_case`, drops stopwords),
- **structural boosts** — a query term that matches a chunk's file path or symbol label is weighted higher.

This is the same `search()` contract that a future embeddings backend (Qdrant) would implement — see `integrations/vector_store.py`.

### `assistant.py` — grounded answers
`answer_question(analysis, index, question, assistant=None)`:

1. Runs retrieval for the question.
2. Builds grounded context (`_build_context`) from the summary + top snippets.
3. If OpenRouter is configured, calls the LLM; otherwise returns `_local_answer` — an extractive answer built from retrieval and structural signals (routes, entry points, impact).

Every answer includes **sources** (file + line). This module powers the stateless `/api/ask`.

### `conversation.py` — multi‑turn memory
Adds conversation memory on top of `assistant.py` without changing it:

- `Turn`, `Conversation` (rolling, capped by `MAX_TURNS_PER_CONVERSATION`), and a thread‑safe `ConversationManager` (capped by `MAX_CONVERSATIONS`, guarded by a `threading.Lock`).
- `resolve_query(question, conversation)` — finds the **salient entity** from the last turn's citation and rewrites deictic references (_"it"_, _"that function"_, _"this module"_), then **augments the retrieval query** with terms from recent turns.
- `chat_answer(...)` — resolve → `search()` → LLM‑with‑history **or** local fallback → record the turn. Context is bounded by `MAX_HISTORY_TURNS` and `MAX_HISTORY_CHARS`.

This module powers `/api/chat`. All state is in‑process memory.

### `server.py` — dashboard + JSON API
Standard‑library `ThreadingHTTPServer`. Routes:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/analysis` | Return the loaded `analysis.json`. |
| GET | `/api/impact?id=<node_id>` | Return the impact entry for a node. |
| POST | `/api/analyze` | Analyze a path, rewrite analysis + index. |
| POST | `/api/ask` | Stateless, single‑shot grounded answer. |
| POST | `/api/chat` | Multi‑turn answer (`conversation_id`, `reset`). |
| GET | `/*` | Serve static dashboard assets. |

A single shared `ConversationManager` lives on the handler class.

### `static/` — the dashboard
Vanilla `index.html`, `app.js`, and `styles.css` — no framework, no build step. Tabs: Overview, Graph (canvas), APIs, Impact, Guide, plus the Repository Assistant (multi‑turn chat with citations and a reset control).

### `integrations/` — optional future boundaries
- `llm.py` — **implemented** OpenRouter client using `urllib` (activates only with `OPENROUTER_API_KEY`).
- `vector_store.py` — **stub** Qdrant boundary for a future embeddings layer.
- `graph_store.py` — **stub** Neo4j boundary for a future production graph.

The stubs document the contract; they are not used by the MVP and require no services.

## Data artifacts

| File | Written by | Contents |
| --- | --- | --- |
| `.repomind/analysis.json` | `analyzer.write_analysis` | Full knowledge map. |
| `.repomind/index.json` | `retrieval.write_index` | BM25 chunk index. |

Both live under `.repomind/`, which is git‑ignored. Re‑run `analyze` after code changes so retrieval reflects the latest code.

## Testing
`tests/` uses the standard‑library `unittest` (no pytest required):

```bash
python -B -m unittest discover -s tests -v
```

Covers analyzer parsing/routes, retrieval ranking + tokenization, the OpenRouter request wiring (mocked, no network), local fallback, and the full multi‑turn conversation surface (follow‑ups, pronoun resolution, long conversations, missing context, reset).

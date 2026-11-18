# Frequently Asked Questions

### What is CodeCompass?
A zero‑dependency, offline‑first developer tool that turns a repository into a searchable architecture map, an interactive dashboard, and a repository‑aware AI assistant. See the [README](../README.md).

### Do I need an API key or any external service?
No. The MVP runs entirely on the Python standard library. Code search (a lexical BM25 index) and the assistant's grounded, cited answers work with **no key and no services**. An OpenRouter key is **optional** and only upgrades the assistant's answers to LLM‑written prose.

### What are the requirements?
Python **3.11+**. That's it. `git` is only needed if you want to analyze a **GitHub URL** (CodeCompass shallow‑clones it to a temp directory).

### Which languages does it analyze?
- **Python** — parsed with the `ast` module (most detailed).
- **JavaScript / TypeScript / JSX / TSX** — lightweight regex parsing.
- **Java** — lightweight regex parsing.

Support is defined in `analyzer.py` (`SUPPORTED_EXTENSIONS`).

### Which API frameworks are detected?
FastAPI, Flask, Express, Next.js route handlers, and Spring (`@…Mapping`). Detection is heuristic and defined in `analyzer.py`.

### Is the code search "semantic" / embeddings‑based?
No. In v0.1.0 it is **lexical** (keyword) search: a pure‑Python **BM25** index with identifier‑aware tokenization (splits `camelCase`/`snake_case`) and structural boosts (matching a file path or symbol name ranks higher). There are **no embeddings** and no vector database. This keeps the tool key‑free and offline. A true **semantic** (embeddings) layer is a planned **optional** backend behind the same `search()` contract (`integrations/vector_store.py`). See the [Roadmap](ROADMAP.md).

### How does the AI chat avoid hallucinating?
Answers are **grounded** in retrieved code snippets and always include **file + line citations**. With no LLM key, the assistant returns an extractive answer built directly from retrieval and structural signals. With a key, the model is instructed to answer only from the provided repository context.

### How do multi‑turn conversations work?
`/api/chat` keeps a rolling, capped history in **in‑process memory** (a thread‑safe dict — no Redis or database). It resolves follow‑up references like _"it"_, _"that function"_, and _"this module"_ against the previously discussed code, and folds recent turns into both retrieval and the prompt. `/api/ask` remains stateless. Details in [ARCHITECTURE.md](ARCHITECTURE.md).

### Where is the analysis stored?
Two JSON files under `.codecompass/`: `analysis.json` (the knowledge map) and `index.json` (the search index). This folder is git‑ignored.

### The chat can't find code I just added — why?
The dashboard reads the on‑disk analysis and index. **Re‑run `python -m codecompass analyze .`** (or use the dashboard's Analyze button / `POST /api/analyze`) to refresh them after code changes.

### Why not use Neo4j / Qdrant / Docker / FastAPI?
To keep CodeCompass usable the instant you clone it, with nothing to set up. Those tools are represented as **optional future boundaries** (`integrations/`) and will only ever be opt‑in, never required by the core.

### Is my code sent anywhere?
Only if you configure OpenRouter. In that case, the question plus the relevant retrieved snippets and repository summary are sent to OpenRouter to generate an answer. With no key, nothing leaves your machine.

### How do I run the tests?
```bash
python -B -m unittest discover -s tests -v
```
Standard‑library `unittest`, no network required.

### How can I contribute or report a bug?
See [CONTRIBUTING.md](CONTRIBUTING.md) and use the issue templates. The one hard rule: keep it zero‑dependency and offline‑first.

# Contributing to CodeCompass

Thanks for your interest in improving CodeCompass! This project aims to be a polished, dependency‑free developer tool, and contributions of all sizes are welcome.

Please also read our [Code of Conduct](../CODE_OF_CONDUCT.md).

## The golden rule

**Keep CodeCompass zero‑dependency and offline‑first.**

- `pyproject.toml` must keep `dependencies = []`. Use the Python standard library.
- No new required infrastructure — no Docker, database, Redis, message queue, web framework, or auth system.
- New capabilities must **degrade gracefully** with no configuration. Optional enhancements (like OpenRouter) may exist only behind a clear opt‑in and must never be required.

If a change seems to need a dependency or a service, open an issue first so we can discuss an approach that preserves the philosophy.

## Getting set up

Requirements: **Python 3.11+**. No install step is needed to run from source.

```bash
git clone https://github.com/shubhamag7789/CodeCompass.git
cd CodeCompass

# Run it
python -m codecompass analyze .
python -m codecompass serve

# Optional: install the CLI entry point in editable mode
pip install -e .
```

## Running the tests

CodeCompass uses the standard‑library `unittest` runner (no pytest, no plugins):

```bash
python -B -m unittest discover -s tests -v
```

All tests must pass and run **without network access** — the OpenRouter path is exercised with a mocked `urlopen`, never a live call.

## Project layout

See [ARCHITECTURE.md](ARCHITECTURE.md) for a module‑by‑module tour. In short:

- `codecompass/analyzer.py` — parsing → knowledge graph (the heart of the tool)
- `codecompass/retrieval.py` — BM25 search
- `codecompass/assistant.py` / `conversation.py` — grounded Q&A and multi‑turn memory
- `codecompass/server.py` + `codecompass/static/` — dashboard and JSON API
- `codecompass/integrations/` — optional, gated boundaries

## Making a change

1. **Open an issue** for anything non‑trivial (bug or feature) so we can align first.
2. Create a branch from `main`.
3. Keep changes focused. Match the surrounding style (type hints, `from __future__ import annotations`, small helpers).
4. **Add or update tests** for behavior changes.
5. If you touch analysis output, remember to re‑run `analyze` — the dashboard reads `.codecompass/analysis.json`.
6. Update docs (`README.md`, `docs/`) when behavior or interfaces change.
7. Run the test suite and make sure it's green.
8. Open a pull request using the [PR template](../.github/PULL_REQUEST_TEMPLATE.md) and describe **what** and **why**.

## Coding conventions

- Python 3.11+, standard library only.
- Prefer clear, small functions and explicit names — match what's already in the file you're editing.
- Keep public JSON shapes and API routes **backward compatible** where possible; call out any breaking change explicitly.
- No secrets in the repo. `.env` is git‑ignored; only `.env.example` is tracked.

## Reporting bugs & requesting features

Use the issue templates:

- 🐞 [Bug report](https://github.com/shubhamag7789/CodeCompass/issues/new/choose)
- 💡 [Feature request](https://github.com/shubhamag7789/CodeCompass/issues/new/choose)

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](../LICENSE).

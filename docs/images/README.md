# Screenshots & demo assets

This folder holds the images referenced by the main [README](../../README.md). Replace these placeholders with real captures before publicly announcing the release.

Expected files:

| File | What to capture |
| --- | --- |
| `overview.png` | The dashboard **Overview** tab — summary, architecture layers, and the Repository Assistant. |
| `graph.png` | The **Graph** tab — the dependency graph with a filter applied. |
| `impact.png` | The **Impact** tab — a selected file showing affected files/APIs/tests and risk. |
| `demo.gif` | A short walkthrough: `analyze .` → `serve` → ask a question → ask a follow‑up. |

**How to capture:**

```bash
python -m codecompass analyze .
python -m codecompass serve
# open http://127.0.0.1:8765 and capture each tab
```

Keep images reasonably sized (e.g. ≤ 1600px wide) so the README loads quickly.

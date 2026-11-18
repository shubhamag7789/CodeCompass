# Pull Request

## Summary

<!-- What does this PR do, and why? -->

## Related issue

<!-- e.g. Closes #123 -->

## Type of change

- [ ] 🐞 Bug fix
- [ ] ✨ New feature
- [ ] 📝 Documentation
- [ ] ♻️ Refactor (no behavior change)
- [ ] 🧪 Tests
- [ ] 🔧 Tooling / meta

## Checklist

- [ ] Preserves **offline-first** default and Tree-sitter + SQLite architectural foundation.
- [ ] Preserves the **offline-first** default (no new required services/infrastructure; optional features are gated and degrade gracefully).
- [ ] Tests added or updated for behavior changes.
- [ ] `python -B -m unittest discover -s tests -v` passes locally.
- [ ] Docs updated (`README.md` / `docs/`) if behavior or interfaces changed.
- [ ] Public JSON shapes / API routes remain backward compatible (or the break is called out below).
- [ ] No secrets committed (`.env` stays local; only `.env.example` is tracked).

## Notes for reviewers

<!-- Anything reviewers should focus on, trade-offs, follow-ups, etc. -->

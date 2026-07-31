## What does this change do, and why?

<!-- One or two sentences. Link an issue if there is one. -->

## Checklist

- [ ] `ruff check .` passes
- [ ] `pytest -m "not embeddings"` passes locally
- [ ] `pytest -m embeddings` passes locally (only if you touched retrieval, dedup, or conflict
      detection — the semantic behavior calibrated for the `sentence-transformers` backend)
- [ ] Docs (`README.md`, `docs/*.qmd`) updated if this changes user-facing behavior
- [ ] `CHANGELOG.md` updated under `[Unreleased]` if this is a user-facing change

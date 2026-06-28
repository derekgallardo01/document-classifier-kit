# Changelog

Notable changes to the document classifier kit. Dates are when the
change landed on `main`.

## 2026-06-28 — Initial public release (v1.0.0)
- `schema.py` — declarative `Catalog` + `DocClass` with validation
  (catches duplicate names, empty keywords, non-positive SLAs)
- `classifier.py` — keyword + length-weighted rules backend, plus
  documented LLM backend swap point; router with three
  human-review paths
- 7 bundled fixtures (1 per class + 1 ambiguous)
- `cli.py` — `doc-classifier classify`, `doc-classifier demo`,
  `doc-classifier list-classes`, with `--json` output
- 23 pytest tests (schema + classifier + router + backend wiring)
- 7 golden eval cases asserting label per fixture; harness reports
  per-class precision / recall / F1 + overall accuracy
- CI gates on 100% accuracy on the bundled fixtures
- CI on Python 3.10/3.11/3.12 (tests + evals + CLI smoke)
- `pyproject.toml` with `[llm]` optional extra for `anthropic`
- Docs trio: `getting-started`, `architecture`, `customization`,
  `evaluation`, `diagrams`, `faq`
- OSS niceties: `CONTRIBUTING`, `CODE_OF_CONDUCT`, `SECURITY`,
  `CITATION.cff`, `.editorconfig`, `.devcontainer/devcontainer.json`,
  `.github/ISSUE_TEMPLATE/*`, `.github/PULL_REQUEST_TEMPLATE.md`,
  `.github/dependabot.yml`
- `Dockerfile`, `pages.yml` (live demo with per-doc card showing
  prediction, confidence, top-3, routing decision, review reason),
  `screenshots.yml`, `portfolio.yml`
- README badges: CI + License (MIT) + Python (3.10+) + Open in
  Codespaces
- Theme: violet (classification / routing)

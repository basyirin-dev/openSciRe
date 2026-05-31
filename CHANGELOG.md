# Changelog

## [0.1.0] — 2026-06-01

### Phase 0 — Repo & Agent Infrastructure

#### Added
- **Git repository** — initialized with `.gitignore` (Python, Rust, Node, env, IDE, OS), `.gitattributes` (cross-platform line endings, language diff mappings)
- **License files** — Apache 2.0 (`LICENSE`) and commercial license placeholder (`LICENSE-COMMERCIAL.md`); SPDX headers on all source files
- **Security documentation** — `SECURITY.md` (vulnerability disclosure, 72h SLA, 14d fix target, scope), `RESPONSIBLE_DISCLOSURE.md` (dual-use policy, prohibited uses, ethical concern reporting), `docs/threat-model.md` (attack surfaces, data classification, trust boundaries)
- **Root `README.md`** — project identity, philosophical stance, architecture diagram, quick start, ethical use section, license/CI/Python badges
- **Project configurations** — `pyproject.toml` (hatchling build, ruff/mypy/pytest/coverage config, dependency groups), `Cargo.toml` (workspace root), `Makefile` (install/lint/format/typecheck/test/clean/build/all/update-hooks)
- **Pre-commit hooks** — ruff, ruff-format, mypy, trailing-whitespace, end-of-file-fixer, YAML/TOML/JSON validation, large-file detection, merge-conflict check, private-key detection
- **GitHub templates** — bug report, feature request, ethics concern, RFC issue templates; PR template; CONTRIBUTING.md; CODEOWNERS
- **Citation metadata** — `CITATION.cff` (CFF 1.2.0, validated), `codemeta.json` (CodeMeta 3.0)
- **Critique library** — 8 documents (01–08) with philosophical and structural analysis of Gemini for Science
- **Documentation framework** — `docs/business-brief.md`, `docs/phase-roadmap.md`, 19 phase task breakdowns, cross-cutting concerns, risk register
- **Rust scaffold** — `skepsis-sandbox-core` workspace member with placeholder lib and test
- **Python scaffold** — `skepsis-core` package with `src/skepsis/__init__.py` stub

#### Fixed
- CITATION.cff `date-released` format (YYYY-MM → YYYY-MM-DD) and DOI placeholder pattern for CFF 1.2.0 schema compliance
- Cargo workspace `edition` field moved from workspace declaration to member crate
- pre-commit hooks updated to latest revisions (ruff v0.11→v0.15, mypy v1.15→v2.1, pre-commit-hooks v5→v6)

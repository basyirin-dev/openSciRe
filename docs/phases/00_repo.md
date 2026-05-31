# Phase 0 — Repo & Agent Infrastructure

**Duration**: 2 weeks (Jun 2026)
**Dependencies**: None
**Output**: Working repository with CI/CD, linting, project identity

---

### Task 0.1: Initialize Git Repository

- [ ] 0.1.1: Run `git init` in project root
- [ ] 0.1.2: Create `.gitignore` — Python (`__pycache__/`, `*.pyc`, `.egg-info/`, `dist/`, `build/`), Rust (`target/`), Node (`node_modules/`), environment (`.env`, `.venv`, `venv/`), IDE (`.vscode/`, `.idea/`), OS (`*.DS_Store`, `Thumbs.db`)
- [ ] 0.1.3: Create `.gitattributes` for cross-platform line endings (`* text=auto`, `*.py diff=python`, `*.md diff=markdown`)
- [ ] 0.1.4: Create initial commit with README, LICENSE, and structure

### Task 0.2: License Files

- [ ] 0.2.1: Add `LICENSE` file with Apache 2.0 full text
- [ ] 0.2.2: Add `LICENSE-COMMERCIAL.md` — placeholder for enterprise feature license terms
- [ ] 0.2.3: Add license header template for source files (`# SPDX-License-Identifier: Apache-2.0`)

### Task 0.3: Security Documentation

- [ ] 0.3.1: Create `SECURITY.md` — vulnerability reporting process, PGP key for encrypted disclosure, response SLA (72h acknowledgment, 14d fix target), scope definition
- [ ] 0.3.2: Create `RESPONSIBLE_DISCLOSURE.md` — dual-use research policy, prohibited use cases (weapons development, human subjects without IRB, surveillance), reporting channel for ethical concerns
- [ ] 0.3.3: Create initial threat model document at `docs/threat-model.md` — attack surfaces, data sensitivity classification, trust boundaries, mitigation priorities

### Task 0.4: Root README.md

- [ ] 0.4.1: Project name and one-line description
- [ ] 0.4.2: Philosophical stance and motivation (link to `critiques/`)
- [ ] 0.4.3: Architecture overview (link to `docs/phase-roadmap.md`)
- [ ] 0.4.4: Quick start — prerequisites, install, first command
- [ ] 0.4.5: Badges — license, Python version, build status (when CI is running)
- [ ] 0.4.6: Ethical use section — link to `RESPONSIBLE_DISCLOSURE.md`, prohibited uses, epistemic caveat

### Task 0.5: Makefile

- [ ] 0.5.1: `make install` — `pip install -e .` for core package
- [ ] 0.5.2: `make lint` — `ruff check .`
- [ ] 0.5.3: `make format` — `ruff format .`
- [ ] 0.5.4: `make typecheck` — `mypy .`
- [ ] 0.5.5: `make test` — `pytest -v --cov=skepsis`
- [ ] 0.5.6: `make clean` — remove `__pycache__`, `.mypy_cache`, `.pytest_cache`, `build/`, `dist/`
- [ ] 0.5.7: `make build` — build Python wheel and source distribution
- [ ] 0.5.8: `make all` — lint, typecheck, test, build in sequence

### Task 0.6: Pre-Commit Hooks

- [ ] 0.6.1: Install `pre-commit` framework
- [ ] 0.6.2: Configure `.pre-commit-config.yaml` — `ruff check`, `ruff format`, `mypy`, trailing whitespace, EOF newline, YAML validator, TOML validator
- [ ] 0.6.3: Run `pre-commit install` to register hooks
- [ ] 0.6.4: Run `pre-commit run --all-files` to verify all hooks pass on existing files
- [ ] 0.6.5: Add `pre-commit autoupdate` to maintenance schedule

### Task 0.7: pyproject.toml Scaffold

- [ ] 0.7.1: Set build system (`hatchling` or `setuptools`)
- [ ] 0.7.2: Core package metadata — name (`skepsis-core`), version (`0.1.0`), description, authors, license (Apache 2.0), Python version constraint (`>=3.12`)
- [ ] 0.7.3: Declare `[project.optional-dependencies]` groups: `dev` (ruff, mypy, pytest, pytest-cov, pre-commit), `jupyter` (notebook, jupyterlab, ipywidgets), `docs` (mkdocs, mkdocstrings), `all` (union of all groups)
- [ ] 0.7.4: Configure `[tool.ruff]` — line length (100), target Python version, selected rulesets (E, F, I, N, W, UP, B, SIM, ARG, RET, PT, ANN)
- [ ] 0.7.5: Configure `[tool.mypy]` — strict mode, Python version, `--ignore-missing-imports` for optional deps
- [ ] 0.7.6: Configure `[tool.pytest.ini_options]` — test paths, coverage config, markers (`slow`, `integration`, `network`, `gpu`)
- [ ] 0.7.7: Add `[tool.coverage.run]` — source paths, branch coverage, exclude lines
- [ ] 0.7.8: Add `[project.urls]` — Homepage, Repository, Documentation, Issues

### Task 0.8: Cargo.toml Workspace Scaffold

- [ ] 0.8.1: Create `Cargo.toml` at root with `[workspace]`
- [ ] 0.8.2: Declare workspace members: `skepsis-sandbox-core` (placeholder)
- [ ] 0.8.3: Set `edition = "2024"`, `resolver = "2"`
- [ ] 0.8.4: Create `skepsis-sandbox-core/Cargo.toml` with PyO3 dependency (deferred, but declared)
- [ ] 0.8.5: Create `skepsis-sandbox-core/src/lib.rs` with stub function

### Task 0.9: CITATION.cff

- [ ] 0.9.1: Create `CITATION.cff` with `cff-version: 1.2.0`
- [ ] 0.9.2: Define authors (project maintainers)
- [ ] 0.9.3: Set `preferred-citation` with DOI placeholder
- [ ] 0.9.4: Define repository-artifact, date-released, version
- [ ] 0.9.5: Validate against schema (if `cffconvert` is available)

### Task 0.10: codemeta.json

- [ ] 0.10.1: Create `codemeta.json` with CodeMeta standard fields
- [ ] 0.10.2: Define author ORCIDs (when available), funding, development status
- [ ] 0.10.3: Link to associated publication placeholder

### Task 0.11: GitHub Templates

- [ ] 0.11.1: `.github/ISSUE_TEMPLATE/bug_report.md` — environment details, reproduction steps, expected vs. actual, scientific context
- [ ] 0.11.2: `.github/ISSUE_TEMPLATE/feature_request.md` — use case, proposed solution, alternatives considered
- [ ] 0.11.3: `.github/ISSUE_TEMPLATE/ethics_concern.md` — description of concern, affected domain (DURC, privacy, indigenous data, bias), suggested mitigation
- [ ] 0.11.4: `.github/ISSUE_TEMPLATE/rfc.md` — motivation, design proposal, tradeoffs, open questions
- [ ] 0.11.5: `.github/PULL_REQUEST_TEMPLATE.md` — description, related issue, testing done, checklist (lint, typecheck, test, documentation updated)
- [ ] 0.11.6: `.github/CONTRIBUTING.md` — code of conduct, development setup, coding standards, PR workflow, ethical contribution guidelines, licensing
- [ ] 0.11.7: `.github/CODEOWNERS` — define ownership for `critiques/`, `docs/`, `skepsis-core/`

### Task 0.12: Repository Verification

- [ ] 0.12.1: `git status` — verify no untracked secrets or artifacts
- [ ] 0.12.2: `make lint` — passes on all files
- [ ] 0.12.3: `make format` — produces no changes
- [ ] 0.12.4: `make typecheck` — passes (or known exceptions documented)
- [ ] 0.12.5: `make test` — at minimum runs and discovers zero tests without error

---

**Phase 0 Exit Criteria**: Repository is cloned fresh and `make all` passes on a clean checkout.

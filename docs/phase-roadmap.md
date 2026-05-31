# Project Skepsis — Comprehensive Phase Roadmap

> **Target**: Y Combinator S2027 (apply mid-Feb 2027)
> **License**: Apache 2.0 (core OSS) + Proprietary (enterprise features)
> **Current date**: May 2026
> **Build window**: ~8 months to YC application

Each phase has its own detailed task breakdown in `docs/phases/`.
See [dependency graph](#dependency-graph) below for sequencing.

---

## High-Level Phase Map

| Phase | Name | Duration | Dependencies | Critical Path | File |
|-------|------|----------|--------------|---------------|------|
| 0 | Repo & Agent Infrastructure | 2 weeks | None | Yes | [`phases/00_repo.md`](phases/00_repo.md) |
| 0.5 | User Research | 2 weeks | Phase 0 | Yes (gate) | [`phases/00_5_user_research.md`](phases/00_5_user_research.md) |
| 1 | Core Python Package | 3 weeks | Phase 0, 0.5 | Yes | [`phases/01_core_package.md`](phases/01_core_package.md) |
| 2 | Model Provider Interface | 3 weeks | Phase 1 | Yes | [`phases/02_model_provider.md`](phases/02_model_provider.md) |
| 3 | Epistemic Safety & Ethics Layer | 2 weeks | Phase 1, 2 | Yes | [`phases/03_ethics_layer.md`](phases/03_ethics_layer.md) |
| 4 | Scientific Literature Engine | 4 weeks | Phase 1, 2 | Yes | [`phases/04_literature_engine.md`](phases/04_literature_engine.md) |
| 5 | Retrieval-Augmented Generation | 4 weeks | Phase 4 | Yes | [`phases/05_rag.md`](phases/05_rag.md) |
| 6 | Multi-Agent Research Framework (4-agent MVP) | 5 weeks | Phase 5 | Yes | [`phases/06_multi_agent.md`](phases/06_multi_agent.md) |
| 7 | Hypothesis Generation & Experimental Design | 4 weeks | Phase 5, 6 | Yes | [`phases/07_hypothesis_generation.md`](phases/07_hypothesis_generation.md) |
| 8 | CLI Application | 3 weeks | Phase 6, 7 | Yes | [`phases/08_cli.md`](phases/08_cli.md) |
| 9 | Rust Sandbox (Design only → Deferred) | 2 weeks | Phase 1 | No | [`phases/09_sandbox.md`](phases/09_sandbox.md) |
| 10 | Jupyter Lab Extension | 3 weeks | Phase 4, 5, 8 | Yes | [`phases/10_jupyter.md`](phases/10_jupyter.md) |
| 11 | Local Web UI | Post-YC | Phase 8, 10 | No | [`phases/11_local_web_ui.md`](phases/11_local_web_ui.md) |
| 12 | API Server & Team Collaboration | Post-YC | Phase 8, 10 | No | [`phases/12_api_server.md`](phases/12_api_server.md) |
| 13 | Academic Pilot Program | 12 weeks | Phase 8, 10 | Yes (parallel) | [`phases/13_academic_pilot.md`](phases/13_academic_pilot.md) |
| 14 | Distribution & DevOps Maturity | Ongoing | Phase 0 | No | [`phases/14_distribution.md`](phases/14_distribution.md) |
| 15 | Open Source Community Launch | Post-pilot | Phase 13, 14 | No | [`phases/15_community_launch.md`](phases/15_community_launch.md) |
| 16 | Monetization Launch | Post-YC | Phase 12, 15 | No | [`phases/16_monetization.md`](phases/16_monetization.md) |
| 17 | YC Application & Fundraising | Feb 2027 | Phase 13 | Yes | [`phases/17_yc_application.md`](phases/17_yc_application.md) |
| 18 | Post-YC Scale | Contingent | Phase 17 | No | [`phases/18_post_yc_scale.md`](phases/18_post_yc_scale.md) |

---

## Dependency Graph

```
Phase 0 (Repo)
    │
    ▼
Phase 0.5 (Desk Research)
    │
    ▼
Phase 1 (Core + Provenance) ────────────────── Phase 9 (Sandbox Design)
    │                                                     (parallel, deferred)
    ▼
Phase 2 (Model Provider) ──── Phase 3 (Ethics)
    │                              │
    ▼                              │
Phase 4 (Literature) ◄─────────────┘
    │
    ▼
Phase 5 (RAG)
    │
    ▼
Phase 6 (Agents)
    │
    ▼
Phase 7 (Hypothesis)
    │
    ▼
Phase 8 (CLI) ───────────── Phase 10 (Jupyter) ──── Phase 13 (Pilot)
    │                              │                      │
    ▼                              ▼                      ▼
Phase 12 (API Server) ── Phase 11 (Web UI)      Phase 17 (YC App)
    (deferred)              (deferred)
```

---

## Cross-Cutting Concerns

See [`phases/00_cross_cutting.md`](phases/00_cross_cutting.md) for:
- R / Julia / MATLAB bridges (Track C)
- Provenance pervasiveness requirements
- Ethical checkpoint requirements
- Testing requirements
- Documentation requirements

---

## Table of Phases with Status

| # | Phase | Priority | Timeline | Deps | Status |
|---|-------|----------|----------|------|--------|
| 0 | Repo & Agent Infrastructure | Critical | Jun 2026 | None | **Complete** |
| 0.5 | User Research | Critical (gate) | Jun 2026 | Phase 0 | **Complete** |
| 1 | Core Python Package | Critical | Jul 2026 | Phases 0, 0.5 | Pending |
| 2 | Model Provider Interface | Critical | Jul 2026 | Phase 1 | Pending |
| 3 | Epistemic Safety & Ethics | Critical | Aug 2026 | Phases 1, 2 | Pending |
| 4 | Scientific Literature Engine | Critical | Aug–Sep 2026 | Phases 1, 2 | Pending |
| 5 | Retrieval-Augmented Generation | Critical | Sep–Oct 2026 | Phase 4 | Pending |
| 6 | Multi-Agent Framework (4-agent MVP) | Critical | Oct–Nov 2026 | Phase 5 | Pending |
| 7 | Hypothesis Generation & Design | Critical | Nov–Dec 2026 | Phases 5, 6 | Pending |
| 8 | CLI Application | Critical | Dec 2026 | Phases 6, 7 | Pending |
| 9 | Rust Sandbox (design only) | Non-critical | Jul 2026 (2wk) | Phase 1 | Design only |
| 10 | Jupyter Lab Extension | Critical | Jan 2027 | Phases 4, 5, 8 | Pending |
| 11 | Local Web UI | Deferred | Post-YC | Phases 8, 10 | Deferred |
| 12 | API Server & Team | Deferred | Post-YC | Phases 8, 10 | Deferred |
| 13 | Academic Pilot Program | Critical | Jan–Mar 2027 | Phases 8, 10 | Pending |
| 14 | Distribution & DevOps | Incremental | Throughout | Phase 0 | Incremental |
| 15 | Open Source Community | Post-pilot | Mar 2027+ | Phases 13, 14 | Deferred |
| 16 | Monetization Launch | Deferred | Post-YC | Phase 12 | Deferred |
| 17 | YC Application & Fundraising | Critical | Feb 2027 | Phase 13 | Pending |
| 18 | Post-YC Scale | Contingent | Post-YC | Phase 17 | Contingent |

# openSciRe — Comprehensive Phase Roadmap

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
| 1 | Core Python Package + Philosophy Foundation | 3 weeks | Phase 0, 0.5 | Yes | [`phases/01_core_package.md`](phases/01_core_package.md) |
| 2 | Model Provider Interface | 3 weeks | Phase 1 | Yes | [`phases/02_model_provider.md`](phases/02_model_provider.md) |
| 3 | Epistemic Safety & Ethics Layer + Confabulation Detection | 2 weeks | Phase 1, 2 | Yes | [`phases/03_ethics_layer.md`](phases/03_ethics_layer.md) |
| 4 | Scientific Literature Engine + Bio Database Bridges | **6 weeks** | Phase 1, 2 | Yes | [`phases/04_literature_engine.md`](phases/04_literature_engine.md) |
| 5 | Retrieval-Augmented Generation + Pedagogical Report | 4 weeks | Phase 4 | Yes | [`phases/05_rag.md`](phases/05_rag.md) |
| 6 | Multi-Agent Research Framework (4-agent MVP) + Diversity Guarantee | 5 weeks | Phase 5 | Yes | [`phases/06_multi_agent.md`](phases/06_multi_agent.md) |
| 7 | Hypothesis Generation & Experimental Design + ProblemFormulationAdvisor | 4 weeks | Phase 5, 6 | Yes | [`phases/07_hypothesis_generation.md`](phases/07_hypothesis_generation.md) |
| 8 | CLI Application | 3 weeks | Phase 6, 7 | Yes | [`phases/08_cli.md`](phases/08_cli.md) |
| 9 | Rust Sandbox **(Working MVP)** | **3 weeks** | Phase 1 | No | [`phases/09_sandbox.md`](phases/09_sandbox.md) |
| 10 | Jupyter Lab Extension | 3 weeks | Phase 4, 5, 8 | Yes | [`phases/10_jupyter.md`](phases/10_jupyter.md) |
| 11 | Local Web UI | Post-YC | Phase 8, 10 | No | [`phases/11_local_web_ui.md`](phases/11_local_web_ui.md) |
| 12 | API Server & Team Collaboration | Post-YC | Phase 8, 10 | No | [`phases/12_api_server.md`](phases/12_api_server.md) |
| 13 | Academic Pilot Program | 12 weeks | Phase 8, 10 | Yes (parallel) | [`phases/13_academic_pilot.md`](phases/13_academic_pilot.md) |
| 14 | Distribution & DevOps Maturity | Ongoing | Phase 0 | No | [`phases/14_distribution.md`](phases/14_distribution.md) |
| 15 | Open Source Community Launch | Post-pilot | Phase 13, 14 | No | [`phases/15_community_launch.md`](phases/15_community_launch.md) |
| 16 | Monetization Launch | Post-YC | Phase 12, 15 | No | [`phases/16_monetization.md`](phases/16_monetization.md) |
| 17 | YC Application & Fundraising | Feb 2027 | Phase 13 | Yes | [`phases/17_yc_application.md`](phases/17_yc_application.md) |
| 18 | Post-YC Scale | Contingent | Phase 17 | No | [`phases/18_post_yc_scale.md`](phases/18_post_yc_scale.md) |

> **Note on Phase 4 and bio bridges**: Phase 4 now includes bio database bridges (UniProt, PDB, NCBI, AlphaFold DB, InterPro) via shared BridgeAdapter infrastructure (4.14–4.20). These bridges feed into Phase 5 (RAG) and Phase 7 (hypothesis generation grounds in structural data). Extended from 4 to 6 weeks to accommodate the additional scope.
>
> **Note on Phase 9**: Upgraded from "design only → deferred" to a working Rust sandbox MVP with seccomp, tmpfs, cgroups, and PyO3 bridge. Runs in parallel with Phase 1. Post-pilot features (multi-criteria evaluation, carbon tracking, DURC for code) deferred.

---

## Dependency Graph

```
Phase 0 (Repo)
    │
    ▼
Phase 0.5 (Desk Research)
    │
    ▼
Phase 1 (Core + Provenance + Philosophy) ─── Phase 9 (Rust Sandbox MVP)
    │                                              (parallel, working impl)
    ▼
Phase 2 (Model Provider) ──── Phase 3 (Ethics + Confabulation)
    │                              │
    ▼                              │
Phase 4 (Literature + Bio Bridges) ◄┘
    │
    ▼
Phase 5 (RAG + Pedagogical Report)
    │
    ▼
Phase 6 (Agents + Diversity Guarantee)
    │
    ▼
Phase 7 (Hypothesis + ProblemFormulation)
    │
    ▼
Phase 8 (CLI) ───────────── Phase 10 (Jupyter) ──── Phase 13 (Pilot)
    │                              │                      │
    ▼                              ▼                      ▼
Phase 12 (API Server) ── Phase 11 (Web UI)      Phase 17 (YC App)
    (deferred)              (deferred)
```

> **Sandbox integration path**: Phase 9 sandbox core MVP is independent and builds in parallel with Phase 1. Full integration with the agent framework and ethics layer happens post-MVP (Q1 2027), enabling sandboxed execution of LLM-generated code through the multi-agent workflow.

---

## Cross-Cutting Concerns

See [`phases/00_cross_cutting.md`](phases/00_cross_cutting.md) for:
- Provenance pervasiveness requirements
- Ethical checkpoint requirements
- Testing requirements
- Documentation requirements
- Openscire-philosophy epistemic principles applied across all phases

---

## Table of Phases with Status

| # | Phase | Priority | Timeline | Deps | Status |
|---|-------|----------|----------|------|--------|
| 0 | Repo & Agent Infrastructure | Critical | Jun 2026 | None | **Complete** |
| 0.5 | User Research | Critical (gate) | Jun 2026 | Phase 0 | **Complete** |
| 1 | Core Python Package + Philosophy Foundation | Critical | Jul 2026 | Phases 0, 0.5 | Pending |
| 2 | Model Provider Interface | Critical | Jul 2026 | Phase 1 | Pending |
| 3 | Epistemic Safety & Ethics + Confabulation | Critical | Aug 2026 | Phases 1, 2 | Pending |
| 4 | Scientific Literature Engine + Bio Bridges | Critical | Aug–Oct 2026 | Phases 1, 2 | Pending |
| 5 | RAG + Pedagogical Report | Critical | Oct–Nov 2026 | Phase 4 | Pending |
| 6 | Multi-Agent Framework + Diversity Guarantee | Critical | Nov–Dec 2026 | Phase 5 | Pending |
| 7 | Hypothesis Generation + ProblemFormulation | Critical | Dec 2026–Jan 2027 | Phases 5, 6 | Pending |
| 8 | CLI Application | Critical | Jan 2027 | Phases 6, 7 | Pending |
| 9 | Rust Sandbox (Working MVP) | Non-critical | Jul 2026 (3wk) | Phase 1 | MVP |
| 10 | Jupyter Lab Extension | Critical | Jan–Feb 2027 | Phases 4, 5, 8 | Pending |
| 11 | Local Web UI | Deferred | Post-YC | Phases 8, 10 | Deferred |
| 12 | API Server & Team | Deferred | Post-YC | Phases 8, 10 | Deferred |
| 13 | Academic Pilot Program | Critical | Jan–Mar 2027 | Phases 8, 10 | Pending |
| 14 | Distribution & DevOps | Incremental | Throughout | Phase 0 | Incremental |
| 15 | Open Source Community | Post-pilot | Mar 2027+ | Phases 13, 14 | Deferred |
| 16 | Monetization Launch | Deferred | Post-YC | Phase 12 | Deferred |
| 17 | YC Application & Fundraising | Critical | Feb 2027 | Phase 13 | Pending |
| 18 | Post-YC Scale | Contingent | Post-YC | Phase 17 | Contingent |

> **Status notes**:
> - Phase 9: Now a working MVP (not design-only). Core sandbox (seccomp, tmpfs, cgroups, PyO3) builds in parallel with Phase 1. Post-pilot integration features deferred.
> - Phase 4: Extended to 6 weeks to accommodate bio database bridges and shared BridgeAdapter infrastructure.
> - Phases 7–8: Timeline shifted slightly later to absorb the new ProblemFormulationAdvisor in Phase 7 and accommodate the 6-week Phase 4.

# Project Skepsis — Risk Register

> **Status**: Phase 0 — initial
> **Last reviewed**: May 2026
> **Review cadence**: Monthly or when a phase gate is crossed

---

## How to Use This Document

Each risk is assigned a unique ID (R-001, R-002, ...) and tracked through its lifecycle. Risks are reviewed during phase transitions. When a risk materializes, it becomes an _issue_ and is moved to the Issues section with a remediation plan.

---

## Risk Table

| ID | Risk | Likelihood | Impact | Category | Mitigation | Monitor | Status |
|----|------|-----------|--------|----------|-----------|---------|--------|
| R-001 | Desk research (Phase 0.5) shows no demand for local-first scientific AI | Medium | Critical | Market | Pivot before writing production code. Phase 0.5 is a hard go/no-go gate. | Desk research results after competitor/forum analysis | Open |
| R-002 | LLM-dependent tests are flaky or non-deterministic | High | Medium | Technical | Build MockModelProvider in Phase 2 that replays recorded cassettes. Unit tests never call real APIs. | CI failure rate | Open |
| R-003 | API providers (OpenAI, Anthropic, Google) change or deprecate endpoints | Medium | High | Technical | Adapter pattern + MCP + fallback cascade (Ollama → smaller local → BYOK remote). No hardcoded API shapes. | Provider changelogs, CI integration tests | Open |
| R-004 | Pilot labs ghost or produce no usable data | Medium | High | Execution | Recruit 5 labs for 3 spots. Lightweight onboarding (<2h). Monthly check-ins. Pre-written case study template. | Pilot recruitment pipeline, weekly check-ins during Phase 13 | Open |
| R-005 | Y Combinator rejects S2027 application | High | Medium | Funding | Plan B: NSF SBIR (Phase I: $256K), angel investors (Lux Capital, a16z bio, OS Fund, LocalGlobe). SBIR drafts prepared before YC decision. | YC application quality, SBIR deadline calendar | Open |
| R-006 | Prohibited dependency license conflicts with Apache 2.0 | Low | High | Legal | Automated `pip-licenses` check in CI. License review before adding any new dependency. GPL/AGPL dependencies forbidden in core OSS packages. | CI pipeline, dependency review in PR template | Open |
| R-007 | Solo developer burnout or bus factor | High | Critical | People | Scope aggressively. Defer Tauri desktop, API server, and full Rust sandbox to post-YC. Dogfood the roadmap timeline. | Velocity vs timeline tracking | Open |
| R-008 | Critiques and user research findings conflict | Low | Medium | Design | Critiques are the philosophical worldview; user research is empirical signal. When they conflict, document the tension and make an explicit design decision. Document tradeoffs. | Phase 0.5 synthesis document, Phase 1 design decisions | Open |
| R-009 | Phase 6 (agent orchestration) is architecturally harder than estimated | Medium | High | Technical | Start with 4-agent MVP, not all 8. Structured message protocol (Pydantic), not free-text. Fail fast on integration complexity. | Phase 6 progress against 5-week budget | Open |
| R-010 | Academic institutions block local-first tools due to IT policy | Medium | Medium | Market | BYOK + managed cloud option. Self-hosted Docker Compose deployment for institutional firewalls. Pilot in institutions with flexible IT. | Pilot lab IT onboarding friction | Open |
| R-011 | NIH/NSF grant cycles are too slow for YC timeline | Medium | Medium | Funding | SBIR/STTR as Plan B, not primary funding. YC application depends on pilot traction, not grant funding. | Grant submission deadlines | Open |
| R-012 | Literature API rate limits block indexing at scale | Medium | Low | Technical | Local embedding index reduces API dependency after initial fetch. Cache aggressively. Queue-based rate limiting. | API usage metrics during Phase 4 | Open |
| R-013 | Ethical Firewall generates too many false positives | Medium | Medium | Product | Tunable sensitivity. Tier 1 (hard block) vs Tier 2 (soft flag with user override). Collect FP data during Phase 13 pilots. | False positive rate during Phase 6/7 testing | Open |
| R-014 | Non-English corpus integration is legally ambiguous (CNKI, eLibrary) | Low | Medium | Legal | Start with metadata-only indexing for restricted corpora. Full-text only where license permits. Legal review before expanding. | Legal review scheduled before Phase 4 | Open |

---

## Risk Categories

| Category | Count | Notes |
|----------|-------|-------|
| Market | 3 | R-001, R-010, R-014 |
| Technical | 4 | R-002, R-003, R-009, R-012 |
| Execution | 1 | R-004 |
| Funding | 2 | R-005, R-011 |
| Legal | 1 | R-006 |
| People | 1 | R-007 |
| Design | 1 | R-008 |
| Product | 1 | R-013 |

---

## Open Issues (Materialized Risks)

None yet. This section populated when a risk becomes an active issue.

---

## Review Log

| Date | Reviewed By | Notes |
|------|-------------|-------|
| May 2026 | Initial | Created during Phase 0 repo infrastructure setup |

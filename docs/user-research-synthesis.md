# User Research Synthesis & Go/No-Go Decision

> **Status**: Phase 0.5 — desk research, exit artifact
> **Date**: May 2026
> **Method**: Synthesis of competitor teardown, pain point heatmap, and published surveys review

---

## I. Executive Summary

Desk research across **3 artifacts** (competitor teardown of 7 tools, pain point heatmap of 12 pain points from ~30 sources, published surveys review of 9 surveys totalling ~14,000+ respondents) yields a clear verdict: **the openSciRe value proposition is validated, the market gap is real, and Phase 1 should proceed.**

No existing tool offers local-first inference, cryptographic provenance, or a falsification-oriented epistemic framework. Researchers across target segments (biomedical, life sciences R&D, clinical) report acute pain from hallucination (16% fabrication rate), tool fragmentation (2–4 tools needed), and trust deficits (94% concerned about AI misinformation). The window for a credible local-first alternative is open.

---

## II. Evidence Synthesis

### A. Competitor Landscape

| Finding | Source |
|---------|--------|
| Local-first / offline: **wide open** — zero competitors offer it | Competitor teardown |
| Cryptographic provenance: **wide open** — no tool has this | Competitor teardown |
| Falsification framework: **partially addressed** — ContraCrow detects contradictions but is not an epistemic framework | Competitor teardown |
| Closest competitor (PaperQA2) is open-source but cloud-dependent at inference time | Competitor teardown |
| Google Co-Scientist: the philosophical antagonist — cloud-locked, no provenance, no falsification | Competitor teardown |

### B. Pain Point Validation

| # | Pain Point | Frequency × Intensity | Confirmed? |
|---|-----------|----------------------|------------|
| 1 | Literature review takes too long | 25/25 | ✅ |
| 2 | AI hallucination / citation fabrication | 25/25 | ✅ |
| 3 | Tool fragmentation | 16/25 | ✅ |
| 4 | AI misses minority subdomains | 16/25 | ✅ |
| 5 | Paywalled content restricts AI tools | 16/25 | ✅ |
| 6 | No local-first option | 20/25 | ✅ |
| 7 | No provenance / audit trail | 16/25 | ✅ |

**6 of 7 roadmap assumptions confirmed.** The weakest link ("researchers want a single tool") is nuanced — power users prefer stacks — but fragmentation itself is acutely painful.

### C. Quantitative Baselines from Published Surveys

| Metric | Value | Source |
|--------|-------|--------|
| AI adoption rate (researchers, 2025) | **84%** (up from 57% in 2024) | Wiley ExplanAItions |
| Researchers using AI in life science labs | **68%** (2024), up from 54% in 2023 | Pistoia Alliance |
| Verified authors who've used LLMs in workflow | **81%** | arXiv (Biderman et al.) |
| Researchers using **general-purpose tools** (ChatGPT) | **80%** | Wiley 2025 |
| Researchers using **specialized research AI tools** | **25%** | Wiley 2025 |
| Who say domain-specific tools would be "very helpful" | **56%** | Ithaka S+R / CZI |
| Who don't know what data their AI models use | **27%** | Pistoia 2025 |
| Who cite lack of verification standards as barrier | **50%** | Pistoia 2025 |
| Concerned AI will erode critical thinking | **81%** | Elsevier 2024 |
| Concerned AI will cause critical errors | **86%** | Elsevier 2024 |
| Prefer **open-source/non-profit** LLMs (among those with a preference) | **59%** | arXiv (Biderman et al.) |

---

## III. Decision Criteria Evaluation

| Criterion | Evidence | Verdict |
|-----------|----------|---------|
| **Active demand across 2+ target segments** | Literature review pain (25/25) affects all segments. Hallucination concern (25/25) concentrated in biomedical. 56% want domain-specific tools. 84% adoption but surging skepticism — market is primed for better alternatives. | ✅ **PASS** (3 segments: biomed, life sciences R&D, clinical research) |
| **No competitor fully addresses the openSciRe value proposition** | Competitor teardown: local-first = wide open. Provenance = wide open. Falsification = partial only. PaperQA2 is closest but cloud-dependent at inference time. | ✅ **PASS** (3 of 4 value props uncontested) |
| **Desk research confirms at least 3 of 5 assumed pain points** | Pain point heatmap confirms all 5 top pain points: (1) lit review time, (2) hallucination, (3) fragmentation, (6) no local-first, (7) no provenance. | ✅ **PASS** (5 of 5 confirmed) |

---

## IV. Decision: GO → Phase 1

All three decision criteria are met. The project proceeds to **Phase 1: Core Python Package**.

### Phase 1 Prioritization Recommendations

Based on desk research findings, Phase 1 should prioritize in this order:

1. **Provenance system** — cryptographic output signing + audit trail (addressed gap #7, required by Pistoia's 50% demanding verification standards)
2. **Model provider abstraction** (BYOK / local-first path) — addresses local-first gap #6, enables 59% who prefer open-source/non-profit
3. **Ethical firewall** (falsification over plausibility) — addresses hallucination gap #2, directly counters 94% misinformation concern
4. **Literature engine** (retrieval) — addresses lit-review-time gap #1, but note that AI search tools currently miss 91% of relevant studies — openSciRe must beat this baseline
5. **Simple CLI** for testing the stack end-to-end

### Key Numbers to Beat

| Baseline | Metric | Target |
|----------|--------|--------|
| 91% | Studies missed by AI search tools | <50% (Phase 1), <20% (Phase 4) |
| 16% | Fabricated references in ChatGPT output | <1% (provenance-verified) |
| 0 | Competitors with local inference | At least 1 (us) |
| 27% | Researchers who don't know their AI's data provenance | 0% for openSciRe outputs |

---

## V. What Was Deferred (and Why)

| Research type | Deferred to | Reason |
|---------------|-------------|--------|
| Structured survey (N 20+) | Phase 15 — Community Launch | Not credible until we have real users |
| Email interviews (4–6) | Phase 15 — Community Launch | Need warm leads from survey |
| Price sensitivity (Van Westendorp) | Phase 16 — Monetization | Need real product context |

These do not block Phase 1. The desk research provides sufficient directional evidence for go/no-go and initial design decisions.

---

## VI. References

- Competitor teardown: `docs/competitor-teardown.md`
- Pain point heatmap: `docs/pain-point-heatmap.md`
- Published surveys review: `docs/published-surveys-review.md`
- Phase 0.5 task breakdown: `docs/phases/00_5_user_research.md`
- Threat model: `docs/threat-model.md`

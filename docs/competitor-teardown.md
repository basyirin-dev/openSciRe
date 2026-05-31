# Competitor Teardown

> **Status**: Phase 0.5 — desk research
> **Last updated**: May 2026
> **Method**: Public product documentation, reviews, academic papers, community analysis

---

## Evaluation Framework

Each tool scored against Skepsis's four core value propositions:

| Criterion | Meaning |
|-----------|---------|
| **Local-first** | Runs fully offline; no mandatory cloud dependency |
| **Provenance** | Cryptographically signed, auditable output trail |
| **Falsification** | Designed to test claims, not just generate plausible text |
| **BYOK / Model-agnostic** | Bring your own API key; swappable backends |

---

## Competitor Table

| Tool | Strength | Key Gap | Skepsis Angle |
|------|----------|---------|---------------|
| **Perplexity for Science** | Fast synthesis with citations; 45M+ users; Deep Research mode runs agentic search loops; Spaces for organization; Research mode does 100+ searches per query | **Cloud-only** — no local model option. No provenance tracking. No falsification orientation. Model-locked (Claude Opus only for Deep Research). Cannot BYOK. | Full local-first alternative with verifiable provenance. |
| **Elicit** | Best-in-class systematic review workflow; 138M papers indexed; PRISMA 2020 compliant; 99.4% extraction accuracy; Zotero integration | **Cloud-only**. No provenance. Academic paper-centric — no web or multi-modal search. No BYOK. $49/mo Pro is expensive. | Local-first with provenance fills the gap for labs that can't upload sensitive research to cloud. |
| **Scite** | 1.6B+ Smart Citations (supporting/contrasting/mentioning); 280M+ full-text articles incl. paywalled; MCP integration with ChatGPT/Claude | **Cloud-only**. Citation intelligence only — no hypothesis generation, no falsification, no provenance. | Provenance layer would integrate with Scite's citation data rather than replace it. |
| **Research Rabbit** | Visual citation mapping; free; Zotero sync; 270M papers; excellent for discovery | **Cloud-only**. No synthesis or Q&A — discovery only. No provenance, no falsification, no BYOK. | Complementary — Skepsis could ingest Research Rabbit collections via Zotero bridge. |
| **PaperQA2/3** | Open-source; agentic RAG; LitQA2 benchmark leader; LiteLLM for model flexibility; contradiction detection (ContraCrow); multi-modal (figures/tables) | **Requires cloud LLM APIs** (defaults to OpenAI). No built-in provenance. No falsification framework. CLI-only, no desktop UI. | Closest existing tool to Skepsis's vision. Skepsis differentiator: provenance layer + falsification framework + local inference as first-class citizen. |
| **Undermind** | 10-50x more precise than Google Scholar; citation chain following; adaptive successive search; 98% precision; MIT PhD founders | **Cloud-only**. No provenance, no falsification, no BYOK. Limited to academic literature. Free tier is very restrictive (3-5 searches/mo). | Strong search precision is table stakes — Skepsis adds falsification and provenance on top. |
| **Google Co-Scientist** | Multi-agent hypothesis generation (Generation, Reflection, Ranking, Evolution, Proximity, Meta-review agents); tournament-of-ideas; integrated with Gemini; Nature publication; validated in wet-lab | **Cloud-only, Google Cloud locked**. No BYOK. No local option. No provenance for individual claims. Designed for Google-scale compute. Cloud trust is eroding among research institutions. | The direct philosophical antagonist. Skepsis offers the same hypothesis generation capability but local-first, with provenance, and without vendor lock-in. |

---

## Gap Summary

| Value Prop | Uncontested? | Competition |
|------------|-------------|-------------|
| **Local-first / offline** | ✅ **Wide open** | No tool offers this. All require cloud. |
| **Provenance (cryptographic)** | ✅ **Wide open** | No tool offers signed, auditable output trails. |
| **Falsification-oriented** | ⚠️ **Partial** | ContraCrow (PaperQA2) detects contradictions but isn't a falsification framework. Co-Scientist has self-critique but no epistemic safety guarantees. |
| **BYOK / Model-agnostic** | ⚠️ **Partial** | PaperQA2 supports LiteLLM (any provider) but defaults to OpenAI and requires cloud. No tool supports local inference (Ollama/vLLM) as a first-class path. |

## Verdict

**The market gap is confirmed.** Three of four Skepsis value propositions (local-first, provenance, falsification) are uncontested or only partially addressed. The closest competitor (PaperQA2) is open-source but cloud-dependent at inference time — Skepsis's local-first stance is a genuine differentiator, not a nice-to-have.

# Published Surveys Review

> **Status**: Phase 0.5 — desk research, sub-task 0.5.1.3
> **Last updated**: May 2026
> **Scope**: Reviewed 9 major surveys (2023–2026) covering ~14,000+ respondents across biomedical, life sciences, and general research.

---

## Survey Index

| # | Survey | Source | n | Population | Date |
|---|--------|--------|---|------------|------|
| 1 | Nature AI & Science Survey | Nature | 1,659 | Global researchers (40k sampled) | Sep 2023 |
| 2 | Wellcome: AI in Drug Discovery | Wellcome Trust | N/A (report) | Drug discovery ecosystem | Jun 2023 |
| 3 | Insights 2024: Attitudes Toward AI | Elsevier / Wellcome | 2,999 | Researchers & clinicians (123 countries) | Dec 2023–Feb 2024 |
| 4 | Ithaka S+R: GenAI in Biomedical Research | Ithaka S+R / CZI | 770 | Academic biomedical researchers | Feb–Mar 2024 |
| 5 | LLMs as Research Tools (large-scale) | arXiv (Biderman et al.) | 816 | Verified published article authors | Nov 2023–Apr 2024 |
| 6 | PLOS ONE: AI in Medical Journals | PLOS ONE | 236 | Corresponding authors (top 15 med journals) | Jul–Sep 2023 |
| 7 | Pistoia Alliance Lab of the Future (2024) | Pistoia Alliance | 200 | Life science R&D experts | May–Aug 2024 |
| 8 | Pistoia Alliance Lab of the Future (2025) | Pistoia Alliance | 206 | Life science R&D experts | May–Aug 2025 |
| 9 | Wiley ExplanAItions (2025) | Wiley | 2,430 | Global researchers | Aug 2025 |

**Plus**: 4 systematic reviews/meta-research studies on AI in evidence synthesis (AHRQ 2025, Cambridge 2025, BMJ Open 2025, BMC 2026).

---

## Key Findings by Theme

### 1. Adoption Is Surging — But Fragile

| Stat | Source |
|------|--------|
| 57% → 84% researcher AI adoption (2024→2025) | Wiley ExplanAItions 2025 |
| 68% using AI/ML in life science labs (2024, up from 54% in 2023) | Pistoia 2024 |
| 81% of verified research authors have used LLMs in workflow | arXiv (Biderman et al.) |
| 77% expect to use AI in next 2 years | Pistoia 2025 |
| 67% of non-users expect to start within 2–5 years | Elsevier 2024 |

**However**: Expectations are undergoing a "reality check." The Wiley study found researchers are significantly scaling back their beliefs about AI outperforming humans — last year they thought AI already beat humans for >50% of use cases; this year <30%.

### 2. Primary Barriers to Adoption

| Barrier | Prevalence | Source |
|---------|-----------|--------|
| Concern over accuracy / output quality | #1 barrier (biomedical) | Ithaka S+R 2024 |
| Lack of guidelines and training | 57% | Wiley 2025 |
| Low quality / poorly curated datasets | 52% | Pistoia 2024 |
| Privacy and security concerns | 41% (up from 34% in 2023) | Pistoia 2024 |
| Lack of skilled people | 34% (up from 23% in 2024) | Pistoia 2025 |
| Data not FAIR (findable, accessible, interoperable, reusable) | 34% (up from 23% in 2024) | Pistoia 2024 |

**Key insight for Skepsis**: Pistoia 2025 found that **27% of life science professionals don't know what data their AI models use**, and **50% cite lack of shared verification standards as the biggest barrier to AI agent adoption**. This directly validates the provenance and verification architecture.

### 3. What Researchers Actually Use AI For

| Use Case | Prevalence | Source |
|----------|-----------|--------|
| Editing / proofreading / rephrasing | 31–56% | Ithaka, PLOS ONE |
| Information seeking / literature discovery | ~30% | arXiv (Biderman) |
| Code generation | ~20–30% | Nature 2023 |
| Brainstorming / ideation | ~20% | Nature 2023 |
| Data processing / analysis | 66% see benefit | Nature 2023 |
| Automated manuscript writing | 5% | Ithaka 2024 |

**Critical finding**: **80% of researchers use general-purpose tools (ChatGPT)** vs **only 25% use specialized research AI tools** (Wiley 2025). But **56% say biomed-specific tools would be "very helpful"** (Ithaka 2024). The gap between demand for domain-specific tools and actual adoption is enormous — 80% still on ChatGPT.

### 4. Tool Choice Preferences

- **54.8%** of researchers say their perception of an LLM changes depending on its source
- Of those, **59% prefer open-source / non-profit** LLMs over corporate
- **Only 2.85%** stated preference for corporate LLMs
- Source: arXiv (Biderman et al.), n=816

### 5. Trust Factors

What would increase trust in GenAI tools (Elsevier 2024):
- Training model to be factually accurate, moral, not harmful: 58%
- Only using high-quality peer-reviewed content to train: 57%
- Citing references by default (transparency): 56%
- Keeping input confidential: 55%
- Abiding by laws governing development: 53%

What would increase comfort:
- Knowing model uses up-to-date information: 37%
- Robust governance on training data: 36%
- Accountability through human oversight: 36%

### 6. Concerns

| Concern | Prevalence | Source |
|---------|-----------|--------|
| Inaccurate information / misinformation | 68% | Nature 2023 |
| Easier plagiarism (harder to detect) | 68% | Nature 2023 |
| Introducing errors in papers/code | 66% | Nature 2023 |
| Over-reliance on pattern recognition | 69% | Nature 2023 |
| AI will erode critical thinking | 81% | Elsevier 2024 |
| AI will cause critical errors/mishaps | 86% | Elsevier 2024 |
| AI used for misinformation | 94% | Elsevier 2024 |

### 7. Evidence Synthesis Performance (Systematic Review Data)

| Task | AI Performance | Source |
|------|---------------|--------|
| **Searching** — recall | Median 14% (AI) vs human | AHRQ 2025 |
| **Searching** — studies missed | 68%–96% (median 91%) | Cambridge 2025 |
| **Abstract screening** — recall | 85% (zero-shot), 97% (semi-automated, 51% burden reduction) | AHRQ 2025 |
| **Screening** — incorrect inclusion | 0%–29% (median 10%) | Cambridge 2025 |
| **Screening** — incorrect exclusion | 1%–83% (median 28%) | Cambridge 2025 |
| **Data extraction** — accuracy | Median 66% correct | AHRQ 2025 |
| **Data extraction** — errors | 4%–31% (median 14%) | Cambridge 2025 |
| **Risk of bias** — agreement with humans | Cohen's κ = 0.20 (median agreement 71%) | AHRQ 2025 |
| **Risk of bias** — incorrect assessments | 10%–56% (median 27%) | Cambridge 2025 |

**Bottom line**: AI is useful for **screening with human oversight** but **fails catastrophically at searching** (missing 91% of relevant studies on median). The Cambridge 2025 review concludes: "The current evidence does not support GenAI use in evidence synthesis without human involvement."

### 8. Demographic Disparities

- **Non-White, junior, and non-native English speaking researchers** report higher LLM usage and perceived benefits → AI is potentially an equity tool (arXiv)
- **Women, non-binary, and senior researchers** express greater ethical concerns → adoption is not uniform
- **Researchers in APAC** are most optimistic about AI impact; **Europe** least (Elsevier 2024)
- **Authors from high-income countries** publish AI-disclosing reviews in higher-impact journals (BMC 2026)

---

## Implications for Skepsis

| Finding | Skepsis Response |
|---------|-----------------|
| 84% adoption but surge in skepticism/"reality check" | Mature audience ready for honest, non-hype tooling |
| 59% prefer open-source/non-profit LLMs | Local-first, open-source position validated |
| 27% don't know what data their AI uses | Provenance-first architecture is a differentiator |
| 50% cite lack of verification standards for AI agents | Verification as core feature, not afterthought |
| Search tools miss 91% of relevant studies on average | Skepsis must invest in retrieval quality, not just LLM output |
| 56% want domain-specific tools but only 14% use them | Demand exists; distribution/marketing is the barrier |
| 80% using ChatGPT for research | Low bar to beat on accuracy and trust |
| Lack of guidelines/training is #2 barrier | Invest in onboarding and documentation |
| Over-reliance on pattern recognition → deskilling concern (69%) | Build for augmentation, not automation; falsification > plausibility |
| Critical thinking erosion feared by 81% | Epistemic design language validates Skepsis philosophical stance |

---

## Sources

1. Nature 2023 — `doi:10.1038/d41586-023-02988-6` (n=1,659)
2. Wellcome 2023 — `wellcome.org/reports/unlocking-potential-ai-drug-discovery`
3. Elsevier/Wellcome Insights 2024 — `assets.ctfassets.net/.../Insights_2024_-_Attitudes_toward_AI` (n=2,999)
4. Ithaka S+R 2024 — `sr.ithaka.org/publications/adoption-of-generative-ai-by-academic-biomedical-researchers/` (n=770)
5. Biderman et al. 2024 — arXiv:2411.05025 "LLMs as Research Tools" (n=816)
6. PLOS ONE 2024 — `doi:10.1371/journal.pone.0309208` (n=236)
7. Pistoia Alliance 2024 — `pistoiaalliance.org/resource-library/lab-of-the-future-2024-survey/` (n=200)
8. Pistoia Alliance 2025 — `pistoiaalliance.org/resource-library/lab-of-the-future-2025/` (n=206)
9. Wiley ExplanAItions 2025 — `newsroom.wiley.com/press-releases/.../AI-Adoption-Jumps-to-84` (n=2,430)
10. AHRQ 2025 — NCBI Bookshelf NBK620201 (95 studies reviewed)
11. Cambridge 2025 — `doi:10.1017/...` GenAI for Evidence Synthesis SR (19 studies)
12. BMJ Open 2025 — `doi:10.1136/bmjopen-2025-099921` (n=187, DCE)
13. BMC 2026 — `doi:10.1186/s12874-026-02796-2` (188 SRs, meta-research)

# Phase 3 — Epistemic Safety & Ethics Layer

**Duration**: 2 weeks (Aug 2026)
**Dependencies**: Phase 1 (models, provenance), Phase 2 (model access)
**Output**: Ethical firewall, carbon tracking, uncertainty quantification, source grounding

---

### Task 3.1: EthicalFirewall with DURC Detection

- [ ] 3.1.1: `EthicalFirewall` — configurable policy engine with rule set
- [ ] 3.1.2: DURC category definitions (dual-use research of concern) — pathogen enhancement, toxin synthesis, weapons delivery, AI safety evasion, surveillance hardening
- [ ] 3.1.3: LLM-assisted classification — prompt-level and response-level scanning for DURC patterns
- [ ] 3.1.4: Keyword + embedding-based detection (local, no cloud dependency)
- [ ] 3.1.5: Configurable action on detection: flag (log only), warn (user visible), block (prevent execution), escalate (notify admin)
- [ ] 3.1.6: False positive feedback loop — allow users to contest flags; contested flags reviewed and used to tune classifier
- [ ] 3.1.7: Audit log of all firewall decisions (non-removable, append-only provenance entries)

### Task 3.2: Risk Tier Classification (Differential Speed Governance)

- [ ] 3.2.1: Three-tier classification:
  - **Tier 1 (High Risk)**: virology, toxin research, AI safety, weapons, dual-use chemistry, human genetic engineering → mandatory 24-hour cooling-off period, external reviewer gate
  - **Tier 2 (Medium Risk)**: clinical research without IRB clearance, human subjects data, animal research, controlled substances → mandatory human checkpoint (cannot proceed autonomously)
  - **Tier 3 (Low Risk)**: solar forecasting, materials science, ecology observation, mathematics, theoretical physics → standard workflow
- [ ] 3.2.2: Domain auto-classification based on query content and literature context
- [ ] 3.2.3: Manual override mechanism with justification log (can escalate but cannot silently downgrade)
- [ ] 3.2.4: Tier display in CLI/UI — user always knows which tier they are operating in
- [ ] 3.2.5: Tier audit trail in provenance

### Task 3.3: DataSovereigntyChecker

- [ ] 3.3.1: Verify provenance and consent constraints before ingesting data
- [ ] 3.3.2: Data origin classification — public, licensed, IRB-approved, indigenous, clinical, proprietary
- [ ] 3.3.3: Consent metadata parser — check for usage restrictions in data provenance
- [ ] 3.3.4: Restriction enforcement — block analysis of data that violates consent terms
- [ ] 3.3.5: Export restriction marker — flag data that cannot be shared across borders (GDPR, ITAR, HIPAA)

### Task 3.4: IndigenousKnowledgeProtector

- [ ] 3.4.1: Culturally restricted data markers — metadata field indicating cultural or indigenous knowledge restrictions
- [ ] 3.4.2: Block ingestion of marked data into training/generation pipelines
- [ ] 3.4.3: CARE Principles for Indigenous Data Governance integration (Collective Benefit, Authority to Control, Responsibility, Ethics)
- [ ] 3.4.4: Audit trail of all blocked access attempts by indigenous knowledge category

### Task 3.5: CarbonBudgetTracker

- [ ] 3.5.1: Track compute per operation — FLOPs estimation from model size, token count, and hardware profile
- [ ] 3.5.2: Energy conversion — FLOPs → kWh based on hardware efficiency factors
- [ ] 3.5.3: CO2e estimation — kWh → CO2e based on regional grid carbon intensity (user-configurable)
- [ ] 3.5.4: Per-query carbon report — displayed as part of CLI output, logged in provenance
- [ ] 3.5.5: Cumulative carbon budget — user-configurable monthly limit with warning at 80%, hard stop at 100%
- [ ] 3.5.6: Carbon comparison — "This query used X kWh, equivalent to Y km of driving"

### Task 3.6: UncertaintyQuantifier

- [ ] 3.6.1: Confidence scoring for all generated claims — based on source quality, agreement level, model certainty signals
- [ ] 3.6.2: Contradiction detection — when two sources disagree, flag and present both sides with confidence scores
- [ ] 3.6.3: Knowledge boundary flagging — "This question cannot be answered from available literature"
- [ ] 3.6.4: Model uncertainty extraction — parse logprobs, token probabilities, refusal signals
- [ ] 3.6.5: Confidence visualization: confidence bar, source count, contradiction indicators
- [ ] 3.6.6: Mandatory uncertainty disclosure — every generated claim displayed with confidence indicator

### Task 3.7: SourceGrounding

- [ ] 3.7.1: Forced citation enforcement — every factual claim in output must cite at least one source
- [ ] 3.7.2: Source extraction from model responses — parse citations from generated text
- [ ] 3.7.3: Source verification — check that cited sources exist in retrieved literature
- [ ] 3.7.4: Unsupported claim flagging — highlight claims without citations in output
- [ ] 3.7.5: Citation confidence — distinguish between "source supports claim" and "source does not contradict claim"

### Task 3.8: VerificationAsymmetryTracker

- [ ] 3.8.1: Claim categorization — verifiable (testable with available resources), partially verifiable (testable but expensive/time-consuming), non-verifiable (currently untestable by principle or resource)
- [ ] 3.8.2: Track verification status over time — as new literature arrives, re-evaluate claim verifiability
- [ ] 3.8.3: Verification gap reporting — "40% of generated hypotheses have no known path to verification"
- [ ] 3.8.4: Suggest verification path — for verifiable claims, suggest experimental or computational approach

### Task 3.9: Ethics Layer Tests

- [ ] 3.9.1: Unit tests for EthicalFirewall — DURC detection with known test cases
- [ ] 3.9.2: Unit tests for RiskTier classification for each tier
- [ ] 3.9.3: Unit tests for DataSovereigntyChecker — consent parsing, restriction enforcement
- [ ] 3.9.4: Unit tests for CarbonBudgetTracker — FLOPs calculation, kWh conversion, budget enforcement
- [ ] 3.9.5: Unit tests for UncertaintyQuantifier — confidence scoring, contradiction detection
- [ ] 3.9.6: Unit tests for SourceGrounding — citation enforcement, unsupported claim flagging
- [ ] 3.9.7: Unit tests for VerificationAsymmetryTracker — claim categorization, tracking
- [ ] 3.9.8: Integration test: ethical firewall → block → provenance entry → audit log

---

**Phase 3 Exit Criteria**: All safety modules operational. DURC detection blocks known test cases. Carbon budget enforces limits. Provenance entries include ethical firewall decisions.

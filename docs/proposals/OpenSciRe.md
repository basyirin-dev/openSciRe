# OpenSciRe — Epistemically Honest Scientific AI: Ecosystem Overview

## I. Executive Summary

**OpenSciRe** is an open-source, local-first, epistemically honest scientific AI ecosystem built in explicit response to Google's Gemini for Science (announced at I/O 2026). Where Google offers three proprietary, cloud-locked tools (Co-Scientist for hypothesis generation, AlphaEvolve/ERA for computational discovery, NotebookLM for literature insights) arranged in a linear waterfall architecture, OpenSciRe provides a **cyclical, re-entrant, provenance-native framework** that treats uncertainty, falsification, and human judgment as architectural requirements — not afterthoughts.

The project begins where Google's philosophy ends: with the recognition that scientific AI tools are not neutral instruments but **epistemic interventions** that shape what questions researchers ask, what evidence they trust, and whose knowledge counts. Google's framework conflates information synthesis with understanding, treats the scientific method as an optimizable pipeline, and embeds the interests of its enterprise partners into the architecture of discovery itself. OpenSciRe rejects this on first-principles philosophical grounds and builds toward an alternative — one grounded in situated knowledges (Haraway), falsification-first methodology (Popper), tacit knowledge preservation (Ryle, Polanyi), and the irreducible human act of scientific judgment.

Concretely, OpenSciRe delivers three layers: **openscire-philosophy** (the epistemic foundation, ethical architecture, and hard limits encoded in code), **openscire-core** (the provenance DAG, uncertainty quantification, verification asymmetry tracking, falsification mesh, and ethical firewall), and four domain-specific pillars — **openscire-literature** ("what is known?"), **openscire-hypothesis** ("what if?"), **openscire-sandbox** ("does it work?"), and **openscire-bio** (domain-specific database integration). All layers run locally by default, support BYOK and Ollama/vLLM/llama.cpp for inference, and produce cryptographically signed, RO-Crate-exportable provenance traces for every operation.

This document is the North Star. It maps every gap identified across the eight critique files to a specific architectural mitigation, defines the component ecosystem, and ties the development roadmap to the existing phase documents. It is the single source of truth for *why* OpenSciRe exists, *what* it builds, and *how* the pieces fit together.

---

## II. The Philosophy Layer (openscire-philosophy)

The philosophy layer is not a separate document or set of principles — it is compiled into code. Every module in OpenSciRe encodes an epistemic stance. The following sections articulate those stances and how they are instantiated architecturally.

### A. Epistemic Foundation

OpenSciRe's epistemic foundation rests on six principles, each derived from a specific gap in Google's framework identified in the critiques:

#### 1. Situated Knowledges — No View from Nowhere

**Philosophical source**: Haraway's "Situated Knowledges" (1988) — the claim that all knowledge is marked by its origin; there is no disembodied, universal perspective.

**Gap addressed**: Google's framework treats a hypothesis generated from a corpus dominated by English-language, Northern, well-funded institutions as universal knowledge. It is, in fact, situated knowledge masquerading as objective truth. [02_philosophy.md](../../critiques/02_philosophy.md): §1 ("The Conflation of Information Synthesis with Understanding").

**Architectural instantiation**:

- **`DataSovereigntyChecker`** (Phase 3.3) classifies every ingested data item by origin: public corpus, licensed database, IRB-approved study, indigenous knowledge, proprietary dataset, clinical trial. This classification is not a metadata tag; it is a **structural constraint** that travels with the data through the provenance DAG. A claim generated from a corpus skewed toward English-language Northern institutions carries an explicit `corpus_bias` parameter in its `ProvenanceEntry` metadata — not as a footnote, but as a first-class field in the signed record.
- **`LiteratureReference` model** (Phase 1.2.5) includes `source_repository`, `language`, `publisher_country`, and `funding_source` fields. These are not optional. Every reference without them is tagged `provenance_incomplete` at ingestion.
- **Non-English corpus support** (Phase 4.8) ingests metadata from CNKI, Wanfang Data, SciELO, AJOL, and eLibrary.ru, with multilingual embedding models (LaBSE, BGE-M3) that operate independently of any cloud API. The system does not claim to be universal; it surfaces its **linguistic and geographic coverage boundaries** in every literature synthesis report.

#### 2. Falsification-First — Not Verification-First

**Philosophical source**: Popper's "Logic of Scientific Discovery" — science advances through falsification, not verification. A hypothesis that cannot be falsified is not scientific.

**Gap addressed**: Google's "deep verification" and "scoring" mechanisms are verificationist. They confirm; they do not refute. The system is designed to produce normal science (Kuhn), not revolutionary science. [02_philosophy.md](../../critiques/02_philosophy.md): §7 ("The Algorithmic Fossilization of Method"). Also [03_structural_triad.md](../../critiques/03_structural_triad.md): §3 ("The Missing Terminal Stage: Validation, Replication & Falsification").

**Architectural instantiation**:

- **`FalsificationAgent`** (Phase 6.4) is a first-class agent, not a secondary reviewer. Given a hypothesis, it actively searches for contradictory evidence, constructs counter-examples, identifies experimental confounds, and generates alternative explanations. Its output is a structured `FalsificationReport` that is cryptographically signed and stored in the provenance DAG alongside the original hypothesis. If the `FalsificationAgent` cannot find counter-evidence, that is noted — but the hypothesis is not promoted to "confirmed"; it is promoted to "not yet falsified."
- **`VerificationAsymmetryTracker`** (Phase 3.8) categorizes every claim as verifiable, partially verifiable, or non-verifiable. This categorization is **mandatory** before any claim is presented to the user. Claims categorized as non-verifiable are displayed with explicit epistemic caveats: "This claim cannot currently be tested with available resources."
- **Risk Tier Classification** (Phase 3.2) uses differential speed governance: high-risk hypotheses (virology, dual-use chemistry) face a mandatory 24-hour cooling-off period before any action can be taken. This is architectural — the system physically cannot proceed without a human override that is itself logged and signed.

#### 3. Knowing-That vs. Knowing-How — Judgment Cannot Be Automated

**Philosophical source**: Ryle's distinction between propositional knowledge (knowing-that) and procedural knowledge (knowing-how). Scientific mastery involves tacit, embodied skills that cannot be reduced to token generation.

**Gap addressed**: Google's framework treats scientific knowledge as a combinatorial search problem — synthesizing millions of papers to produce propositions. It has no account of the tacit dimension of scientific judgment. [02_philosophy.md](../../critiques/02_philosophy.md): §1 ("The Distinction Between Knowing-That and Knowing-How").

**Architectural instantiation**:

- **Mandatory Human Checkpoint Nodes** (Phase 6.2.6, cross-cutting per [00_cross_cutting.md](../../docs/phases/00_cross_cutting.md)): The architecture includes hard stops where the system cannot proceed without explicit human evaluation. These are not optional UI buttons — they are **architectural constraints** enforced at the `SupervisorAgent` orchestration layer. A human must read, evaluate, and sign off (via cryptographic signature in the provenance DAG) before certain operations continue.
- **Anti-deskilling design**: The system does not generate final experimental protocols automatically. Instead, `ExperimentalDesignAdvisor` (Phase 7.3) generates a structured protocol with identified control variables, sample size estimates, and statistical method suggestions — but leaves the **critical judgment calls** (e.g., which control variables are most relevant given the lab's specific conditions) as explicit prompts requiring human input. The system says "here is what I can suggest; you must decide."
- **Pedagogical Commitment** (§II-D below): Every output that makes a methodological recommendation also surfaces the reasoning chain — why specific sources were selected, what parameters were used, what alternatives were considered. This is not transparency theater; it is structural support for the human's development of their own knowing-how.

#### 4. Negative Knowledge as a First-Class Citizen

**Philosophical source**: Negative knowledge — knowledge of what does not work, what is false, what has been refuted — is structurally equal to positive knowledge in the progress of science.

**Gap addressed**: The file drawer problem (publication bias toward positive results) is one of science's deepest structural flaws. Google's triad amplifies this bias by making positive generation frictionless and negative results structurally invisible. [03_structural_triad.md](../../critiques/03_structural_triad.md): §10 ("The Missing Negative Result & Null Hypothesis Architecture").

**Architectural instantiation**:

- **`NegativeResultRegistry`** (Phase 6.6) is a first-class storage system, structurally equal to the literature index. It stores `NegativeResult` entries — hypothesis tested, method used, result (null, contradictory, inconclusive), confidence, reason for failure — all cryptographically signed and searchable by domain, method, and date. When the `FalsificationAgent` successfully falsifies a hypothesis, the result is **automatically registered**.
- **Provenance DAG chaining**: Negative results are linked to their source hypotheses and to related literature. A search for "transfer learning for protein folding" will surface not only the positive results but also the registry entries reading "five groups attempted this between 2022–2025; all failed for the following reasons."
- **No delete, only supersede**: Negative results cannot be deleted from the registry. They can be superseded by contradictory evidence (a later successful replication), but the original entry remains in the provenance chain — ensuring that the record of failure is not lost.

#### 5. Uncertainty as an Architectural Requirement, Not an Afterthought

**Philosophical source**: Scientific claims are inherently uncertain. Quantifying and displaying that uncertainty is a requirement of epistemic honesty.

**Gap addressed**: Google's framework produces confidence — scores, citations, synthesized reports — without structural support for reflexive doubt. The triad treats methodology as transparent and unproblematic. [03_structural_triad.md](../../critiques/03_structural_triad.md): §9 ("The Absence of a Meta-Scientific / Reflexive Layer").

**Architectural instantiation**:

- **`UncertaintyQuantifier`** (Phase 3.6) assigns a confidence score to every generated claim based on source quality, inter-source agreement, and model certainty signals. This is not optional metadata — it is displayed alongside every claim as a mandatory uncertainty indicator. If confidence drops below a configurable threshold, the system refuses to present the claim without a human override.
- **Knowledge boundary flagging**: When the system determines that a question cannot be answered from available literature, it says so explicitly — and logs the boundary condition in the provenance DAG. This is enforced at the `LiteratureReviewAgent` level (Phase 6.3).
- **Contradiction detection**: When two or more sources disagree, the system surfaces both positions with their respective confidence scores and supporting provenance chains. It does not attempt to adjudicate — it presents the contradiction as a finding in itself.

#### 6. How Each Principle is Encoded in Architecture (Summary Table)

| Principle | Enforced By | Enforcement Mechanism |
|-----------|-------------|----------------------|
| Situated knowledges | DataSovereigntyChecker, LiteratureReference model, non-English corpus bridges | Origin classification is a structural constraint; coverage boundaries are surfaced explicitly |
| Falsification-first | FalsificationAgent, VerificationAsymmetryTracker, Risk Tier Classification | FalsificationAgent is a first-class agent; non-verifiable claims blocked from presentation |
| Knowing-that vs. knowing-how | Mandatory Human Checkpoint Nodes, ExperimentalDesignAdvisor, Pedagogical Commitment | Hard stops at judgment-critical junctures; system exposes reasoning chain |
| Negative knowledge | NegativeResultRegistry, provenance DAG chaining | Registry structurally equal to literature index; results cannot be deleted |
| Uncertainty as requirement | UncertaintyQuantifier, KnowledgeBoundaryFlagging, ContradictionDetection | Mandatory confidence display; boundary conditions surfaced; contradictions presented as findings |

### B. Ethical Architecture

The ethical architecture is not a separate compliance layer bolted onto the system — it is cross-cutting, present at every level from data ingestion to output rendering. This reflects the structural critique that Google's triad treats ethics as an external overlay rather than an internal architectural constraint. [03_structural_triad.md](../../critiques/03_structural_triad.md): §13 ("The Absence of an Ethical/Governance Structural Layer").

#### 1. Ethical Firewall (DURC Detection)

**What it does**: Scans all prompts and responses for Dual-Use Research of Concern (DURC) patterns — pathogen enhancement, novel toxin synthesis, weapons delivery systems, AI safety evasion, surveillance hardening. [03_ethics_layer.md](../../docs/phases/03_ethics_layer.md): Task 3.1.

**How it works**:
- **Classification method**: LLM-assisted classification combined with keyword + embedding-based detection. The embedding-based classifier runs locally (no cloud dependency) using sentence-transformers models. The LLM-assisted classifier uses whatever model the system is currently configured with, but the keyword/embedding baseline ensures coverage even if the LLM classifier is unavailable.
- **Action matrix** (configurable per policy):
  | Detection Level | Action |
  |-----------------|--------|
  | Flag | Log only, no user-visible change |
  | Warn | User sees warning banner, must acknowledge |
  | Block | Execution prevented; user cannot override |
  | Escalate | Workflow paused; designated reviewer notified |
- **False positive feedback loop**: Contested flags are reviewed and used to tune the classifier. The entire cycle is logged in the provenance DAG (non-removable, append-only).

#### 2. Risk Tier Classification (Differential Speed Governance)

**What it does**: Automatically classifies research domains into three tiers, each with different procedural requirements. [03_ethics_layer.md](../../docs/phases/03_ethics_layer.md): Task 3.2.

**Three tiers**:

| Tier | Description | Examples | Requirements |
|------|-------------|----------|--------------|
| **Tier 1 (High Risk)** | Dual-use, catastrophic potential | Virology, toxin synthesis, weapons physics, AI safety | Mandatory 24-hour cooling-off period; external reviewer gate; cannot proceed autonomously |
| **Tier 2 (Medium Risk)** | Human/animal subjects, controlled data | Clinical research without IRB clearance, human subjects data, animal research | Mandatory human checkpoint; cannot proceed without explicit signed approval |
| **Tier 3 (Low Risk)** | Standard computational science | Solar forecasting, theoretical physics, mathematics, materials science | Standard workflow |

**Key architectural features**:
- **Domain auto-classification** based on query content, literature context, and MeSH terms. Users can escalate (move a query to higher scrutiny) but cannot silently downgrade. Any downgrade attempt is logged in the provenance DAG with justification required.
- **Tier awareness** is baked into every output and workflow template. The CLI/UI always displays the current tier. The `SupervisorAgent` (Phase 6.2) will not dispatch tasks that violate tier constraints.
- **Differential speed governance**: Tier 1 workflows are architecturally slowed down. The `NegativeResultRegistry` cross-links Tier 1 findings to relevant safety literature before any output is rendered. This is a structural response to the "catastrophic discovery acceleration" gap ([08_miscellaneous.md](../../critiques/08_miscellaneous.md): §37).

#### 3. Data Sovereignty Checker

**What it does**: Verifies provenance and consent constraints before ingesting data. Classifies data origin and enforces usage restrictions. [03_ethics_layer.md](../../docs/phases/03_ethics_layer.md): Task 3.3.

**Origin classes** (enforced in `DataSovereigntyChecker`):
- **Public**: Open-access publications, freely licensed datasets
- **Licensed**: Subscription content (Elsevier, Springer Nature) — requires valid institutional access
- **IRB-approved**: Human subjects data — verifies that IRB documentation is present in provenance
- **Indigenous**: Culturally restricted knowledge — consults `IndigenousKnowledgeProtector` (Task 3.4)
- **Clinical**: HIPAA/GDPR-regulated data — enforces regional restriction markers
- **Proprietary**: Institutional or corporate data — enforces usage scope from metadata

#### 4. Carbon Budget Tracker

**What it does**: Tracks compute per operation (FLOPs → kWh → CO2e), displays per-query carbon reports, enforces user-configurable monthly carbon budgets with hard stops at 100%. [03_ethics_layer.md](../../docs/phases/03_ethics_layer.md): Task 3.5.

**Architectural details**:
- FLOPs estimation uses model size, token count, and hardware profile (user-configured or auto-detected).
- kWh conversion uses hardware efficiency factors drawn from a local lookup table (no cloud dependency).
- CO2e conversion uses regional grid carbon intensity, user-configurable (default: global average).
- Cumulative budget enforcement: warning at 80%, hard stop at 100%. The hard stop is architectural — the `ModelProvider` interface (Phase 2) refuses to dispatch operations when the budget is exhausted, and the `SupervisorAgent` refuses to schedule new research tasks.

#### 5. How Ethics Is Cross-Cutting

Per the requirements in [00_cross_cutting.md](../../docs/phases/00_cross_cutting.md), every phase after Phase 3 must:
- Check `EthicalFirewall` before generating any claim
- Log `RiskTier` classification in provenance
- Display carbon cost estimate for compute-heavy operations
- Flag unsupported claims and require citations before final output

This means the ethical architecture is not a single module you pass through — it is a **mesh** that touches every component: data ingestion (`DataSovereigntyChecker`), model dispatch (`CarbonBudgetTracker`), hypothesis generation (`RiskTier` classification), literature synthesis (`EthicalFirewall` for DURC in retrieved texts), and output rendering (`VerificationAsymmetryTracker` for uncertainty display). There is no path through the system that avoids all ethical checkpoints.

### C. Philosophy of Limits

The single most critical gap across all critiques is that "Gemini for Science has no theory of its own limits." [08_miscellaneous.md](../../critiques/08_miscellaneous.md): §54 ("The Ultimate Human Override Absence"). OpenSciRe encodes a philosophy of limits directly into its architecture.

#### 1. What the System WILL NOT Do (Hard Boundaries)

These are not advisory guidelines — they are architectural constraints:

- **No wet lab execution**: OpenSciRe will not control laboratory equipment, ingest sensor data in real time, or monitor physical experiments. These are material science activities that require physical presence.
- **No clinical decision support**: The system will not generate treatment recommendations, diagnostic suggestions, or clinical protocols intended for direct patient care. Any output that appears to fall into this category triggers an automatic `EthicalFirewall` escalation and a `Tier 1` classification.
- **No autonomous hypothesis testing**: The system will not execute experiments (computational or otherwise) without a human checkpoint. The `SupervisorAgent` requires human sign-off at the transition from hypothesis to execution.
- **No liability assumption**: Every output includes a disclaimer that the human researcher bears final responsibility for design, execution, and interpretation. This is not a legal shield — it is an epistemic statement.

#### 2. Knowledge Boundary Flagging

The `UncertaintyQuantifier` (Phase 3.6.3) includes a dedicated knowledge boundary detection mechanism:

- When a query falls outside the available literature corpus, the system returns: "This question cannot be answered from available literature. The literature corpus currently covers [X domains]. Your query appears to belong to [Y domain], which has [Z papers indexed]."
- When a query is technically answerable but requires assumptions that the system cannot verify, the system returns: "I can generate an answer, but it requires assumptions about [A, B, C] that I cannot verify. Proceed with caution."
- When a query is in principle unanswerable (e.g., "what is the fundamental nature of consciousness?"), the system returns: "This is a philosophical question outside the scope of scientific AI tools. No amount of literature synthesis can provide a definitive answer."

#### 3. Mandatory Uncertainty Display on All Outputs

Every output — every claim, every hypothesis, every literature synthesis — is displayed with an uncertainty indicator. The format is:

```
[Claim text]
Confidence: 72% (moderate — 3 supporting sources, 1 contradictory source)
Knowledge boundary: This claim is supported by computational evidence only;
no wet lab validation has been found in the available corpus.
Verification status: Partially verifiable (estimated cost: $15K–$50K, 3–6 months)
```

This is not a toggle. It cannot be hidden. The `UncertaintyQuantifier` is called at every output rendering point, and the display template enforces the inclusion of confidence, knowledge boundary, and verification status fields.

#### 4. Verification Asymmetry Tracking

The `VerificationAsymmetryTracker` (Phase 3.8) categorizes claims into three classes:

| Class | Definition | Display treatment |
|-------|------------|-------------------|
| **Verifiable** | Can be tested with currently available resources | "This claim is testable. Suggested verification path: [methods]" |
| **Partially verifiable** | Testable but expensive or time-consuming | "This claim is theoretically testable but costly. Estimated cost: [X], timeline: [Y]" |
| **Non-verifiable** | Cannot currently be tested by principle or resource constraint | "This claim cannot currently be verified with available resources. Do not treat as scientific evidence." |

Claims in the "non-verifiable" class are flagged with a prominent warning. The system will not allow a non-verifiable claim to be exported as evidence without an explicit human override that itself becomes a signed provenance entry.

#### 5. The "Hippocratic Oath" Architecture — Ethics in Code

OpenSciRe operationalizes the missing "Hippocratic Oath for AI Science Developers" [08_miscellaneous.md](../../critiques/08_miscellaneous.md): §50 through three architectural commitments:

1. **First, do no epistemic harm**: The `EthicalFirewall` is invoked before every output. The `UncertaintyQuantifier` prevents presentation of claims that exceed known knowledge boundaries. The `VerificationAsymmetryTracker` prevents treatment of non-verifiable claims as evidence.
2. **Accountability for dual-use**: Every interaction that triggers a DURC flag produces a non-removable provenance entry. The `NegativeResultRegistry` cross-links dangerous hypotheses with relevant safety literature.
3. **Fiduciary duty to scientific truth**: The system's primary performance metric is not hypothesis volume or user engagement but **epistemic integrity** — measured by verification rate, falsification attempts logged, uncertainty disclosures surfaced, and knowledge boundaries respected.

#### 6. Meta-Cognition: The System Knows What It Doesn't Know

OpenSciRe's meta-cognitive layer (distributed across `UncertaintyQuantifier`, `VerificationAsymmetryTracker`, and `KnowledgeBoundaryFlagging`) gives the system the ability to:

- **Know its corpus coverage**: "I have indexed 4,872 papers in this domain. The literature review is X% complete."
- **Know its model limitations**: "The underlying model [model name] has known biases: [bias description from `ModelCard`]. Consider this when interpreting results."
- **Know its verification gaps**: "Of the 12 claims generated in this research context, 5 have verification paths, 4 are partially verifiable, and 3 are non-verifiable."
- **Know its own provenance**: "Every claim in this document can be traced to a signed provenance entry. Click any claim to view its full chain."

### D. Pedagogical Commitment

OpenSciRe is explicitly designed to **teach**, not just to output. This addresses the PhD curriculum obsolescence crisis ([08_miscellaneous.md](../../critiques/08_miscellaneous.md): §16) and the disappearance of methodological apprenticeship (§17).

#### 1. Outputs Explain Their Own Reasoning

Every generated output includes a **reasoning trace**:

```
[Generated hypothesis]
Why this hypothesis was generated:
1. Literature gap detected: No studies have examined [X] in the context of [Y].
2. Cross-domain analogy applied: The mechanism in [field A] maps structurally to [field B].
3. Two supporting sources: [citations]; one contradictory source: [citation].
4. Parameters used: similarity_threshold=0.7, serendipity_level=0.3
5. Alternative hypotheses considered (and rejected):
   - [H2]: Rejected due to insufficient falsifiability
   - [H3]: Rejected due to excessive test cost
```

This trace is not an optional detail — it is part of the output template. The `ProvenanceExporter` (Phase 1.5.8) ensures all traces survive export.

#### 2. Anti-Deskilling Design

The system is designed to **assist, not replace**, researcher judgment:

- **Progressive disclosure**: Novice users see simpler interfaces with more guidance. Expert users can access the full configuration surface. The transition between modes is explicit — the system tells you "you are using 'progressive' mode" and offers to switch.
- **Methodological transparency**: When the `ExperimentalDesignAdvisor` suggests a statistical test, it also provides a one-paragraph explanation of why that test is appropriate and what assumptions it makes. This is not a link to documentation — it is inline.
- **Checkpoint rationale**: When a human checkpoint is triggered, the system explains *why* it cannot proceed — "I cannot design this experiment because it requires knowing which cell line you are using. This is a judgment call that depends on your specific experimental context."

#### 3. Human Checkpoints as Architectural Hard Stops

Checkpoints are not optional UI buttons. They are enforced at the `SupervisorAgent` orchestration layer:

- The `SupervisorAgent` (Phase 6.2) has a state machine that explicitly includes a `waiting_for_human` state.
- Workflows are templated with checkpoint nodes. For example, the default `literature review → hypothesis → falsification` workflow includes checkpoints at:
  1. After literature review synthesis (human must approve the synthesis before hypothesis generation begins)
  2. After hypothesis generation (human must select which hypotheses to pursue)
  3. After falsification report (human must assess the falsification evidence)
- These checkpoints are **architecturally mandatory** for certain workflow templates. The user can define custom workflows that remove checkpoints, but this is a deliberate action that requires modifying the workflow template and is logged in provenance.

#### 4. Serendipity Preservation

**Gap addressed**: The role of serendipity in scientific discovery — major breakthroughs emerge from accident, failure, and observation. Google's pipeline model of discovery has no room for serendipity. [02_philosophy.md](../../critiques/02_philosophy.md): §7 ("The Role of Serendipity"). [03_structural_triad.md](../../critiques/03_structural_triad.md): §12 ("The Missing Interdisciplinary Translation Structure").

**Architectural instantiation: `SerendipityInjector`** (Phase 7.2):

- **Cross-domain analogy**: The injector randomly samples concepts from unrelated fields and tests for analogical mapping. Configurable `serendipity_level` parameter (0 = conservative consensus, 1.0 = maximal exploration).
- **Contradiction-driven exploration**: When two or more sources disagree, the injector generates hypotheses that reconcile the contradiction — even if the reconciliation requires bridging normally separate domains.
- **Audit trail**: All serendipitous connections are logged with their source fields and the random seed used, ensuring reproducibility. "This connection is serendipitous" is displayed as a positive epistemic feature, not a bug.

---

## III. The Core Architecture (openscire-core)

### A. Cyclical Structural Triad (vs Google's Linear Stage-Gate)

#### Google's Architecture: Linear Waterfall

Google's three-tool framework (Co-Scientist → AlphaEvolve/ERA → NotebookLM) is structurally a **linear stage-gate model**: Read → Hypothesize → Test. As identified in [03_structural_triad.md](../../critiques/03_structural_triad.md): §1, this is a waterfall architecture with no feedback loops, no retroduction, and no mechanism for experimental results to re-seed the hypothesis tournament.

```
Google's implicit model:
  Literature → Hypothesis → Experiment
     (Read)      (What if?)    (Does it work?)
```

The problems with this are structural, not cosmetic:
- There is no retroduction (Peirce) — the movement from surprising experimental results back to theory revision.
- The multi-agent tournament in Hypothesis Generation is structurally isolated from the code variations in Computational Discovery.
- A failed experiment cannot re-seed the literature review with new questions.
- The architecture is determined by **corporate asset availability** (Co-Scientist, AlphaEvolve, NotebookLM are existing Google products), not by scientific workflow analysis [03_structural_triad.md](../../critiques/03_structural_triad.md): §5.

#### OpenSciRe's Architecture: Cyclical/Re-entrant

OpenSciRe replaces the linear waterfall with a **cyclical, re-entrant architecture** with explicit backflow channels:

```
                          ┌─────────────────────────────┐
                          │   openscire-philosophy       │
                          │  (epistemic constraints,     │
                          │   ethics, uncertainty,       │
                          │   falsification)             │
                          └──────────┬──────────────────┘
                                     │
┌────────────────────────────────────┼───────────────────────────┐
│           openscire-core           │                           │
│  (provenance DAG, ethical firewall,│                           │
│   uncertainty quantifier, falsifica│                           │
│   tion mesh, verification asymmetry)│                          │
└──────────┬──────────┬──────────────┼───────────────────────────┘
           │          │              │
           ▼          ▼              ▼
┌──────────────┐ ┌──────────┐ ┌──────────────┐
│ openscire-   │ │openscire-│ │ openscire-   │
│ literature   │◄┤hypothesis├►│ sandbox      │
│ (what is     │ │(what if?)│ │(does it work?)│
│  known?)     │ └────┬─────┘ └──────┬───────┘
└──────┬───────┘      │              │
       │              │              │
       └──────────────┴──────────────┘
                     │
                     ▼
          ┌──────────────────┐
          │ NegativeResult   │
          │ Registry         │
          └──────────────────┘
```

**Backflow channels** (arrows pointing "backward" through the cycle):

| Source | Target | Mechanism | Purpose |
|--------|--------|-----------|---------|
| Sandbox (failed experiment) | Literature | Retrodiction analysis: "the sandbox result contradicts the literature — re-open literature review to find alternative frameworks" | Failed experiments re-seed hermeneutic investigation |
| Sandbox (unexpected result) | Hypothesis | `FalsificationAgent` receives experimental result as input; generates new falsification attempts | Serendipitous results trigger new hypothesis space exploration |
| Hypothesis (falsified) | Negative Result Registry | Automatic registration of null/contradictory results | Knowledge that something doesn't work is preserved |
| Negative Result Registry | Literature | Cross-link: "this hypothesis was tested and failed — here are the related papers that attempted similar approaches" | Failed hypotheses inform future literature review |
| Literature (contradiction) | Hypothesis | `SerendipityInjector` uses inter-source contradictions as seeds for new hypotheses | Contradictions across literature drive ideation |
| Any layer | Ethical Firewall | Every operation passes through ethical screening; flagged results pause or escalate | Ethics is cross-cutting, not a gate at one end |

**The three OpenSciRe pillars** (corresponding to Google's three but structurally transformed):

1. **openscire-literature** — "What is known?" (hermeneutic layer)
   - Multi-source ingestion (PubMed, arXiv, Semantic Scholar, OpenAlex, non-English corpora)
   - Full-text PDF parsing, embedding, semantic search
   - Citation graph analysis, retraction monitoring
   - Provenance-native: every literature reference carries its source, access date, language, and bias markers

2. **openscire-hypothesis** — "What if?" (abductive/ideation layer)
   - Literature-grounded hypothesis synthesis
   - Multi-hypothesis generation with prioritization
   - `SerendipityInjector` for cross-domain analogy and contradiction-driven exploration
   - `VerifiabilityAssessor` for cost-of-test and falsifiability scoring
   - `ExperimentalDesignAdvisor` for protocol generation

3. **openscire-sandbox** — "Does it work?" (computational execution layer)
   - Rust-based sandboxed code execution (seccomp, landlock, cgroups)
   - Python, R, Julia, bash, C++ support
   - Deterministic execution with random seed capture
   - ReproducibilityBundle generation (environment lockfile, dependency tree, config snapshot)

4. **openscire-bio** — Life science database integration (analogous to Google's Science Skills)
   - UniProt, AlphaFold DB, InterPro, and other life science API bridges
   - Integrated as a foundational data layer beneath all three pillars (not siloed as a separate product)
   - Provenance-native: every database query carries database version, access date, and API reliability metrics

**How they feed back into each other**:

- **FalsificationAgent re-seeds HypothesisAgent**: When the `FalsificationAgent` (Phase 6.4) successfully falsifies a hypothesis, its report becomes input to the `HypothesisGenerator` (Phase 7.1), which treats falsification as a signal to generate new, non-obvious hypotheses in the same space.
- **NegativeResultRegistry informs LiteratureEngine**: The `NegativeResultRegistry` (Phase 6.6) publishes cross-links to the `LiteratureReviewAgent` (Phase 6.3), so literature synthesis includes not just positive literature but the history of failed attempts.
- **EthicsAgent feeds SupervisorAgent**: The `EthicsAgent` (Phase 6.5) classifies risk tiers and flags DURC concerns; the `SupervisorAgent` (Phase 6.2) uses this to route workflows differently (e.g., Tier 1 workflows get mandatory cooling-off periods).

### B. Cross-Cutting Architecture Layers

#### 1. Provenance DAG (Phase 1)

Every significant operation in OpenSciRe produces a cryptographically signed `ProvenanceEntry` that forms a Directed Acyclic Graph (DAG). This is the system's central nervous system.

**Key characteristics**:

- **Entry structure** (`ProvenanceEntry`, Phase 1.2.4): action_id, parent_ids, agent_id, model_id, parameters_snapshot (JSON hash), input_hash (SHA-256), output_hash (SHA-256), timestamp (ISO 8601 with timezone), cryptographic_signature (Ed25519)
- **Entry chaining**: Every entry records `parent_ids`, forming a DAG that can be traversed backward (to see what inputs produced an output) and forward (to see how an input was used).
- **Cryptographic signing**: Each entry is signed with an Ed25519 key. The signature covers the entire entry content. Verification: `provenance_entry.verify()` returns `bool`. Signature aggregation: root hash of DAG for audit report integrity.
- **Storage backends**: In-memory (development), SQLite (local default), PostgreSQL (team/enterprise, Phase 12+).
- **Export formats**: JSON (debug), RO-Crate (interoperable with institutional repositories), W3C PROV (FAIR-compliant).

**Critical subcomponent: `ResearchChronologyEnforcer`** (Phase 1.5.10):
This component cryptographically timestamps hypotheses before evidence is synthesized and detects temporal ordering violations. It is the architectural answer to AI-enabled HARKing (Hypothesizing After Results are Known) identified in [08_miscellaneous.md](../../critiques/08_miscellaneous.md): §43. If a literature entry is ingested *after* a hypothesis was timestamped but is cited as evidence *for* that hypothesis, the enforcer flags the temporal violation.

#### 2. Uncertainty Quantifier (Phase 3.6)

Detailed in §II-A-5 and §II-C-3 above. Key technical specifications:

- **Confidence scoring** combines: source quality (journal impact factor, retraction status, citation count), inter-source agreement (percentage of sources that agree), model certainty (logprobs, token probabilities, refusal signals).
- **Contradiction detection** compares claims across the literature corpus and surfaces disagreements. When two sources contradict each other, both are presented with their respective confidence scores.
- **Knowledge boundary flagging** uses embedding similarity to detect when a query is outside the indexed corpus. Configurable threshold (default: cosine similarity < 0.3 to nearest indexed cluster triggers boundary flag).

#### 3. Verification Asymmetry Tracker (Phase 3.8)

Detailed in §II-C-4 above. Operational details:

- Claims are categorized at generation time by the `VerifiabilityAssessor` (Phase 7.4) based on:
  - Falsifiability (Popperian criterion: is there a conceivable observation that would disprove this?)
  - Testability (available resources: time, money, equipment, expertise)
  - Accessibility (is the required equipment/expertise available to the current user or institution?)
- Tracking over time: when new literature is ingested, the tracker re-evaluates previously categorized claims. A claim that was "non-verifiable" last month may become "verifiable" this month because a new methodology was published.
- **Verification gap reporting**: Periodically generates a report: "40% of generated hypotheses have no known path to verification."

#### 4. Falsification Mesh

The falsification mesh is a network of components that actively attempt to **destroy** hypotheses, not support them:

- **FalsificationAgent** (Phase 6.4): Given a hypothesis, searches for contradictory evidence, constructs counter-examples, identifies confounds, generates alternative explanations. Outputs a structured `FalsificationReport`.
- **Null Hypothesis Agent** (deferred to post-pilot, Phase 6): Generates null hypotheses for every generated hypothesis and ensures they are statistically tested against the proposed hypothesis.
- **Cross-agent contradiction detection**: When the `LiteratureReviewAgent` identifies contradictory findings across sources, those contradictions are automatically routed to the `FalsificationAgent` as candidate falsifications of any hypothesis that relies on the contested finding.
- **Negative result feedback**: When the `NegativeResultRegistry` logs a falsified hypothesis, the falsification mesh automatically updates its knowledge base, preventing the same dead-end from being proposed again.

#### 5. Ethical Firewall (Phase 3.1)

Detailed in §II-B-1 above. Cross-cutting: invoked at prompt generation, response rendering, literature retrieval, hypothesis formulation, and experimental design stages. No layer is exempt.

### C. Data & Provenance Layer

#### Storage Architecture

| Data Type | Default Backend | Team/Enterprise | Export Format |
|-----------|----------------|-----------------|---------------|
| Provenance DAG | SQLite | PostgreSQL | RO-Crate, W3C PROV, JSON |
| Literature embeddings | Chroma / FAISS | Managed vector DB | Parquet, NPZ |
| Literature metadata | SQLite | PostgreSQL | JSON, CSV, BibTeX |
| Config | YAML/TOML file | Same | JSON Schema |
| Negative results | SQLite | PostgreSQL | RO-Crate, JSON, CSV |
| Carbon budget | SQLite | PostgreSQL | JSON |
| User models (PyTorch) | Disk directory | S3/MinIO | Pickle, ONNX, Safetensors |
| ReproducibilityBundle | Zip archive | Same | Zip (standardized format) |

#### Cryptographic Infrastructure

- **Ed25519 signing keys** for provenance entries. Keys stored in OS keychain (macOS Keychain, Linux Secret Service, Windows Credential Manager) with file fallback (encrypted at rest, never logged).
- **SHA-256 hashing** for all input/output/parameters snapshots.
- **Signature aggregation**: Root hash of the provenance DAG, allowing third-party verification that no entries have been tampered with since the root was signed.

#### ReproducibilityBundle (Phase 1.2.7)

Every research run produces a `ReproducibilityBundle` containing:

```
reproducibility_bundle/
├── environment.lock    # pip freeze / conda env export equivalent
├── dependencies.json   # Full dependency tree with versions
├── config_snapshot.yaml # All configuration parameters
├── random_seeds.json   # All random seeds used in this run
├── data_hashes.json    # SHA-256 hashes of all input datasets
├── hardware_profile.json # CPU, GPU, RAM, OS information
└── provenance_root.sig # Ed25519 signature of provenance DAG root hash
```

This bundle is the answer to the reproducibility crisis in AI-assisted science. Two researchers with the same `ReproducibilityBundle` should be able to reproduce each other's results — provided they have equivalent hardware and the same model provider configuration.

### D. Local-First Design

OpenSciRe's local-first principle is not a feature — it is an architectural constraint.

**What runs locally by default**:

| Component | Default Mode | Cloud Optional? |
|-----------|-------------|-----------------|
| Provenance DAG | SQLite on local disk | PostgreSQL via network (Phase 12) |
| Literature embeddings | Chroma/FAISS (local) | Yes, but not recommended |
| Ethical Firewall (DURC detection) | Local keyword + embedding model | No — local is the only mode for ethics |
| Carbon Budget Tracker | Local computation | No |
| Uncertainty Quantifier | Local computation | No |
| FalsificationAgent | Local model (Ollama/vLLM) | Yes, BYOK (user-provided cloud key) |
| HypothesisGenerator | Local model | Yes, BYOK |
| Literature metadata | Local SQLite | PostgreSQL via network |
| PDF parsing | Local (pdfplumber/pypdf) | No |

**Inference support matrix**:

| Provider | Mode | Use Case |
|----------|------|----------|
| Ollama | Local | Default for individual researchers |
| vLLM | Local | Large-scale local inference with GPU |
| llama.cpp | Local | CPU inference, quantized models |
| LM Studio | Local | GUI-based local model management |
| LiteLLM | Router | Unified API over any provider |
| BYOK (OpenAI/Anthropic/Gemini) | Cloud | User-provided API keys for cloud models |

**No cloud dependency for basic operation**: A researcher with a laptop, Ollama, and a local corpus can use OpenSciRe without ever connecting to the internet. The ethical firewall, provenance DAG, uncertainty quantifier, and falsification mesh all operate using local resources. This is a structural response to the field science offline requirement ([08_miscellaneous.md](../../critiques/08_miscellaneous.md): §21) and the cloud dependence that makes Google's framework unusable for sensitive or disconnected work.

---

## IV. Component Ecosystem Map

```
┌───────────────────────────────────────────────────────────────────┐
│                    openscire-philosophy                            │
│  (epistemic foundation, ethics, limits, pedagogy)                 │
│                                                                   │
│  Principles: situated knowledges, falsification-first,            │
│  knowing-that vs knowing-how, negative knowledge, uncertainty     │
│  as requirement, hard limits, meta-cognition, anti-deskilling     │
│                                                                   │
│  Instantiated in: EthicalFirewall, RiskTier, DataSovereignty,     │
│  CarbonBudget, UncertaintyQuantifier, VerificationAsymmetry        │
└──────────────────────────┬────────────────────────────────────────┘
                           │
┌──────────────────────────┴────────────────────────────────────────┐
│                      openscire-core                                │
│  (provenance DAG, falsification mesh, ethical firewall,           │
│   uncertainty quantifier, verification asymmetry tracker)         │
│                                                                   │
│  ProvenanceTracker → Ed25519-signed DAG                          │
│  FalsificationMesh → FalsificationAgent + NullHypothesisAgent    │
│  EthicalFirewall → DURC detection + risk tiers                   │
│  UncertaintyQuantifier → confidence scoring + contradiction       │
│  VerificationAsymmetryTracker → claim categorization              │
│  CarbonBudgetTracker → FLOPs→kWh→CO2e tracking                   │
│  ResearchChronologyEnforcer → HARKing detection                   │
│  DataSovereigntyChecker → consent verification                    │
│  IndigenousKnowledgeProtector → CARE principles                   │
└───────────┬──────────────────┬──────────────────┬─────────────────┘
            │                  │                  │
┌───────────┴──────────┐ ┌────┴────┐ ┌──────────┴─────────────────┐
│  openscire-literature │ │openscire│ │    openscire-sandbox        │
│  (what is known?)     │ │-hypoth. │ │    (does it work?)         │
│                       │ │(what if)│ │                            │
│ PubMedBridge          │ │Hypothes │ │ Seccomp-BPF sandbox        │
│ ArXivClient           │ │isGenerat│ │ CPU/memory/network limits  │
│ SemanticScholarClient│ │or       │ │ Python/R/Julia/C++ exec    │
│ OpenAlexClient        │ │Serendip │ │ ReproducibilityBundle      │
│ ZoteroBridge          │ │ityInject│ │ Deterministic execution    │
│ MendeleyBridge        │ │or       │ │ Random seed capture        │
│ Non-English bridges   │ │Verifiab │ │ Dependency pinning         │
│ (CNKI, SciELO, AJOL,  │ │ilityAss │ │ TODO: Rust implementation  │
│  eLibrary.ru)         │ │essor    │ │ deferred (Phase 9 stubs)   │
│ RetractionMonitor     │ │Experimen│ │                            │
│ PDFParser             │ │talDesign│ │                            │
│ EmbeddingIndex        │ │Advisor  │ │                            │
│ CitationGraphAnalyzer │ │Synthetic│ │                            │
│                       │ │DataWate │ │                            │
│                       │ │rmarker  │ │                            │
└───────────────────────┘ └─────────┘ └────────────────────────────┘
            │                                                    │
            └──────────────┬─────────────────────────────────────┘
                           │
            ┌──────────────┴──────────────┐
            │      openscire-bio          │
            │  (life science databases)   │
            │                             │
            │  UniProt bridge             │
            │  AlphaFold DB bridge        │
            │  InterPro bridge            │
            │  NCBI GenBank bridge        │
            │  PDB (Protein Data Bank)    │
            │  bridge                     │
            └─────────────────────────────┘
                           │
┌──────────────────────────┴────────────────────────────────────────┐
│              Model Provider Interface (Phase 2)                    │
│                                                                   │
│  OpenAI-compatible (Ollama, vLLM, LM Studio, Groq, Together,     │
│   Fireworks, OpenRouter, Perplexity, custom local endpoints)      │
│  Anthropic (native API)                                           │
│  Google Gemini (native API)                                       │
│  LiteLLM (unified router over 100+ providers)                     │
│  MCP (Model Context Protocol) adapter                             │
│  BYOK (encrypted key storage, OS keyring support)                 │
│  Fallback cascade (local → cheaper local → BYOK → fail)          │
│  Runtime feature detection (tool_use, vision, streaming)         │
│  Local model quantization awareness (GGUF, EXL2, AWQ, GPTQ)      │
└───────────────────────────────────────────────────────────────────┘
```

---

## V. Comprehensive Gap Closure Matrix

### From 01_overview.md (Overview)

| # | Gap Description | OpenSciRe Mitigation | Source Section |
|---|---|---|---|
| G1 | Hypothesis Generation treats science as a combinatorial optimization problem — multi-agent "tournaments" produce statistically likely hypotheses | `FalsificationAgent` actively seeks contradictory evidence; `SerendipityInjector` introduces cross-domain analogies and contradiction-driven exploration; `VerificationAsymmetryTracker` categorizes claims by verifiability | §III-A, §II-C-4 |
| G2 | Computational Discovery generates code variations in parallel but assumes the search space is well-formed | Re-entrant architecture: sandbox results feed back into hypothesis generation and literature review; `NegativeResultRegistry` preserves failed approaches as learnable artifacts | §III-A |
| G3 | Literature Insights structures results into searchable tables — a hermeneutical act that imposes an interpretive grid on texts | `DataSovereigntyChecker` classifies literature by origin and language; non-English corpus bridges preserve plural epistemologies; hermeneutic outputs carry reasoning traces and source context | §II-A-1, §II-D-1 |
| G4 | Enterprise/experimental chasm: two-tier architecture with no graduation path | Unified open-core model: same codebase for individual and enterprise use; PostgreSQL backend for team deployment; Phase 16 monetization model (managed cloud + enterprise features) keeps core free | §VII |
| G5 | Science Skills is architecturally orphaned — not integrated with the three tools | `openscire-bio` integrated as a foundational data layer beneath all three pillars; Zotero/Mendeley bridges provide reference management; PubMed/PMC/Europe PMC bridges connect literature to databases | §III-A |
| G6 | Cloud-native architecture excludes sensitive/disconnected research | All core components run locally; Ethical Firewall, CarbonBudget, provenance DAG are local-only; Ollama/vLLM/llama.cpp for inference; offline mode for field science | §III-D |
| G7 | "Generalist agents > specialized tools" philosophy contradicts three separate tools with distinct UIs/backends | Unified `ModelProvider` abstraction with `SupervisorAgent` orchestration; one architecture that mode-shifts between literature review, hypothesis generation, and sandboxed execution | §III-A |

### From 02_philosophy.md (Philosophy)

| # | Gap Description | OpenSciRe Mitigation | Source Section |
|---|---|---|---|
| P1 | Conflation of information synthesis with understanding — treats knowledge as combinatorial search | Multi-component epistemic architecture: `UncertaintyQuantifier` distinguishes confidence from understanding; `VerificationAsymmetryTracker` marks what is not yet known; `Pedagogical Commitment` ensures outputs explain their reasoning | §II-A, §II-D |
| P2 | Gettier problem — deep verification is itself a black-box classifier; no theory of how we verify the verifiers | `ProvenanceDAG` with `ResearchChronologyEnforcer` provides chain-of-custody for every verification step; `FalsificationAgent` actively tests verifications rather than trusting them; `EthicalFirewall` operates at prompt and response levels | §II-A-2, §III-B-1, §III-B-5 |
| P3 | Situated knowledges ignored — universal knowledge masquerade | `DataSovereigntyChecker` classifies data by origin; `LiteratureReference` model includes language, publisher_country, funding_source; non-English corpus bridges (CNKI, SciELO, AJOL) | §II-A-1 |
| P4 | No account of tacit knowledge (knowing-how) | Mandatory Human Checkpoint Nodes; `ExperimentalDesignAdvisor` makes suggestions but leaves judgment calls to humans; Anti-deskilling design preserves methodological apprenticeship | §II-A-3, §II-D-2 |
| P5 | Science treated as optimization — paradigm-shifting discoveries not accounted for | `SerendipityInjector` with controlled randomness; `FalsificationAgent` looks for anomalies that resist optimization; `NegativeResultRegistry` preserves paradigm-challenging negative results | §II-A-2, §II-D-4 |
| P6 | Anthropomorphization of AI — "co-scientist" implies agency that does not exist | Terminology: "tool," not "co-scientist"; every output surfaces model provenance (`ModelCard`); `RiskTier` classification places human judgment above automated decisions | §I, §III-B-5 |
| P7 | Erasure of struggle — friction treated as pure negativity | Anti-deskilling design preserves learning friction; Mandatory Human Checkpoints are architectural hard stops; `SerendipityInjector` treats failures as productive | §II-D |
| P8 | No theory of justice in scientific AI | Apache 2.0 open-source core with `LICENSE-COMMERCIAL.md` for enterprise; open-core model keeps key capabilities free; `CarbonBudgetTracker` ensures ecological accountability | §VII |
| P9 | Political economy — value extraction from public scientific commons | Apache 2.0 + commercial license model; provenance export ensures FAIR compliance; all outputs exportable to open repositories (Zenodo, Figshare, OSF) | §VI |
| P10 | Violent hermeneutics — literature synthesis imposes interpretive grid | Non-English corpus bridges; `DataSovereigntyChecker` preserves indigenous knowledge restrictions; every synthesis carries reasoning trace showing how interpretation was constructed | §II-A-1, §II-D-1 |
| P11 | Algorithmic fossilization of method — simulated scientific method is verificationist | `FalsificationAgent` operationalizes Popperian falsification; `NegativeResultRegistry` archives falsifications; `VerificationAsymmetryTracker` prevents non-verifiable claims from being treated as evidence | §II-A-2 |
| P12 | No room for serendipity — pipeline model prevents accidental discovery | `SerendipityInjector` with user-configurable randomness level; cross-domain analogy engine; contradiction-driven exploration | §II-D-4 |
| P13 | Carbon ontology of AI — environmental externalities unaccounted | `CarbonBudgetTracker` with hard stop at configurable monthly limit; FLOPs→kWh→CO2e tracking per query; `ReproducibilityBundle` includes hardware profile | §II-B-4 |
| P14 | Epistemic colonialism — Global South structurally excluded | Non-English corpus bridges; `IndigenousKnowledgeProtector` implements CARE principles; multilingual embedding models; offline-capable for field science | §II-B-3, §III-D |
| P15 | Industrialization of scientific imagination | `SerendipityInjector` preserves generative ambiguity; cross-domain analogy; controlled randomness parameter; serendipity audit trail | §II-D-4 |
| P16 | Heidegger's Gestell — technology reduces nature to standing-reserve | Philosophy of Limits encoded in code (§II-C); hard boundaries on what system will/won't do; uncertainty disclosure surfaces the gap between tool and reality | §II-C |
| P17 | Transhumanist erasure of the scientist — human as bottleneck | Anti-deskilling design; Mandatory Human Checkpoints; Pedagogical Commitment; "assists, not replaces" as architectural principle | §II-D |

### From 03_structural_triad.md (Structural)

| # | Gap Description | OpenSciRe Mitigation | Source Section |
|---|---|---|---|
| S1 | Linear pipeline fallacy — waterfall architecture with no feedback loops | Cyclical/re-entrant architecture with explicit backflow channels (figure in §III-A); `FalsificationAgent` re-seeds `HypothesisGenerator`; `NegativeResultRegistry` informs `LiteratureReviewAgent` | §III-A |
| S2 | Missing zeroth stage — problem formation and anomaly detection | `LiteratureReviewAgent` with gap identification (Phase 6.3.5); `RelatedWorkAnalyzer` with contradiction clustering (Phase 7.5); `SerendipityInjector` with contradiction-driven exploration (Phase 7.2.2) | §III-A, §II-D-4 |
| S3 | Missing terminal stage — validation, replication, falsification | `FalsificationAgent` (Phase 6.4); `VerifiabilityAssessor` (Phase 7.4); `NegativeResultRegistry` (Phase 6.6); `ReproducibilityBundle` for replication support | §II-A-2, §II-A-4 |
| S4 | Orphaned Science Skills — no integration logic | `openscire-bio` integrated as foundational data layer; Zotero/Mendeley bridges handle reference management; `UnpaywallClient` for open-access content | §III-A, §IV |
| S5 | Product-driven rather than process-driven structure | Process-driven reference architecture derived from scientific workflow analysis; each component maps to a scientific activity (read, hypothesize, test, verify, publish) | §III-A |
| S6 | Absence of data/instrumentation layer | `DataSovereigntyChecker` for ingestion; provenance DAG for data tracking; `ReproducibilityBundle` for protocol capture; `ExperimentalDesignAdvisor` for protocol generation | §III-B-1, §III-C |
| S7 | Missing social/collaborative architecture | `ProvenanceGraph` supports multi-agent collaboration; `SupervisorAgent` with task queue manages distributed work; Phase 12 adds team server (deferred) | §III-B-1 |
| S8 | Enterprise/experimental structural chasm | Unified tier architecture with same codebase; SQLite→PostgreSQL scaling path; Phase 12 API server for team deployment | §III-C |
| S9 | Absence of meta-scientific/reflexive layer | `UncertaintyQuantifier`; `VerificationAsymmetryTracker`; `KnowledgeBoundaryFlagging`; `DataSovereigntyChecker` with bias markers; every output carries epistemic status | §II-A-5, §II-C |
| S10 | Missing negative result/null hypothesis architecture | `NegativeResultRegistry` (Phase 6.6) — structurally equal to literature index; `FalsificationAgent` auto-registers falsifications; no delete, only supersede | §II-A-4 |
| S11 | Temporal/project lifecycle gap | Project lifecycle coverage: grant support (Phase 7), IRB checkpoints (EthicsAgent), publication export (Phase 8 CLI), post-publication monitoring (RetractionMonitor) | §III-B-5 |
| S12 | Missing interdisciplinary translation structure | `SerendipityInjector` with cross-domain analogy; non-English corpus bridges; multilingual embedding models | §II-D-4 |
| S13 | Absence of ethical/governance structural layer | `EthicalFirewall` is cross-cutting (every layer, not a gate); `RiskTier` classification with differential speed governance; `DataSovereigntyChecker`; `IndigenousKnowledgeProtector` | §II-B |
| S14 | Structural erosion of human judgment checkpoints | Mandatory Human Checkpoint Nodes enforced at `SupervisorAgent` orchestration layer; workflows templated with checkpoint nodes; override requires signed provenance entry | §II-D-3 |
| S15 | Generalist-vs-specialist structural contradiction | Unified architecture with mode-shifting; `ModelProvider` interface hides backend complexity; `SupervisorAgent` routes tasks to appropriate specialist agents | §III-A |
| S16 | Missing material/embodied interface | Acknowledged limitation (§VIII) — wet lab integration out of scope; `ExperimentalDesignAdvisor` generates protocols but human executes them | §VIII |
| S17 | Citation/trust structure is non-cross-cutting | `Unified Provenance DAG` (Phase 1) tracks attribution across all operations; every component accepts and emits provenance entries; cross-cutting per §00_cross_cutting.md | §III-B-1 |
| S18 | Absence of public/commons structural exit | All outputs exportable to open repositories (Zenodo, Figshare, OSF); RO-Crate and W3C PROV export; Apache 2.0 license; `LICENSE-COMMERCIAL.md` for enterprise | §III-C |

### From 08_miscellaneous.md (Cross-Cutting)

| # | Gap Description | OpenSciRe Mitigation | Source Section |
|---|---|---|---|
| M1 | Patentability void for AI-generated discoveries | Provenance DAG provides legal chain-of-invention tracking; `ResearchChronologyEnforcer` establishes IP priority timestamps; human authorship attribution via signed checkpoint entries | §III-B-1 |
| M2 | Training data IP contamination | `DataSovereigntyChecker` classifies data by license type; `LiteratureReference` tracks source repository and retraction status; all outputs cite specific sources | §II-B-3 |
| M3 | Trade secret vs. open science contradiction | Open-core model: community edition is Apache 2.0; enterprise features (Phase 16) are proprietary; no structural enforcement of publication timelines (acknowledged limitation) | §VII |
| M4 | Attribution bankruptcy of AI synthesis | Provenance DAG tracks every agent contribution; human checkpoints produce signed attribution entries; Phase 8 CLI includes citation format generation | §III-B-1 |
| M5 | Unpublished data exposure risk | Local-first architecture: no data leaves user's machine unless they explicitly choose cloud/BYOK mode; `DataSovereigntyChecker` flags unpublished data for special handling | §III-D |
| M6 | Scientific espionage via prompt engineering | Local-only operation prevents server-side prompt collection; `EthicalFirewall` scans for DURC patterns but does not log user queries to any external service | §II-B-1, §III-D |
| M7 | Supply chain attack surface | `ReproducibilityBundle` includes dependency hashes; database bridges use certificate pinning; `LiteratureReference` includes retraction monitoring | §III-C, §III-B-1 |
| M8 | Data deletion guarantee absence | Local SQLite can be destroyed by user at any time; no cloud storage of user data; encrypted BYOK keys stored in OS keyring with verifiable deletion | §III-D |
| M9 | FDA/EMA regulatory chasm | Acknowledged limitation (§VIII) — system does not generate clinical decision support; `RiskTier` classification flags clinical hypotheses for mandatory human review | §VIII, §II-B-2 |
| M10 | Missing export control framework | `DataSovereigntyChecker` includes regional restriction markers; `RiskTier` classification for dual-use domains; export of non-verifiable claims is blocked | §II-B-2, §II-B-3 |
| M11 | No IRB integration | `EthicsAgent` (Phase 6.5) includes IRB verification step; `RiskTier` classification flags human-subjects research for mandatory checkpoint | §II-B-2 |
| M12 | No liability framework for AI malpractice | All outputs carry epistemic disclaimer (§II-C-1); human checkpoints ensure researcher retains ultimate responsibility; provenance DAG provides full audit trail | §II-C-1 |
| M13 | "Freemium cliff" for academic labs | Open-source core is fully functional for individual researchers and small labs (3–20 people); managed cloud is additional convenience, not required capability | §VII |
| M14 | Grant budget inflation | OpenSciRe runs on consumer hardware with local models; no mandatory cloud spending; `CarbonBudgetTracker` prevents compute inflation | §III-D, §II-B-4 |
| M15 | Maintenance funding crisis for open components | Open-core business model generates sustainable revenue (Phase 16); community version maintained indefinitely; grant-funded development for new features | §VII |
| M16 | PhD curriculum obsolescence | Pedagogical Commitment (§II-D) preserves methodological training; anti-deskilling design; outputs explain their own reasoning; Mandatory Human Checkpoints prevent full automation of research workflow | §II-D |
| M17 | Disappearance of methodological apprenticeship | Mandatory Human Checkpoint Nodes at judgment-critical junctures; `ExperimentalDesignAdvisor` surfaces methodological reasoning; progressive disclosure supports novice-to-expert transition | §II-D-3 |
| M18 | Scientific "barista" problem | System is designed to augment, not replace — every automated step has a reasoning trace; human checkpoints treat researcher as governor, not supervisor | §II-D |
| M19 | Non-coder scientist exclusion | Progressive disclosure interface (Phase 11 local web UI, Phase 10 Jupyter); CLI (Phase 8) for power users; all core functions accessible via chat interface | §II-D-2 |
| M20 | Visual impairment and disability gap | Acknowledged as deferred (§VIII); Phase 11 UI must comply with WCAG 2.2 AA; CLI is screen-reader accessible by design | §VIII |
| M21 | Field science offline requirement | All core components run offline; local-first architecture ensures no internet dependency for basic operation; sync-when-connected mode planned (deferred) | §III-D |
| M22 | Language barrier beyond translation | Non-English corpus bridges (CNKI, SciELO, AJOL, eLibrary.ru); multilingual embedding models; original-language alongside translation display | §II-A-1 |
| M23 | FAIR principles violation | All outputs exportable to FAIR-compliant formats (RO-Crate, W3C PROV, JSON-LD); provenance DAG ensures findability; Ed25519 signing ensures authenticity | §III-C |
| M24 | Lock-in to Google's API ecosystem | `ModelProvider` interface (Phase 2) is provider-agnostic; BYOK allows any OpenAI-compatible endpoint; local models require no API keys | §III-D |
| M25 | Incompatibility with existing scientific software | Zotero/Mendeley bridges for reference management; R/Julia/MATLAB integration (Track C); CLI generates outputs compatible with Jupyter, markdown, LaTeX | §III-A |
| M26 | Missing provenance standard | RO-Crate and W3C PROV export are core requirements (Phase 1.5.8); `ProvenanceExporter` generates standardized provenance containers | §III-B-1 |
| M27 | No independent certification body | Acknowledged limitation (§VIII); system exposes its own epistemic status transparently so third-party auditors can verify claims | §VIII |
| M28 | Missing "recall" mechanism | Provenance DAG enables querying all outputs by version; `RetractionMonitor` provides citation chain invalidation; `NegativeResultRegistry` preserves records of failed approaches | §III-B-1 |
| M29 | No liability framework for research harm | Acknowledged limitation (§VIII); provenance DAG provides audit trail for post-hoc analysis of research decisions | §VIII |
| M30 | Science communication distortion pipeline | All outputs include mandatory uncertainty display; knowledge boundary flagging prevents overconfident summaries; no auto-generated public-facing summaries without human review | §II-C-3 |
| M31 | Democratic deficit in AI science governance | Acknowledged limitation (§VIII); open-source model allows community governance structures; AGENTS.md establishes fiduciary tone | §VIII |
| M32 | Erosion of public trust | Epistemic honesty as architectural principle: uncertainty displayed, limits communicated, provenance open; all code is Apache 2.0 for public scrutiny | §II-C |
| M33 | Scientific neo-colonialism through cloud dependency | Local-first architecture; non-English corpus bridges; `IndigenousKnowledgeProtector`; export control markers | §III-D, §II-B |
| M34 | Brain drain acceleration | Local-only mode ensures research data stays on researcher's machine; BYOK prevents data from flowing through OpenSciRe's infrastructure | §III-D |
| M35 | Cold War dynamics in scientific AI | Acknowledged limitation (§VIII); open-source model permits sovereign hosting and national mirror infrastructure | §VIII |
| M36 | Research agenda homogenization | `SerendipityInjector` with configurable novelty parameter; `FalsificationAgent` actively seeks divergent evidence; non-English corpus bridges inject plural perspectives | §II-D-4 |
| M37 | Catastrophic discovery acceleration | Differential speed governance (RiskTier): Tier 1 has mandatory 24-hour cooling-off period; `VerificationAsymmetryTracker` blocks non-verifiable claims; `EthicalFirewall` for DURC detection | §II-B-2 |
| M38 | Scientific system fragility | Local-first prevents single-point-of-failure; open-source permits community maintenance; `ReproducibilityBundle` preserves environment for re-execution | §III-C, §III-D |
| M39 | Automation bias and complacency | Mandatory Human Checkpoints; `UncertaintyQuantifier` surfaces low-confidence claims; `FalsificationAgent` actively contradicts user expectations | §II-D-3, §II-A-5 |
| M40 | Decision fatigue from option overload | Progressive disclosure; tiered decision trees; `SerendipityInjector` with configurable level (not always at maximum); hypothesis prioritization scoring | §II-D-2 |
| M41 | Moral crumple zone | All outputs carry epistemic disclaimer; provenance DAG attributes every claim to its source agent; human checkpoints distribute responsibility | §II-C-1 |
| M42 | Sunk cost fallacy at scale | Open-core model reduces switching cost to zero for most features; data export in standard formats (RO-Crate, JSON, CSV) prevents vendor lock-in | §VII |
| M43 | AI-enabled HARKing | `ResearchChronologyEnforcer` (Phase 1.5.10) cryptographically timestamps hypotheses before evidence is synthesized; temporal ordering violations are detected and flagged | §III-B-1 |
| M44 | Automated salami slicing | `RelatedWorkAnalyzer` with redundancy flagging (Phase 7.5); `FalsificationAgent` checks if new hypotheses are trivially different from existing ones | §III-A |
| M45 | Deepfake data generation | `SyntheticDataWatermarking` (Phase 7.6) cryptographically watermarks all generated synthetic datasets; anti-leak warning on export | §III-A |
| M46 | Citation cartel amplification | `DataSovereigntyChecker` flags prestige-biased sources; `LiteratureReference` includes citation count with institutional diversity index; `LiteratureReviewAgent` manually weights diverse sources | §II-A-1 |
| M47 | E-waste from hardware obsolescence | Local models run on existing consumer hardware; no mandatory GPU upgrades; `CarbonBudgetTracker` encourages efficient compute use | §III-D |
| M48 | Water and energy colonialism | `CarbonBudgetTracker` with regional grid intensity factors; local-first reduces data center water consumption; hard stop at budget limits | §II-B-4 |
| M49 | Carbon colonialism of AI training | `CarbonBudgetTracker` surfaces carbon costs per query; local-first shifts compute to user-controlled hardware; acknowledged: training footprint is inherited from model providers | §II-B-4 |
| M50 | Missing "Hippocratic Oath" for AI science developers | Ethics-in-code architecture (§II-B-5): `EthicalFirewall`, `CarbonBudgetTracker`, `VerificationAsymmetryTracker`, `DataSovereigntyChecker` — ethics is compiled into the binary | §II-B-5 |
| M51 | Absence of deliberative democracy in tool design | Acknowledged limitation (§VIII); open-source permits community-fork governance; `CONTRIBUTING.md` and `ISSUE_TEMPLATE/` provide community input channels | §VIII |
| M52 | Lack of "slow science" mode | Mandatory Human Checkpoints impose reflection pauses; architecture has built-in friction at judgment-critical points; `RiskTier` classification slows high-risk workflows | §II-B-2 |
| M53 | No graceful degradation for catastrophic failure | Local-first architecture means user is never dependent on a remote server; `ReproducibilityBundle` ensures workflow can be replayed on different infrastructure | §III-C |
| M54 | Ultimate human override absence | Mandatory Human Checkpoint Nodes (architectural hard stops, not optional UI); human override logged in provenance DAG; `SupervisorAgent` state machine includes `waiting_for_human` state | §II-D-3 |
| M55 | System has no theory of its own limits | Philosophy of Limits (§II-C) is encoded in architecture: `KnowledgeBoundaryFlagging`, `VerificationAsymmetryTracker`, `UncertaintyQuantifier`, hard boundaries on system scope | §II-C |

### Cross-Cutting Meta-Gaps

| Meta-Gap | Description | OpenSciRe Mitigation |
|----------|-------------|---------------------|
| **Absence of Philosophy of Limits** | Both Google and naive open-source assume more is better. Neither has a theory of when *not* to discover, when *not* to optimize. | §II-C: `KnowledgeBoundaryFlagging`, `VerificationAsymmetryTracker`, `EthicalFirewall`, `CarbonBudgetTracker` with hard stop, `RiskTier` classification with differential speed governance, hard boundaries on what system will not do. The system can say "no," "not yet," and "this is beyond me" — architecturally, not just as a UI message. |
| **Confusion of Scale with Depth** | Both confuse horizontal expansion (more papers, more agents, more users) with vertical depth (better understanding, truer insight, wiser judgment). | §III-B-1: Provenance DAG requires depth — every operation traces back to its inputs, parameters, and signer. §II-D: `Pedagogical Commitment` ensures outputs explain reasoning, not just results. §II-C: `VerificationAsymmetryTracker` categorizes claims by verifiability depth, not count. Quality over quantity is enforced at the framework level. |
| **Substitution of Process for Wisdom** | Both offer processes (multi-agent debate, community audit, parallel computation) as substitutes for wisdom (*phronesis*). | §II-D-3: Mandatory Human Checkpoints treat judgment as a feature, not a bottleneck. §II-C-1: Hard boundaries acknowledge that some questions require human wisdom AI cannot provide. §II-D-2: Anti-deskilling design ensures the researcher exercises judgment at every critical step. The system surfaces epistemic status; the human exercises wisdom. |

---

## VI. Development Roadmap

The following maps how this proposal connects to the existing phase documents in `docs/phases/`.

| Proposal Component | Phase(s) | Current Status | Key Milestones |
|--------------------|----------|----------------|----------------|
| Repo setup, package scaffolding | Phase 0 | **DONE** | Package structure, pyproject.toml, pre-commit, Cargo workspace |
| Core Pydantic models | Phase 1 | **Planned (Jul 2026)** | `ScientificClaim`, `Evidence`, `Hypothesis`, `ProvenanceEntry`, `LiteratureReference`, `ResearchContext`, `ReproducibilityBundle` |
| ProvenanceTracker (DAG) | Phase 1 | **Planned** | Ed25519 signing, entry chaining, DAG traversal, RO-Crate export, `ResearchChronologyEnforcer` |
| Config module | Phase 1 | **Planned** | YAML/TOML parser, env overrides, `Config.to_reproducibility_bundle()`, secret redaction |
| Logging module | Phase 1 | **Planned** | Structured JSON logging, SCIENCE log level, provenance-aware entries |
| Exceptions module | Phase 1 | **Planned** | `openSciReError` hierarchy with error codes |
| Serialization module | Phase 1 | **Planned** | JSON, YAML, MessagePack, versioned formats |
| Model Provider Interface | Phase 2 | **Planned (Jul 2026)** | Abstract provider, OpenAI-compatible, Anthropic, Gemini adapters, fallback cascade, BYOK config, feature detection, LiteLLM integration |
| **Ethical Firewall** | Phase 3 | **Planned (Aug 2026)** | DURC detection, Risk Tier classification, DataSovereigntyChecker, IndigenousKnowledgeProtector, CarbonBudgetTracker, UncertaintyQuantifier, SourceGrounding, VerificationAsymmetryTracker |
| Literature Engine | Phase 4 | **Planned (Aug–Sep 2026)** | Zotero/Mendeley bridges, PubMed/arXiv/Semantic Scholar/OpenAlex clients, non-English corpus bridges, RetractionMonitor, PDF parser, EmbeddingIndex, CitationGraphAnalyzer |
| RAG pipeline | Phase 5 | **Planned (Sep 2026)** | Retrieval-augmented generation for literature synthesis |
| **Multi-Agent Framework** | Phase 6 | **Planned (Oct–Nov 2026)** | SupervisorAgent, LiteratureReviewAgent, FalsificationAgent, EthicsAgent, NegativeResultRegistry, AgentBus communication protocol |
| **Hypothesis Generation** | Phase 7 | **Planned (Nov–Dec 2026)** | HypothesisGenerator, SerendipityInjector, ExperimentalDesignAdvisor, VerifiabilityAssessor, RelatedWorkAnalyzer, SyntheticDataWatermarker |
| CLI | Phase 8 | **Planned** | Command-line interface for all operations |
| Sandbox (design + stubs) | Phase 9 | **Planned (Jul 2026, parallel)** | Design doc, threat model, API contract, Cargo stubs — implementation deferred |
| Jupyter extension | Phase 10 | **Planned** | Jupyter widget integration |
| Local web UI | Phase 11 | **Planned** | React frontend (desktop app via Tauri) |
| API server (team) | Phase 12 | **Planned** | PostgreSQL backend, multi-tenant support, SSO, audit logs |
| Academic pilot | Phase 13 | **Planned** | Pilot with target audience labs |
| Distribution | Phase 14 | **Planned** | PyPI + npm + Docker |
| Community launch | Phase 15 | **Planned** | Public launch, community outreach |
| Monetization | Phase 16 | **Planned** | Open-core: free local + paid managed cloud + enterprise features |
| YC application | Phase 17 | **Planned** | YC batch application |
| Post-YC scale | Phase 18 | **Planned** | Team hiring, product-market fit iteration |

### openscire-philosophy Instantiation Schedule

The philosophy layer is not a separate phase — it is instantiated as components are built:

| Philosophy Component | Phase of Instantiation | Implementation |
|----------------------|----------------------|----------------|
| Situated knowledges | Phase 4 (literature bridges) + Phase 3.3 (DataSovereignty) | Non-English corpus bridges; origin classification metadata |
| Falsification-first | Phase 6.4 (FalsificationAgent) + Phase 3.8 (VerificationAsymmetry) | Popperian falsification as first-class agent; claim categorization |
| Knowing-that vs. knowing-how | Phase 6.2 (SupervisorAgent checkpoints) + Phase 7.3 (ExperimentalDesign) | Mandatory Human Checkpoints; judgment-preserving design |
| Negative knowledge | Phase 6.6 (NegativeResultRegistry) | Structurally equal to literature index; auto-registration on falsification |
| Uncertainty as requirement | Phase 3.6 (UncertaintyQuantifier) | Mandatory confidence display; knowledge boundary flagging |
| Philosophy of Limits | Phase 3.1 (EthicalFirewall) + Phase 3.2 (RiskTier) + Phase 3.8 | Hard boundaries; differential speed governance; non-verifiable claim blocking |
| Pedagogical Commitment | Cross-cutting from Phase 1 onward | Reasoning traces on all outputs; progressive disclosure |

---

## VII. Strategic Context

### How This Differs from Google's Gemini for Science

The central competitive distinction is not technical capability — it is **epistemic architecture**.

| Dimension | Google Gemini for Science | OpenSciRe |
|-----------|--------------------------|-----------|
| **Architecture** | Linear stage-gate (Read → Hypothesize → Test) | Cyclical/re-entrant with explicit backflow channels |
| **Epistemology** | Correspondence theory of truth; verificationist | Popperian falsification; situated knowledges; uncertainty-first |
| **Ethics** | External overlay (human reviewers, institutional partners) | Cross-cutting ethical mesh in every layer; DURC detection, carbon budget, sovereignty checks |
| **Data** | Cloud-locked; proprietary formats; no provenance standard | Local-first; RO-Crate/W3C PROV export; Ed25519-signed provenance DAG |
| **Model Access** | Google Cloud APIs only | Ollama, vLLM, llama.cpp, LM Studio, BYOK (OpenAI/Anthropic/Gemini), LiteLLM |
| **Limits** | None articulated | Hard boundaries; knowledge boundary flagging; non-verifiable claim blocking |
| **Business Model** | Proprietary cloud; enterprise contracts; data harvesting for model training | Open-core (Apache 2.0); managed cloud is convenience, not gate; BYOK prevents data harvesting |
| **Target User** | Enterprise R&D (BASF, Bayer, U.S. National Labs) | Individual researchers and small labs (3–20 people) — the "missing middle" |
| **Serendipity** | None — pipeline model prevents accidental discovery | `SerendipityInjector` with controlled randomness; cross-domain analogy |
| **Negative Results** | Structurally invisible — low scores disappear | `NegativeResultRegistry` is a first-class citizen; falsifications auto-registered |
| **Reproducibility** | Not architecturally addressed | `ReproducibilityBundle` for every research run; deterministic execution in sandbox |
| **Human Role** | User of automated pipeline | Governor of research workflow; Mandatory Human Checkpoints at judgment-critical junctures |

### Economic Role in the Business Model

OpenSciRe follows the **open-core** model (as described in `docs/business-brief.md`), which is the most common and proven YC monetization path for developer tools:

| Tier | Price | What You Get |
|------|-------|--------------|
| **Open Source** | Free (Apache 2.0) | Full local functionality: literature engine, hypothesis generation, falsification, sandbox, all core data models, provenance DAG. Community support via GitHub Issues/Discussions. |
| **Pro (Managed)** | ~$20/mo | Managed cloud hosting (optional — retains full local free tier); BYOK for cloud models; sync across devices; priority support via dedicated channel. |
| **Team** | ~$50/seat/mo | Shared provenance graphs across lab; PostgreSQL backend; role-based access; audit logs; SSO; collaborative hypothesis spaces. |
| **Enterprise** | Custom | On-premise deployment; custom model adapters; SLA guarantees; dedicated support; training; compliance documentation (HIPAA, ITAR, GDPR). |

**Why this works**: The open-source core builds trust and adoption (land). The managed cloud and team tiers generate revenue (expand). Profit is made on **infrastructure convenience and governance**, not on gating scientific capability. Every feature that is critical to science (provenance, falsification, ethics, uncertainty) is in the free tier.

### Target Users

1. **Primary**: Individual researchers and small labs (3–20 people) in life sciences and computational sciences — the "missing middle" that Google Cloud ignores. These groups need powerful scientific AI tools but cannot afford enterprise contracts or are institutionally restricted from using cloud APIs for sensitive research.

2. **Secondary**: Graduate students and postdocs who need literature review, hypothesis generation, and computational prototyping without enterprise budgets. The local-first design is critical here — a graduate student with a laptop and Ollama has the same epistemic capabilities as a well-funded lab.

3. **Tertiary (revenue)**: R&D teams at mid-size biotechs, CROs, and research institutes needing BYOK, auditable, on-premise scientific AI. These are the Team and Enterprise tier customers.

### Why This Exists Now

1. **Post-Gemini-for-Science I/O 2026**: Google's announcement made visible what structural crises had been building for years — the privatization of the scientific commons, the verificationist bias, the erasure of human judgment. The critiques were necessary; OpenSciRe is the constructive response.

2. **Local LLM inference is commodity hardware territory**: Ollama, vLLM, and llama.cpp have made it possible to run capable models on consumer hardware. The cloud dependency that Google used to justify its architectural choices is no longer a technical necessity — it is a business decision that OpenSciRe cannot accept.

3. **Cloud trust is eroding**: Research institutions increasingly recognize the risks of centralizing scientific infrastructure in a single corporate cloud — data exposure, IP contamination, vendor lock-in, geopolitical dependencies. The window for a credible local-first alternative is open and will not remain open indefinitely.

4. **The reproducibility crisis**: Science's inability to reproduce its own results is structural, not methodological. OpenSciRe's provenance DAG, `ReproducibilityBundle`, and `NegativeResultRegistry` are architectural responses to a crisis that no pipeline-AI tool has addressed.

5. **The funding gap**: The "missing middle" of academic labs (3–20 people) generates disproportionate scientific output but is structurally excluded from enterprise AI tools. OpenSciRe's open-core model targets this exact gap.

---

## VIII. Limitations Acknowledged

OpenSciRe knowingly does NOT address the following. These are structural limitations that we explicitly name rather than pretend to solve:

1. **Full clinical/phenotypic integration** (deferred): Integration with electronic health records, clinical trial management systems, and patient-level phenotypic data is deferred. These require HIPAA-compliant infrastructure, regulatory certification, and domain expertise beyond the current scope. The architecture is designed to accommodate this in a future version, but it is not part of the Phase 1–18 roadmap.

2. **Multi-omics integration** (deferred): Simultaneous analysis of genomics, transcriptomics, proteomics, metabolomics, and other -omics data is not structurally supported in the MVP. Individual omics types can be analyzed through the literature engine and sandbox, but the integrated multi-omics pipeline is deferred.

3. **Collaborative/team architecture** (Phase 12): Multi-user workspaces, shared provenance graphs, role-based access, and team-wide research agendas are planned for Phase 12 but are not part of the initial architecture. The single-user local-first experience is the focus through Phase 11.

4. **Wet lab integration** (out of scope): Direct control of laboratory equipment, real-time sensor ingestion, and physical experiment monitoring are out of scope for OpenSciRe. The system supports experimental design and protocol generation, but execution remains the human researcher's responsibility.

5. **PhD curriculum obsolescence** (acknowledged, not architecturally addressed): The pedagogical commitment (§II-D) mitigates deskilling, but OpenSciRe cannot solve the structural problem of how PhD programs should adapt to AI tools. This is a policy and institutional question that software cannot resolve.

6. **Democratic deficit in AI governance** (acknowledged): The open-source model permits community governance, but OpenSciRe does not include citizen assemblies, deliberative democracy mechanisms, or participatory design processes. These are political, not architectural, challenges.

7. **Independent certification body** (acknowledged): There is currently no independent body that certifies scientific AI tools. OpenSciRe exposes its epistemic status transparently (uncertainty, provenance, verification asymmetry) to enable third-party auditing, but certification requires an institution that does not yet exist.

8. **Liability framework** (acknowledged): The provenance DAG provides full audit trails, but legal liability for AI-assisted research harm remains undefined. OpenSciRe cannot create an insurance product or professional liability framework.

9. **Geopolitical tensions** (acknowledged): OpenSciRe's open-source model permits sovereign hosting, but it cannot resolve the structural tensions between international scientific collaboration and geopolitical competition. A neutral-zone architecture would require international governance mechanisms beyond software design.

10. **E-waste from model hardware** (acknowledged): OpenSciRe runs on consumer hardware and does not mandate upgrades, but the broader ecosystem of local LLM inference drives GPU/TPU acquisition cycles. The `CarbonBudgetTracker` encourages responsible compute use, but e-waste remains a systemic issue.

11. **Model training carbon footprint** (acknowledged): OpenSciRe does not train foundation models. The carbon footprint of training (which occurs at inference providers) is not directly under OpenSciRe's control. The `CarbonBudgetTracker` surfaces inference costs but cannot mitigate training costs.

12. **Accessibility beyond CLI** (deferred): WCAG 2.2 AA compliance for the web UI is a Phase 11 requirement. The CLI is inherently screen-reader accessible, but full accessibility (sonification, haptic feedback, tactile interfaces) is deferred.

---

*This document is a living North Star. As components are built and the ecosystem evolves, it should be updated to reflect architectural decisions, new gaps identified, and lessons learned. The gap closure matrix (§V) in particular should be revisited with each phase completion to ensure that epistemic honesty remains the system's first architectural principle — not a design goal, but a compiled constraint.*

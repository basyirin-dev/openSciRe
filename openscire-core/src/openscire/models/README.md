# openSciRe — Models

Purpose: Core and philosophy-grounded Pydantic data models representing scientific claims, evidence,
hypotheses, provenance entries, reproducibility bundles, and epistemic boundary markers.

Status: Stable

Public API:

- `ScientificClaim` — Core domain model: a scientific claim with evidence, status, provenance, and
  epistemic markers
- `Evidence` — Supporting evidence for a claim (type, source, content hash, confidence)
- `EvidenceType` — Enum: theoretical, empirical, computational, anecdotal, meta
- `Hypothesis` — Testable hypothesis with status tracking, falsifiability config, and agent
  diversity requirements
- `HypothesisStatus` — Enum: proposed, in_review, active, rejected, confirmed, retracted
- `LiteratureReference` — Citation/reference with DOI/URL/arXiv, Zotero key, and quoted excerpt
- `ProvenanceEntry` — Signed entry recording which agent produced what, when, and how
- `ReproducibilityBundle` — Container for reproducibility artifacts (config snapshots, code hash,
  container image ref)
- `ReproducibilityStatus` — Enum: unknown, reproducible, partially_reproducible, not_reproducible
- `ResearchContext` — Epistemic context for any research entity (knowledge boundaries, active
  hypotheses, boundary flags)
- `VerificationStatus` — Enum: unverified, verified, contradictory, inconclusive
- `KnowledgeBoundaryFlag` — A boundary category paired with explanatory text
- `EpistemicMarker` — Structured marker indicating the epistemic status and known limitations of a
  generated entity
- `FalsificationConfig` — Popperian falsifiability parameters for a hypothesis generator agent
- `AgentDiversityConfig` — Configuration for ensuring epistemological diversity across agents
- `AgentModelProvider` — Specifies a model/provider combination for an agent
- `AgentTemperatureConfig` — Temperature/creativity parameters for a specific agent
- `BoundaryCategory` — Enum: temporal, methodological, domain, computational, epistemic
- `SourceCategory` — Enum: primary_literature, secondary_literature, database, experimental,
  synthetic

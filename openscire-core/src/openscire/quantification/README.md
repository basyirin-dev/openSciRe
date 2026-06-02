# openSciRe — Quantification

Purpose: Quantitative uncertainty and contradiction analysis for LLM-generated research content — confidence calibration, contradiction detection across claims, and epistemic boundary tracking.

Status: Stable (Phase 3)

Public API:
- `UncertaintyQuantifier` — Evaluates confidence levels of individual claims and overall response consistency, including contradiction-aware confidence calibration
- `ContradictionDetector` — Detects logical contradictions between pairs of claims using semantic similarity and negation detection
- `KnowledgeBoundaryFlag` — Model for epistemic boundary conditions (confidence, contradiction count, calibration status)

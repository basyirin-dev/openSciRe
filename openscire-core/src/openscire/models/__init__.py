# SPDX-License-Identifier: Apache-2.0

"""Core domain models for openSciRe.

Defines the primary data types: scientific claims, hypotheses, evidence,
provenance entries, reproducibility bundles, and epistemic boundary markers.
"""

from openscire.models.models import (
    Evidence,
    EvidenceType,
    Hypothesis,
    HypothesisStatus,
    LiteratureReference,
    ProvenanceEntry,
    ReproducibilityBundle,
    ReproducibilityStatus,
    ResearchContext,
    ScientificClaim,
    VerificationStatus,
)
from openscire.models.philosophy import (
    AgentDiversityConfig,
    AgentModelProvider,
    AgentTemperatureConfig,
    BoundaryCategory,
    EpistemicMarker,
    FalsificationConfig,
    KnowledgeBoundaryFlag,
    SourceCategory,
)

__all__ = [
    "ScientificClaim",
    "Evidence",
    "Hypothesis",
    "ProvenanceEntry",
    "LiteratureReference",
    "ResearchContext",
    "ReproducibilityBundle",
    "VerificationStatus",
    "EvidenceType",
    "ReproducibilityStatus",
    "HypothesisStatus",
    "KnowledgeBoundaryFlag",
    "EpistemicMarker",
    "FalsificationConfig",
    "AgentDiversityConfig",
    "AgentModelProvider",
    "AgentTemperatureConfig",
    "BoundaryCategory",
    "SourceCategory",
]

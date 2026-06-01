# SPDX-License-Identifier: Apache-2.0

import uuid

import pytest
from openscire.models import (
    BoundaryCategory,
    EpistemicMarker,
    Evidence,
    EvidenceType,
    Hypothesis,
    HypothesisStatus,
    KnowledgeBoundaryFlag,
    LiteratureReference,
    ProvenanceEntry,
    ReproducibilityBundle,
    ReproducibilityStatus,
    ResearchContext,
    ScientificClaim,
    SourceCategory,
    VerificationStatus,
)


@pytest.fixture
def sample_claim() -> ScientificClaim:
    return ScientificClaim(
        field="biology",
        evidence_chain=["e1", "e2"],
        confidence_interval=(0.1, 0.5),
        source_references=["doi:10.1234/abc"],
        verification_status=VerificationStatus.supported,
        created_by="test_agent",
    )


@pytest.fixture
def sample_evidence() -> Evidence:
    return Evidence(
        type=EvidenceType.experimental,
        source="lab notebook",
        strength_rating=0.85,
        reproducibility_status=ReproducibilityStatus.reproduced,
    )


@pytest.fixture
def sample_hypothesis() -> Hypothesis:
    return Hypothesis(
        claim="Gene X regulates pathway Y",
        null_hypothesis="Gene X has no effect on pathway Y",
        falsification_criteria=["p < 0.05", "n >= 3"],
        testability_score=0.9,
        domain_tags=["genetics", "molecular_biology"],
        related_literature=["doi:10.1234/abc"],
        status=HypothesisStatus.proposed,
    )


@pytest.fixture
def sample_entry() -> ProvenanceEntry:
    return ProvenanceEntry(
        action_id=str(uuid.uuid4()),
        action_type="literature_review",
        parent_ids=[],
        agent_id="test_agent",
        model_id="llama3.1",
        parameters_snapshot={"temperature": 0.7, "max_tokens": 1024},
        input_hash="abc123",
        output_hash="def456",
    )


@pytest.fixture
def sample_lit_ref() -> LiteratureReference:
    return LiteratureReference(
        doi="10.1234/xyz789",
        title="A Test Paper",
        authors=["Alice", "Bob"],
        journal="Journal of Test Studies",
        year=2024,
        citation_count=42,
        retraction_status="none",
        source_repository="PubMed",
        full_text_hash="feedface",
    )


@pytest.fixture
def sample_context() -> ResearchContext:
    return ResearchContext(
        research_question="Does gene X regulate pathway Y?",
        domain="molecular_biology",
        hypotheses_in_scope=["hyp_001"],
        literature_seed=["doi:10.1234/abc"],
        constraints=["budget < $10k"],
        ethical_flags=[],
        project_id="proj_001",
    )


@pytest.fixture
def sample_bundle() -> ReproducibilityBundle:
    return ReproducibilityBundle(
        environment_lockfile="# pip freeze output",
        dependency_tree={"pydantic": "2.9.0", "pynacl": "1.6.0"},
        config_snapshot={"model": {"provider": "ollama"}},
        random_seeds={"numpy": 42, "python": 123},
        data_hashes={"input.csv": "sha256:abc"},
        hardware_profile="python=3.12; system=Linux; cpu_count=8",
    )


@pytest.fixture
def sample_kbf() -> KnowledgeBoundaryFlag:
    return KnowledgeBoundaryFlag(
        category=BoundaryCategory.outside_corpus,
        query="What is the cure for aging?",
        confidence=0.05,
        threshold=0.3,
        detail="No papers found in corpus.",
    )


@pytest.fixture
def sample_em() -> EpistemicMarker:
    return EpistemicMarker(
        source_category=SourceCategory.public,
        source_type="literature_review",
        method="RAG synthesis",
        confidence=0.85,
        caveats=["English-language bias"],
        corpus_bias={"dominant_language": "en"},
        source_language="en",
    )


@pytest.fixture
def reset_provenance() -> None:
    from openscire.provenance import ProvenanceTracker

    ProvenanceTracker.reset()
    yield
    ProvenanceTracker.reset()

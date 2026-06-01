# SPDX-License-Identifier: Apache-2.0

from datetime import datetime

from openscire.models import (
    AgentDiversityConfig,
    AgentModelProvider,
    AgentTemperatureConfig,
    BoundaryCategory,
    EpistemicMarker,
    Evidence,
    EvidenceType,
    FalsificationConfig,
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


class TestStrEnums:
    def test_verification_status_values(self) -> None:
        assert VerificationStatus.unverified.value == "unverified"
        assert VerificationStatus.supported.value == "supported"
        assert VerificationStatus.contradicted.value == "contradicted"
        assert VerificationStatus.inconclusive.value == "inconclusive"
        assert VerificationStatus.retracted.value == "retracted"

    def test_evidence_type_values(self) -> None:
        assert EvidenceType.experimental.value == "experimental"
        assert EvidenceType.computational.value == "computational"
        assert EvidenceType.literature.value == "literature"
        assert EvidenceType.anecdotal.value == "anecdotal"

    def test_hypothesis_status_values(self) -> None:
        assert HypothesisStatus.proposed.value == "proposed"
        assert HypothesisStatus.tested.value == "tested"
        assert HypothesisStatus.supported.value == "supported"
        assert HypothesisStatus.refuted.value == "refuted"

    def test_reproducibility_status_values(self) -> None:
        assert ReproducibilityStatus.not_assessed.value == "not_assessed"

    def test_boundary_category_values(self) -> None:
        assert BoundaryCategory.outside_corpus.value == "outside_corpus"

    def test_source_category_values(self) -> None:
        assert SourceCategory.indigenous.value == "indigenous"


class TestScientificClaim:
    def test_defaults(self) -> None:
        c = ScientificClaim(field="physics")
        assert c.verification_status == VerificationStatus.unverified
        assert c.evidence_chain == []
        assert c.confidence_interval is None

    def test_serialization_round_trip(self, sample_claim: ScientificClaim) -> None:
        d = sample_claim.model_dump(mode="json")
        restored = ScientificClaim.model_validate(d)
        assert restored.field == sample_claim.field
        assert restored.verification_status == sample_claim.verification_status


class TestEvidence:
    def test_defaults(self) -> None:
        e = Evidence(type=EvidenceType.computational, source="simulation")
        assert e.reproducibility_status == ReproducibilityStatus.not_assessed
        assert e.strength_rating is None

    def test_serialization_round_trip(self, sample_evidence: Evidence) -> None:
        d = sample_evidence.model_dump(mode="json")
        restored = Evidence.model_validate(d)
        assert restored.type == sample_evidence.type


class TestHypothesis:
    def test_defaults(self) -> None:
        h = Hypothesis(claim="test")
        assert h.status == HypothesisStatus.proposed
        assert h.null_hypothesis is None

    def test_serialization_round_trip(self, sample_hypothesis: Hypothesis) -> None:
        d = sample_hypothesis.model_dump(mode="json")
        restored = Hypothesis.model_validate(d)
        assert restored.claim == sample_hypothesis.claim


class TestProvenanceEntry:
    def test_defaults(self) -> None:
        e = ProvenanceEntry(action_id="a1")
        assert e.parent_ids == []
        assert e.cryptographic_signature is None

    def test_serialization_round_trip(self, sample_entry: ProvenanceEntry) -> None:
        d = sample_entry.model_dump(mode="json")
        restored = ProvenanceEntry.model_validate(d)
        assert restored.action_id == sample_entry.action_id


class TestLiteratureReference:
    def test_defaults(self) -> None:
        r = LiteratureReference()
        assert r.doi == ""
        assert r.full_text_hash is None

    def test_serialization_round_trip(self, sample_lit_ref: LiteratureReference) -> None:
        d = sample_lit_ref.model_dump(mode="json")
        restored = LiteratureReference.model_validate(d)
        assert restored.doi == sample_lit_ref.doi


class TestResearchContext:
    def test_defaults(self) -> None:
        c = ResearchContext()
        assert c.research_question == ""

    def test_serialization_round_trip(self, sample_context: ResearchContext) -> None:
        d = sample_context.model_dump(mode="json")
        restored = ResearchContext.model_validate(d)
        assert restored.project_id == sample_context.project_id


class TestReproducibilityBundle:
    def test_defaults(self) -> None:
        b = ReproducibilityBundle()
        assert b.dependency_tree == {}

    def test_serialization_round_trip(self, sample_bundle: ReproducibilityBundle) -> None:
        d = sample_bundle.model_dump(mode="json")
        restored = ReproducibilityBundle.model_validate(d)
        assert restored.hardware_profile == sample_bundle.hardware_profile


class TestKnowledgeBoundaryFlag:
    def test_defaults(self, sample_kbf: KnowledgeBoundaryFlag) -> None:
        assert sample_kbf.requires_human_override is True
        assert sample_kbf.override_entry_id is None

    def test_serialization_round_trip(self, sample_kbf: KnowledgeBoundaryFlag) -> None:
        d = sample_kbf.model_dump(mode="json")
        restored = KnowledgeBoundaryFlag.model_validate(d)
        assert restored.category == sample_kbf.category


class TestEpistemicMarker:
    def test_defaults(self, sample_em: EpistemicMarker) -> None:
        assert sample_em.funding_source is None
        assert sample_em.provenance_entry_id is None

    def test_serialization_round_trip(self, sample_em: EpistemicMarker) -> None:
        d = sample_em.model_dump(mode="json")
        restored = EpistemicMarker.model_validate(d)
        assert restored.source_category == sample_em.source_category


class TestFalsificationConfig:
    def test_defaults(self) -> None:
        fc = FalsificationConfig()
        assert fc.enabled is True
        assert fc.promote_to_not_falsified is True
        assert fc.max_falsification_attempts == 3

    def test_serialization_round_trip(self) -> None:
        fc = FalsificationConfig()
        d = fc.model_dump(mode="json")
        restored = FalsificationConfig.model_validate(d)
        assert restored.enabled == fc.enabled

    def test_field_constraints(self) -> None:
        fc = FalsificationConfig(max_falsification_attempts=10)
        assert fc.max_falsification_attempts == 10


class TestAgentDiversityConfig:
    def test_defaults(self) -> None:
        adc = AgentDiversityConfig()
        assert adc.serendipity_level == 0.4
        assert len(adc.providers) == 3

    def test_temperature_defaults(self) -> None:
        atc = AgentTemperatureConfig()
        assert atc.literature_review == 0.2
        assert atc.hypothesis_generation == 0.9

    def test_provider_construction(self) -> None:
        p = AgentModelProvider(role="test", provider="ollama", model_name="llama3.1")
        assert p.temperature is None
        assert p.tool_access == []

    def test_serialization_round_trip(self) -> None:
        adc = AgentDiversityConfig()
        d = adc.model_dump(mode="json")
        restored = AgentDiversityConfig.model_validate(d)
        assert restored.serendipity_level == adc.serendipity_level


class TestTimestamps:
    def test_models_have_timestamps(
        self,
        sample_claim: ScientificClaim,
        sample_entry: ProvenanceEntry,
        sample_kbf: KnowledgeBoundaryFlag,
    ) -> None:
        assert isinstance(sample_claim.timestamp, datetime)
        assert isinstance(sample_entry.timestamp, datetime)
        assert isinstance(sample_kbf.created_at, datetime)

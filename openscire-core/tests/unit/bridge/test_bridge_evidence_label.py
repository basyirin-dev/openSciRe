from openscire.bridge.evidence_label import (
    EvidencePropagator,
    EvidenceTagged,
    EvidenceTypeLabel,
)


class TestEvidenceTypeLabel:
    def test_hierarchy_reviewed_trumps_experimental(self) -> None:
        result = EvidencePropagator.combine(
            [EvidenceTypeLabel.EXPERIMENTAL, EvidenceTypeLabel.REVIEWED],
        )
        assert result == EvidenceTypeLabel.REVIEWED

    def test_hierarchy_experimental_trumps_predicted(self) -> None:
        result = EvidencePropagator.combine(
            [EvidenceTypeLabel.PREDICTED, EvidenceTypeLabel.EXPERIMENTAL],
        )
        assert result == EvidenceTypeLabel.EXPERIMENTAL

    def test_default_label(self) -> None:
        tagged = EvidenceTagged(value="test")
        assert tagged.evidence_label == EvidenceTypeLabel.EXPERIMENTAL

    def test_mixed_combine(self) -> None:
        result = EvidencePropagator.combine(
            [
                EvidenceTypeLabel.PREDICTED,
                EvidenceTypeLabel.EXPERIMENTAL,
                EvidenceTypeLabel.REVIEWED,
            ],
        )
        assert result == EvidenceTypeLabel.REVIEWED

    def test_combine_all_predicted(self) -> None:
        result = EvidencePropagator.combine(
            [EvidenceTypeLabel.PREDICTED, EvidenceTypeLabel.PREDICTED],
        )
        assert result == EvidenceTypeLabel.PREDICTED

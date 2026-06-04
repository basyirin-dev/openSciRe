from datetime import UTC, datetime

from openscire.references.retraction.models import (
    RetractionRecord,
    RetractionSource,
    RetractionStatus,
)


class TestRetractionStatus:
    def test_values(self) -> None:
        assert RetractionStatus.unchecked == "unchecked"
        assert RetractionStatus.retracted == "retracted"
        assert RetractionStatus.corrected == "corrected"
        assert RetractionStatus.expression_of_concern == "expression_of_concern"
        assert RetractionStatus.concern_raised == "concern_raised"
        assert RetractionStatus.unknown == "unknown"


class TestRetractionSource:
    def test_values(self) -> None:
        assert RetractionSource.pubmed == "pubmed"
        assert RetractionSource.crossref == "crossref"
        assert RetractionSource.pubpeer == "pubpeer"
        assert RetractionSource.openalex == "openalex"


class TestRetractionRecord:
    def test_defaults(self) -> None:
        record = RetractionRecord(
            identifier="10.1234/test",
            source=RetractionSource.pubmed,
        )
        assert record.identifier == "10.1234/test"
        assert record.retraction_status == RetractionStatus.unchecked
        assert record.source == RetractionSource.pubmed
        assert record.notice_text == ""
        assert record.notice_url == ""
        assert record.reason == ""
        assert record.details == {}

    def test_full_construction(self) -> None:
        now = datetime.now(UTC)
        record = RetractionRecord(
            identifier="10.1234/retracted",
            retraction_status=RetractionStatus.retracted,
            source=RetractionSource.crossref,
            detected_at=now,
            updated_at=now,
            notice_text="Figures manipulated",
            notice_url="https://doi.org/10.1234/retraction",
            reason="Figure manipulation",
            details={"original_doi": "10.1234/original"},
        )
        assert record.retraction_status == RetractionStatus.retracted
        assert record.notice_text == "Figures manipulated"
        assert record.details["original_doi"] == "10.1234/original"

    def test_serialization(self) -> None:
        record = RetractionRecord(
            identifier="10.1234/test",
            source=RetractionSource.pubpeer,
            retraction_status=RetractionStatus.concern_raised,
        )
        data = record.model_dump()
        assert data["identifier"] == "10.1234/test"
        assert data["source"] == "pubpeer"
        assert data["retraction_status"] == "concern_raised"
        restored = RetractionRecord(**data)
        assert restored.identifier == record.identifier
        assert restored.source == record.source
        assert restored.retraction_status == record.retraction_status

    def test_status_iteration_order(self) -> None:
        statuses = list(RetractionStatus)
        assert statuses[0] == RetractionStatus.unchecked
        assert statuses[-1] == RetractionStatus.unknown

    def test_source_unique(self) -> None:
        sources = list(RetractionSource)
        assert len(sources) == 4

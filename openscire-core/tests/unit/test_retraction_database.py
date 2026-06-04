from datetime import UTC, datetime

import pytest
from openscire.references.retraction.database import RetractionDatabase
from openscire.references.retraction.models import (
    RetractionRecord,
    RetractionSource,
    RetractionStatus,
)


@pytest.fixture
def db() -> RetractionDatabase:
    return RetractionDatabase(":memory:")


class TestRetractionDatabase:
    def test_upsert_and_get(self, db: RetractionDatabase) -> None:
        record = RetractionRecord(
            identifier="10.1234/test",
            source=RetractionSource.pubmed,
            retraction_status=RetractionStatus.retracted,
        )
        db.upsert(record)
        retrieved = db.get("10.1234/test", RetractionSource.pubmed)
        assert retrieved is not None
        assert retrieved.identifier == "10.1234/test"
        assert retrieved.retraction_status == RetractionStatus.retracted

    def test_upsert_updates_existing(self, db: RetractionDatabase) -> None:
        record = RetractionRecord(
            identifier="10.1234/test",
            source=RetractionSource.pubmed,
            retraction_status=RetractionStatus.unchecked,
        )
        db.upsert(record)

        updated = RetractionRecord(
            identifier="10.1234/test",
            source=RetractionSource.pubmed,
            retraction_status=RetractionStatus.retracted,
            notice_text="Now retracted",
        )
        db.upsert(updated)

        retrieved = db.get("10.1234/test", RetractionSource.pubmed)
        assert retrieved is not None
        assert retrieved.retraction_status == RetractionStatus.retracted
        assert retrieved.notice_text == "Now retracted"

    def test_get_nonexistent(self, db: RetractionDatabase) -> None:
        assert db.get("10.9999/nonexistent") is None

    def test_get_without_source(self, db: RetractionDatabase) -> None:
        r1 = RetractionRecord(
            identifier="10.1234/a",
            source=RetractionSource.pubmed,
            retraction_status=RetractionStatus.retracted,
        )
        db.upsert(r1)
        retrieved = db.get("10.1234/a")
        assert retrieved is not None
        assert retrieved.identifier == "10.1234/a"

    def test_list_retracted(self, db: RetractionDatabase) -> None:
        r1 = RetractionRecord(
            identifier="10.1234/a", source=RetractionSource.pubmed,
            retraction_status=RetractionStatus.retracted,
        )
        r2 = RetractionRecord(
            identifier="10.1234/b", source=RetractionSource.crossref,
            retraction_status=RetractionStatus.expression_of_concern,
        )
        r3 = RetractionRecord(
            identifier="10.1234/c", source=RetractionSource.openalex,
            retraction_status=RetractionStatus.unchecked,
        )
        for r in (r1, r2, r3):
            db.upsert(r)

        retracted = db.list_retracted()
        assert len(retracted) == 2
        assert retracted[0].identifier in ("10.1234/a", "10.1234/b")
        assert retracted[1].identifier in ("10.1234/a", "10.1234/b")

    def test_list_retracted_empty(self, db: RetractionDatabase) -> None:
        assert db.list_retracted() == []

    def test_list_needing_update(self, db: RetractionDatabase) -> None:
        old = RetractionRecord(
            identifier="10.1234/old",
            source=RetractionSource.pubmed,
            retraction_status=RetractionStatus.unchecked,
            updated_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        fresh = RetractionRecord(
            identifier="10.1234/fresh",
            source=RetractionSource.crossref,
            retraction_status=RetractionStatus.retracted,
            updated_at=datetime.now(UTC),
        )
        db.upsert(old)
        db.upsert(fresh)

        stale = db.list_needing_update(max_age_seconds=3600)
        assert len(stale) == 1
        assert stale[0].identifier == "10.1234/old"

    def test_count(self, db: RetractionDatabase) -> None:
        assert db.count() == 0
        db.upsert(RetractionRecord(identifier="10.1234/a", source=RetractionSource.pubmed))
        assert db.count() == 1
        db.upsert(RetractionRecord(identifier="10.1234/b", source=RetractionSource.crossref))
        assert db.count() == 2

    def test_count_by_status(self, db: RetractionDatabase) -> None:
        db.upsert(RetractionRecord(  # noqa: E501
            identifier="10.1234/a", source=RetractionSource.pubmed,
            retraction_status=RetractionStatus.retracted,
        ))
        db.upsert(RetractionRecord(  # noqa: E501
            identifier="10.1234/b", source=RetractionSource.crossref,
            retraction_status=RetractionStatus.retracted,
        ))
        db.upsert(RetractionRecord(  # noqa: E501
            identifier="10.1234/c", source=RetractionSource.openalex,
            retraction_status=RetractionStatus.unchecked,
        ))
        assert db.count_by_status(RetractionStatus.retracted) == 2
        assert db.count_by_status(RetractionStatus.unchecked) == 1
        assert db.count_by_status(RetractionStatus.corrected) == 0

    def test_get_all_identifiers(self, db: RetractionDatabase) -> None:
        db.upsert(RetractionRecord(identifier="10.1234/a", source=RetractionSource.pubmed))
        db.upsert(RetractionRecord(identifier="10.1234/b", source=RetractionSource.crossref))
        ids = db.get_all_identifiers()
        assert sorted(ids) == ["10.1234/a", "10.1234/b"]

    def test_delete(self, db: RetractionDatabase) -> None:
        db.upsert(RetractionRecord(identifier="10.1234/a", source=RetractionSource.pubmed))
        assert db.count() == 1
        assert db.delete("10.1234/a", RetractionSource.pubmed) is True
        assert db.count() == 0
        assert db.delete("10.1234/a", RetractionSource.pubmed) is False

    def test_close(self, db: RetractionDatabase) -> None:
        db.close()
        assert db._conn is None

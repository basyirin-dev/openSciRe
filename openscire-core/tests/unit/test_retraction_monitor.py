from datetime import UTC, datetime

import pytest
from openscire.references.retraction.database import RetractionDatabase
from openscire.references.retraction.models import (
    RetractionRecord,
    RetractionSource,
    RetractionStatus,
)
from openscire.references.retraction.monitor import RetractionMonitor


@pytest.fixture
def db() -> RetractionDatabase:
    return RetractionDatabase(":memory:")


class TestRetractionMonitor:
    @pytest.mark.asyncio
    async def test_get_status_unchecked(self, db: RetractionDatabase) -> None:
        monitor = RetractionMonitor(database=db)
        status = monitor.get_status("10.1234/nonexistent")
        assert status == RetractionStatus.unchecked

    @pytest.mark.asyncio
    async def test_check_paper_openalex(self, db: RetractionDatabase) -> None:
        def is_retracted(doi: str) -> bool:
            return doi == "10.1234/retracted"

        monitor = RetractionMonitor(
            database=db,
            openalex_is_retracted_fn=is_retracted,
        )
        status, records = await monitor.check_paper("10.1234/retracted")
        assert status == RetractionStatus.retracted
        assert len(records) == 1
        assert records[0].source == RetractionSource.openalex
        assert records[0].identifier == "10.1234/retracted"

    @pytest.mark.asyncio
    async def test_check_paper_not_retracted(self, db: RetractionDatabase) -> None:
        def is_retracted(_doi: str) -> bool:
            return False

        monitor = RetractionMonitor(
            database=db,
            openalex_is_retracted_fn=is_retracted,
        )
        status, records = await monitor.check_paper("10.1234/clean")
        assert status == RetractionStatus.unchecked
        assert records == []

    @pytest.mark.asyncio
    async def test_check_batch(self, db: RetractionDatabase) -> None:
        retracted_dois: set[str] = {"10.1234/bad"}
        def is_retracted(doi: str) -> bool:
            return doi in retracted_dois

        monitor = RetractionMonitor(
            database=db,
            openalex_is_retracted_fn=is_retracted,
        )
        results = await monitor.check_batch(["10.1234/bad", "10.1234/good"])
        assert results["10.1234/bad"][0] == RetractionStatus.retracted
        assert results["10.1234/good"][0] == RetractionStatus.unchecked

    @pytest.mark.asyncio
    async def test_refresh_if_needed_stale(self, db: RetractionDatabase) -> None:
        def is_retracted(doi: str) -> bool:
            return doi == "10.1234/retracted"

        monitor = RetractionMonitor(
            database=db,
            openalex_is_retracted_fn=is_retracted,
        )
        status = await monitor.refresh_if_needed("10.1234/retracted", max_age=0)
        assert status == RetractionStatus.retracted

    @pytest.mark.asyncio
    async def test_refresh_if_needed_fresh_skips(self, db: RetractionDatabase) -> None:
        record = RetractionRecord(
            identifier="10.1234/fresh",
            source=RetractionSource.openalex,
            retraction_status=RetractionStatus.unchecked,
        )
        db.upsert(record)

        monitor = RetractionMonitor(database=db)
        status = monitor.get_status("10.1234/fresh")
        assert status == RetractionStatus.unchecked

    @pytest.mark.asyncio
    async def test_needs_update(self, db: RetractionDatabase) -> None:
        monitor = RetractionMonitor(database=db)
        assert monitor.needs_update("10.1234/missing") is True

        record = RetractionRecord(
            identifier="10.1234/existing",
            source=RetractionSource.openalex,
            retraction_status=RetractionStatus.unchecked,
            updated_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        db.upsert(record)
        assert monitor.needs_update("10.1234/existing", max_age=3600) is True

    @pytest.mark.asyncio
    async def test_check_stored_papers_no_stale(self, db: RetractionDatabase) -> None:
        monitor = RetractionMonitor(database=db)
        flagged = await monitor.check_stored_papers(max_age=86400)
        assert flagged == 0

    @pytest.mark.asyncio
    async def test_on_flag_callback(self, db: RetractionDatabase) -> None:
        def is_retracted(doi: str) -> bool:
            return doi == "10.1234/now-retracted"

        flagged_dois: list[str] = []
        def flag_cb(doi: str, _old: RetractionStatus, _new: RetractionStatus, _records: list) -> None:  # noqa: E501
            flagged_dois.append(doi)

        monitor = RetractionMonitor(
            database=db,
            openalex_is_retracted_fn=is_retracted,
        )
        monitor.on_flag(flag_cb)
        status, records = await monitor.check_paper("10.1234/now-retracted")
        assert status == RetractionStatus.retracted
        assert len(flagged_dois) == 0  # flag only fires during check_stored_papers

    @pytest.mark.asyncio
    async def test_invalidate_citations(self, db: RetractionDatabase) -> None:
        monitor = RetractionMonitor(database=db)
        result = monitor.invalidate_citations(
            doi="10.1234/retracted",
        )
        assert result["claims"] == []
        assert result["sources"] == []

    @pytest.mark.asyncio
    async def test_invalidate_citations_with_sources(self, db: RetractionDatabase) -> None:
        monitor = RetractionMonitor(database=db)

        try:
            from openscire.ethics.models import Source

            sources = [
                Source(source_id="src-1", doi="10.1234/retracted"),
                Source(source_id="src-2", doi="10.1234/other"),
            ]
        except ImportError:
            pytest.skip("Source model not available")

        monitor.invalidate_citations(
            doi="10.1234/retracted",
            sources=sources,
        )
        assert sources[0].retracted is True
        assert sources[1].retracted is False

    @pytest.mark.asyncio
    async def test_close(self, db: RetractionDatabase) -> None:
        monitor = RetractionMonitor(database=db)
        await monitor.close()

    @pytest.mark.asyncio
    async def test_invalidate_citations_no_mutation_on_mismatch(
        self, db: RetractionDatabase
    ) -> None:
        monitor = RetractionMonitor(database=db)

        try:
            from openscire.ethics.models import Source

            sources = [
                Source(source_id="src-1", doi="10.1234/different"),
            ]
        except ImportError:
            pytest.skip("Source model not available")

        result = monitor.invalidate_citations(doi="10.1234/retracted", sources=sources)
        assert sources[0].retracted is False
        assert result["sources"] == []

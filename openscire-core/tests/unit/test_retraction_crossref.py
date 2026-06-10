import pytest
import respx
from httpx import Response
from openscire.references.retraction.crossref_feed import CrossrefRetractionClient
from openscire.references.retraction.models import RetractionStatus

CORRECTIONS_RESPONSE = {
    "status": "ok",
    "message": {
        "items": [
            {
                "DOI": "10.1234/retracted",
                "title": ["Retracted Paper"],
                "container-title": ["J Fake Sci"],
                "update-to": [
                    {
                        "type": "retraction",
                        "DOI": "10.1234/retraction-notice",
                        "label": "This article has been retracted",
                        "timestamp": 1700000000000,
                    }
                ],
            },
            {
                "DOI": "10.1234/corrected",
                "title": ["Corrected Paper"],
                "update-to": [
                    {
                        "type": "correction",
                        "DOI": "10.1234/correction-notice",
                        "label": "Minor correction",
                        "timestamp": 1700000000000,
                    }
                ],
            },
            {
                "DOI": "10.1234/unchanged",
                "title": ["Unchanged Paper"],
                "update-to": [],
            },
        ]
    },
}

EMPTY_RESPONSE = {"status": "ok", "message": {"items": []}}


class TestCrossrefRetractionClient:
    @pytest.mark.asyncio
    @respx.mock
    async def test_search_recent_corrections(self) -> None:
        client = CrossrefRetractionClient()
        respx.get("https://api.crossref.org/works").mock(
            return_value=Response(200, json=CORRECTIONS_RESPONSE)
        )

        results = await client.search_recent_corrections(rows=10)
        assert len(results) == 2
        assert results[0]["item"]["DOI"] == "10.1234/retracted"
        assert len(results[0]["updates"]) == 1
        assert results[1]["item"]["DOI"] == "10.1234/corrected"
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_recent_corrections_empty(self) -> None:
        client = CrossrefRetractionClient()
        respx.get("https://api.crossref.org/works").mock(
            return_value=Response(200, json=EMPTY_RESPONSE)
        )

        results = await client.search_recent_corrections(rows=10)
        assert results == []
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_to_retraction_record_retraction(self) -> None:
        client = CrossrefRetractionClient()
        item = {
            "DOI": "10.1234/retracted",
            "title": ["Retracted Paper"],
        }
        update = {
            "type": "retraction",
            "DOI": "10.1234/retraction-notice",
            "label": "This article has been retracted",
        }
        record = await client.to_retraction_record(item, update)
        assert record.identifier == "https://doi.org/10.1234/retracted"
        assert record.retraction_status == RetractionStatus.retracted
        assert record.source == "crossref"
        assert "retraction-notice" in record.notice_url

    @pytest.mark.asyncio
    @respx.mock
    async def test_to_retraction_record_correction(self) -> None:
        client = CrossrefRetractionClient()
        item = {"DOI": "10.1234/corrected", "title": ["Corrected Paper"]}
        update = {"type": "correction", "DOI": "10.1234/correction", "label": "Minor fix"}
        record = await client.to_retraction_record(item, update)
        assert record.retraction_status == RetractionStatus.corrected
        assert record.source == "crossref"

    @pytest.mark.asyncio
    @respx.mock
    async def test_to_retraction_record_eoc(self) -> None:
        client = CrossrefRetractionClient()
        item = {"DOI": "10.1234/concern", "title": ["Expression of Concern"]}
        update = {"type": "expression-of-concern", "DOI": "", "label": "Expression of Concern"}
        record = await client.to_retraction_record(item, update)
        assert record.retraction_status == RetractionStatus.expression_of_concern
        assert record.source == "crossref"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_correction_detail(self) -> None:
        client = CrossrefRetractionClient()
        respx.get("https://api.crossref.org/works/10.1234/test").mock(
            return_value=Response(
                200, json={"status": "ok", "message": {"DOI": "10.1234/test", "title": ["Test"]}}
            )  # noqa: E501
        )

        detail = await client.get_correction_detail("10.1234/test")
        assert detail["DOI"] == "10.1234/test"
        await client.close()

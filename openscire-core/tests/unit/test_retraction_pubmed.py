import pytest
import respx
from httpx import Response
from openscire.references.retraction.pubmed_feed import PubMedRetractionClient

SEARCH_RESPONSE = {
    "esearchresult": {
        "count": "2",
        "idlist": ["12345", "67890"],
    },
}

SUMMARY_RESPONSE = {
    "result": {
        "uids": ["12345", "67890"],
        "12345": {
            "uid": "12345",
            "title": "Retracted Paper A",
            "elocationid": "doi:10.1234/a",
            "source": "J Fake Sci",
            "pubdate": "2024 Jan",
        },
        "67890": {
            "uid": "67890",
            "title": "Retracted Paper B",
            "elocationid": "doi:10.1234/b",
            "source": "J Retracted Res",
            "pubdate": "2024 Feb",
        },
    },
}

EMPTY_SEARCH = {"esearchresult": {"count": "0", "idlist": []}}


class TestPubMedRetractionClient:
    @pytest.mark.asyncio
    @respx.mock
    async def test_search_retracted(self) -> None:
        client = PubMedRetractionClient(email="test@example.com")
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
            return_value=Response(200, json=SEARCH_RESPONSE)
        )
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi").mock(
            return_value=Response(200, json=SUMMARY_RESPONSE)
        )

        results = await client.search_retracted(max_results=10)
        assert len(results) == 2
        assert results[0]["doi"] == "10.1234/a"
        assert results[1]["doi"] == "10.1234/b"
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_retracted_empty(self) -> None:
        client = PubMedRetractionClient(email="test@example.com")
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
            return_value=Response(200, json=EMPTY_SEARCH)
        )

        results = await client.search_retracted(max_results=10)
        assert results == []
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_to_retraction_record(self) -> None:
        client = PubMedRetractionClient(email="test@example.com")
        summary = {
            "pmid": "12345",
            "doi": "10.1234/a",
            "title": "Retracted Paper A",
        }
        record = await client.to_retraction_record(summary)
        assert record is not None
        assert record.identifier == "10.1234/a"
        assert record.retraction_status == "retracted"
        assert record.source == "pubmed"
        assert record.details["pmid"] == "12345"

    @pytest.mark.asyncio
    @respx.mock
    async def test_to_retraction_record_no_doi(self) -> None:
        client = PubMedRetractionClient(email="test@example.com")
        summary = {"pmid": "12345", "doi": ""}
        record = await client.to_retraction_record(summary)
        assert record is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_extract_doi(self) -> None:
        assert PubMedRetractionClient._extract_doi("doi:10.1234/test") == "10.1234/test"
        assert PubMedRetractionClient._extract_doi("10.1234/test") == "10.1234/test"

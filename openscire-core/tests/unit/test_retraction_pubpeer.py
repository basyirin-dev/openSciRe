import pytest
import respx
from httpx import Response
from openscire.references.retraction.pubpeer import PubPeerClient

SEARCH_RESPONSE = [
    {
        "id": "comment-123",
        "doi": "10.1234/test",
        "title": "Concern about Figure 3",
        "category": "concern",
        "text": "The data in Figure 3 appears to be manipulated",
        "authors": "Peer Reviewer",
    }
]

CONCERN_RESPONSE = [
    {
        "id": "comment-456",
        "doi": "10.1234/concerned",
        "title": "Possible fabrication",
        "category": "concern",
        "text": "Western blot bands appear duplicated",
    }
]

NON_CONCERN_RESPONSE = [
    {
        "id": "comment-789",
        "doi": "10.1234/normal",
        "title": "Minor typo",
        "category": "comment",
        "text": "There is a typo in the abstract",
    }
]


class TestPubPeerClient:
    @pytest.mark.asyncio
    @respx.mock
    async def test_search_by_doi(self) -> None:
        client = PubPeerClient(api_key="test-key")
        respx.get("https://pubpeer.com/api/v3/search").mock(
            return_value=Response(200, json=SEARCH_RESPONSE)
        )

        results = await client.search_by_doi("10.1234/test")
        assert len(results) == 1
        assert results[0]["doi"] == "10.1234/test"
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_by_doi_no_api_key(self) -> None:
        client = PubPeerClient()
        results = await client.search_by_doi("10.1234/test")
        assert results == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_concerns_filters_correctly(self) -> None:
        client = PubPeerClient(api_key="test-key")
        respx.get("https://pubpeer.com/api/v3/search").mock(
            return_value=Response(200, json=CONCERN_RESPONSE)
        )

        concerns = await client.get_concerns("10.1234/concerned")
        assert len(concerns) == 1
        assert concerns[0]["category"] == "concern"
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_concerns_filters_non_concern(self) -> None:
        client = PubPeerClient(api_key="test-key")
        respx.get("https://pubpeer.com/api/v3/search").mock(
            return_value=Response(200, json=NON_CONCERN_RESPONSE)
        )

        concerns = await client.get_concerns("10.1234/normal")
        assert len(concerns) == 0
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_to_retraction_record(self) -> None:
        client = PubPeerClient()
        comment = {
            "id": "c1",
            "doi": "10.1234/test",
            "title": "Serious concern",
            "category": "concern",
        }
        record = await client.to_retraction_record(comment)
        assert record is not None
        assert record.identifier == "10.1234/test"
        assert record.retraction_status == "concern_raised"
        assert record.source == "pubpeer"

    @pytest.mark.asyncio
    @respx.mock
    async def test_to_retraction_record_no_doi(self) -> None:
        client = PubPeerClient()
        record = await client.to_retraction_record({"id": "c1", "doi": ""})
        assert record is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_is_concern_keyword_matching(self) -> None:
        assert PubPeerClient._is_concern({"category": "concern"}) is True
        assert (
            PubPeerClient._is_concern(  # noqa: E501
                {"category": "comment", "title": "possible retraction"}
            )
            is True
        )
        assert PubPeerClient._is_concern({"category": "comment", "text": "minor typo"}) is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_recent_activity_no_key(self) -> None:
        client = PubPeerClient()
        results = await client.get_recent_activity()
        assert results == []

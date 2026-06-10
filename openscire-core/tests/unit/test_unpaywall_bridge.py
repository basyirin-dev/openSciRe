# SPDX-License-Identifier: Apache-2.0

import time

import pytest
import respx
from httpx import Response
from openscire.references.bridges.unpaywall import UnpaywallClient
from openscire.references.models import UnpaywallResult

DOI_RESPONSE = {
    "doi": "10.1038/s41586-019-1093-3",
    "doi_url": "https://doi.org/10.1038/s41586-019-1093-3",
    "title": "A Test Paper on Machine Learning",
    "genre": "journal-article",
    "is_oa": True,
    "oa_status": "gold",
    "has_repository_copy": True,
    "best_oa_location": {
        "url_for_pdf": "https://example.com/paper.pdf",
        "url_for_landing_page": "https://example.com/paper",
        "url": "https://example.com/paper",
        "host_type": "publisher",
        "is_best": True,
        "license": "cc-by",
        "version": "publishedVersion",
        "oa_date": "2024-01-01",
        "repository_institution": None,
        "endpoint_id": None,
        "pmh_id": None,
    },
    "first_oa_location": {
        "url_for_pdf": "https://example.com/paper.pdf",
        "url_for_landing_page": "https://example.com/paper",
        "url": "https://example.com/paper",
        "host_type": "publisher",
        "is_best": True,
        "license": "cc-by",
        "version": "publishedVersion",
        "oa_date": "2024-01-01",
        "repository_institution": None,
        "endpoint_id": None,
        "pmh_id": None,
    },
    "oa_locations": [
        {
            "url_for_pdf": "https://example.com/paper.pdf",
            "url_for_landing_page": "https://example.com/paper",
            "url": "https://example.com/paper",
            "host_type": "publisher",
            "is_best": True,
            "license": "cc-by",
            "version": "publishedVersion",
            "oa_date": "2024-01-01",
            "repository_institution": None,
            "endpoint_id": None,
            "pmh_id": None,
        },
        {
            "url_for_pdf": "https://repository.example.com/paper.pdf",
            "url_for_landing_page": "https://repository.example.com/paper",
            "url": "https://repository.example.com/paper",
            "host_type": "repository",
            "is_best": False,
            "license": None,
            "version": "acceptedVersion",
            "oa_date": None,
            "repository_institution": "ArXiv",
            "endpoint_id": "arxiv",
            "pmh_id": "oai:arxiv.org:1234",
        },
    ],
    "journal_name": "Nature",
    "journal_issns": "0028-0836",
    "journal_issn_l": "0028-0836",
    "journal_is_oa": False,
    "journal_is_in_doaj": False,
    "publisher": "Springer Nature",
    "published_date": "2024-06-01",
    "data_standard": 2,
    "updated": "2024-06-01T00:00:00",
}

CLOSED_RESPONSE = {
    "doi": "10.1234/closed-paper",
    "doi_url": "https://doi.org/10.1234/closed-paper",
    "title": "Closed Access Paper",
    "genre": "journal-article",
    "is_oa": False,
    "oa_status": "closed",
    "has_repository_copy": False,
    "best_oa_location": None,
    "first_oa_location": None,
    "oa_locations": [],
    "journal_name": "Subscription Journal",
    "journal_issns": "1234-5678",
    "journal_issn_l": "1234-5678",
    "journal_is_oa": False,
    "journal_is_in_doaj": False,
    "publisher": "Some Publisher",
    "published_date": "2023-01-15",
    "data_standard": 2,
    "updated": "2023-01-15T00:00:00",
}

GREEN_RESPONSE = {
    "doi": "10.1234/green-paper",
    "doi_url": "https://doi.org/10.1234/green-paper",
    "title": "Green OA Paper",
    "genre": "journal-article",
    "is_oa": True,
    "oa_status": "green",
    "has_repository_copy": True,
    "best_oa_location": {
        "url_for_pdf": "https://repository.example.com/green.pdf",
        "url_for_landing_page": "https://repository.example.com/green",
        "url": "https://repository.example.com/green",
        "host_type": "repository",
        "is_best": True,
        "license": None,
        "version": "acceptedVersion",
        "oa_date": None,
        "repository_institution": "University Repository",
        "endpoint_id": "repo123",
        "pmh_id": None,
    },
    "first_oa_location": {
        "url_for_pdf": "https://repository.example.com/green.pdf",
        "url_for_landing_page": "https://repository.example.com/green",
        "url": "https://repository.example.com/green",
        "host_type": "repository",
        "is_best": True,
        "license": None,
        "version": "acceptedVersion",
        "oa_date": None,
        "repository_institution": "University Repository",
        "endpoint_id": "repo123",
        "pmh_id": None,
    },
    "oa_locations": [
        {
            "url_for_pdf": "https://repository.example.com/green.pdf",
            "url_for_landing_page": "https://repository.example.com/green",
            "url": "https://repository.example.com/green",
            "host_type": "repository",
            "is_best": True,
            "license": None,
            "version": "acceptedVersion",
            "oa_date": None,
            "repository_institution": "University Repository",
            "endpoint_id": "repo123",
            "pmh_id": None,
        }
    ],
    "journal_name": "Subscription Journal",
    "journal_issns": "1234-5678",
    "journal_issn_l": "1234-5678",
    "journal_is_oa": False,
    "journal_is_in_doaj": False,
    "publisher": "Some Publisher",
    "published_date": "2023-06-15",
    "data_standard": 2,
    "updated": "2023-06-15T00:00:00",
}


@pytest.fixture
def client() -> UnpaywallClient:
    return UnpaywallClient(email="test@example.com")


@pytest.fixture
def authed_client() -> UnpaywallClient:
    return UnpaywallClient(email="researcher@university.edu")


class TestUnpaywallRateLimiter:
    def test_default_delay(self) -> None:
        from openscire.references.bridges.unpaywall import UnpaywallRateLimiter

        limiter = UnpaywallRateLimiter()
        assert limiter._delay == 0.1

    @pytest.mark.asyncio
    async def test_rate_limiter_enforces_delay(self) -> None:
        from openscire.references.bridges.unpaywall import UnpaywallRateLimiter

        limiter = UnpaywallRateLimiter()
        await limiter.wait()
        t1 = time.monotonic()
        await limiter.wait()
        t2 = time.monotonic()
        assert t2 - t1 >= 0.09


class TestUnpaywallClient:
    def test_constructor_defaults(self) -> None:
        c = UnpaywallClient(email="test@example.com")
        assert c._email == "test@example.com"
        assert c._rate_limiter._delay == 0.1
        assert c._semaphore._value == 5
        assert c._fallback_clients == {}

    def test_constructor_with_fallbacks(self) -> None:
        c = UnpaywallClient(
            email="test@example.com",
            max_concurrent=3,
            fallback_clients={"openalex": "dummy"},
        )
        assert c._semaphore._value == 3
        assert c._fallback_clients == {"openalex": "dummy"}

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_by_doi(self, client: UnpaywallClient) -> None:
        respx.get("https://api.unpaywall.org/v2/10.1038/s41586-019-1093-3").mock(
            return_value=Response(200, json=DOI_RESPONSE)
        )
        result = await client.fetch_by_doi("10.1038/s41586-019-1093-3")
        assert isinstance(result, UnpaywallResult)
        assert result.doi == "10.1038/s41586-019-1093-3"
        assert result.title == "A Test Paper on Machine Learning"
        assert result.is_oa is True
        assert result.oa_status == "gold"
        assert result.year == 2024
        assert result.published_date == "2024-06-01"
        assert result.journal_name == "Nature"
        assert result.publisher == "Springer Nature"
        assert result.genre == "journal-article"
        assert result.pdf_url == "https://example.com/paper.pdf"
        assert result.doi_url == "https://doi.org/10.1038/s41586-019-1093-3"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_by_doi_closed(self, client: UnpaywallClient) -> None:
        respx.get("https://api.unpaywall.org/v2/10.1234/closed-paper").mock(
            return_value=Response(200, json=CLOSED_RESPONSE)
        )
        result = await client.fetch_by_doi("10.1234/closed-paper")
        assert result.is_oa is False
        assert result.oa_status == "closed"
        assert result.pdf_url == ""
        assert result.best_oa_location is None
        assert result.oa_locations == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_by_doi_parses_oa_locations(self, client: UnpaywallClient) -> None:
        respx.get("https://api.unpaywall.org/v2/10.1038/s41586-019-1093-3").mock(
            return_value=Response(200, json=DOI_RESPONSE)
        )
        result = await client.fetch_by_doi("10.1038/s41586-019-1093-3")
        assert len(result.oa_locations) == 2
        best = result.best_oa_location
        assert best is not None
        assert best.url_for_pdf == "https://example.com/paper.pdf"
        assert best.host_type == "publisher"
        assert best.license == "cc-by"
        assert best.is_best is True
        first = result.first_oa_location
        assert first is not None
        assert first.url_for_pdf == "https://example.com/paper.pdf"

        repo = result.oa_locations[1]
        assert repo.host_type == "repository"
        assert repo.repository_institution == "ArXiv"
        assert repo.endpoint_id == "arxiv"
        assert repo.pmh_id == "oai:arxiv.org:1234"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_pdf_url(self, client: UnpaywallClient) -> None:
        respx.get("https://api.unpaywall.org/v2/10.1038/s41586-019-1093-3").mock(
            return_value=Response(200, json=DOI_RESPONSE)
        )
        url = await client.get_pdf_url("10.1038/s41586-019-1093-3")
        assert url == "https://example.com/paper.pdf"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_pdf_url_closed(self, client: UnpaywallClient) -> None:
        respx.get("https://api.unpaywall.org/v2/10.1234/closed-paper").mock(
            return_value=Response(200, json=CLOSED_RESPONSE)
        )
        url = await client.get_pdf_url("10.1234/closed-paper")
        assert url is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_by_title_valid_doi(self, client: UnpaywallClient) -> None:
        respx.get("https://api.unpaywall.org/v2/10.1038/s41586-019-1093-3").mock(
            return_value=Response(200, json=DOI_RESPONSE)
        )
        results = await client.search_by_title("10.1038/s41586-019-1093-3")
        assert len(results) == 1
        assert results[0].doi == "10.1038/s41586-019-1093-3"

    @pytest.mark.asyncio
    async def test_search_by_title_non_doi(self, client: UnpaywallClient) -> None:
        results = await client.search_by_title("Machine Learning")
        assert results == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_by_title_invalid_doi(self, client: UnpaywallClient) -> None:
        respx.get("https://api.unpaywall.org/v2/10.9999/nonexistent").mock(
            return_value=Response(404, json={})
        )
        results = await client.search_by_title("10.9999/nonexistent")
        assert results == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_batch(self, client: UnpaywallClient) -> None:
        respx.get("https://api.unpaywall.org/v2/10.1038/s41586-019-1093-3").mock(
            return_value=Response(200, json=DOI_RESPONSE)
        )
        respx.get("https://api.unpaywall.org/v2/10.1234/closed-paper").mock(
            return_value=Response(200, json=CLOSED_RESPONSE)
        )
        results = await client.fetch_batch(
            [
                "10.1038/s41586-019-1093-3",
                "10.1234/closed-paper",
            ]
        )
        assert len(results) == 2
        assert results[0].doi == "10.1038/s41586-019-1093-3"
        assert results[0].is_oa is True
        assert results[1].doi == "10.1234/closed-paper"
        assert results[1].is_oa is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_batch_skips_failures(self, client: UnpaywallClient) -> None:
        respx.get("https://api.unpaywall.org/v2/10.1038/s41586-019-1093-3").mock(
            return_value=Response(200, json=DOI_RESPONSE)
        )
        respx.get("https://api.unpaywall.org/v2/10.9999/fail").mock(
            return_value=Response(404, json={})
        )
        results = await client.fetch_batch(
            [
                "10.1038/s41586-019-1093-3",
                "10.9999/fail",
            ]
        )
        assert len(results) == 1
        assert results[0].doi == "10.1038/s41586-019-1093-3"

    @pytest.mark.asyncio
    @respx.mock
    async def test_resolve_oa_url_unpaywall_only(self, client: UnpaywallClient) -> None:
        respx.get("https://api.unpaywall.org/v2/10.1038/s41586-019-1093-3").mock(
            return_value=Response(200, json=DOI_RESPONSE)
        )
        url = await client.resolve_oa_url("10.1038/s41586-019-1093-3")
        assert url == "https://example.com/paper.pdf"

    @pytest.mark.asyncio
    @respx.mock
    async def test_resolve_oa_url_closed_no_fallback(self, client: UnpaywallClient) -> None:
        respx.get("https://api.unpaywall.org/v2/10.1234/closed-paper").mock(
            return_value=Response(200, json=CLOSED_RESPONSE)
        )
        url = await client.resolve_oa_url("10.1234/closed-paper")
        assert url is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_classify_oa_gold(self, client: UnpaywallClient) -> None:
        respx.get("https://api.unpaywall.org/v2/10.1038/s41586-019-1093-3").mock(
            return_value=Response(200, json=DOI_RESPONSE)
        )
        result = await client.fetch_by_doi("10.1038/s41586-019-1093-3")
        category = UnpaywallClient.classify_oa(result)
        assert category == "gold"

    @pytest.mark.asyncio
    @respx.mock
    async def test_classify_oa_green(self, client: UnpaywallClient) -> None:
        respx.get("https://api.unpaywall.org/v2/10.1234/green-paper").mock(
            return_value=Response(200, json=GREEN_RESPONSE)
        )
        result = await client.fetch_by_doi("10.1234/green-paper")
        category = UnpaywallClient.classify_oa(result)
        assert category == "green"

    @pytest.mark.asyncio
    @respx.mock
    async def test_classify_oa_closed(self, client: UnpaywallClient) -> None:
        respx.get("https://api.unpaywall.org/v2/10.1234/closed-paper").mock(
            return_value=Response(200, json=CLOSED_RESPONSE)
        )
        result = await client.fetch_by_doi("10.1234/closed-paper")
        category = UnpaywallClient.classify_oa(result)
        assert category == "closed"

    @pytest.mark.asyncio
    @respx.mock
    async def test_http_error(self, client: UnpaywallClient) -> None:
        from openscire.exceptions import ReferenceError

        respx.get("https://api.unpaywall.org/v2/10.9999/nonexistent").mock(
            return_value=Response(429, json={"error": "too many requests"})
        )
        with pytest.raises(ReferenceError, match="Unpaywall API error: 429"):
            await client.fetch_by_doi("10.9999/nonexistent")

    @pytest.mark.asyncio
    async def test_close(self, client: UnpaywallClient) -> None:
        await client.close()

    def test_email_is_required(self) -> None:
        with pytest.raises(TypeError):
            UnpaywallClient()  # type: ignore[call-arg]

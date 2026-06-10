# SPDX-License-Identifier: Apache-2.0

import time

import pytest
import respx
from httpx import Response
from openscire.references.bridges.openalex import OpenAlexClient
from openscire.references.models import OpenAlexSearchResult, ReferenceItem, ReferenceSource

SEARCH_RESPONSE = {
    "meta": {"count": 1, "page": 1, "per_page": 25},
    "results": [
        {
            "id": "https://openalex.org/W2741809807",
            "doi": "https://doi.org/10.1038/s41586-019-1093-3",
            "display_name": "  A Test Paper on Machine Learning  ",
            "publication_year": 2024,
            "cited_by_count": 42,
            "open_access": {
                "is_oa": True,
                "oa_status": "gold",
                "oa_url": "https://example.com/paper.pdf",
            },
        }
    ],
}

SEARCH_EMPTY = {"meta": {"count": 0, "page": 1, "per_page": 25}, "results": []}

SEARCH_MULTI = {
    "meta": {"count": 2, "page": 1, "per_page": 25},
    "results": [
        {
            "id": "https://openalex.org/W111111",
            "display_name": "First Paper",
            "publication_year": 2023,
            "cited_by_count": 10,
        },
        {
            "id": "https://openalex.org/W222222",
            "display_name": "Second Paper",
            "publication_year": 2024,
            "cited_by_count": 5,
        },
    ],
}

WORK_DETAIL = {
    "id": "https://openalex.org/W2741809807",
    "doi": "https://doi.org/10.1038/s41586-019-1093-3",
    "display_name": "Full Detail Paper on Deep Learning",
    "publication_date": "2024-06-01",
    "publication_year": 2024,
    "cited_by_count": 142,
    "fwci": 3.2,
    "is_retracted": False,
    "is_oa": True,
    "language": "en",
    "type": "article",
    "ids": {
        "openalex": "https://openalex.org/W2741809807",
        "doi": "https://doi.org/10.1038/s41586-019-1093-3",
        "pmid": "31234567",
    },
    "abstract_inverted_index": {
        "This": [0],
        "is": [1],
        "a": [2],
        "detailed": [3],
        "abstract": [4],
    },
    "authorships": [
        {
            "author": {
                "id": "https://openalex.org/A5023888391",
                "display_name": "John Smith",
                "orcid": "https://orcid.org/0000-0001-6187-6610",
            },
            "institutions": [
                {
                    "id": "https://openalex.org/I136199984",
                    "display_name": "Harvard University",
                    "ror": "https://ror.org/03vek6s52",
                    "country_code": "us",
                    "type": "education",
                }
            ],
            "countries": ["US"],
            "is_corresponding": True,
            "raw_author_name": "Smith, John",
        }
    ],
    "primary_location": {
        "source": {
            "id": "https://openalex.org/S1234",
            "display_name": "Nature",
            "issn_l": "0028-0836",
            "type": "journal",
        },
        "landing_page_url": "https://nature.com/articles/paper",
        "pdf_url": "https://nature.com/articles/paper.pdf",
        "is_oa": False,
        "version": "published",
        "license": None,
    },
    "open_access": {
        "is_oa": True,
        "oa_status": "green",
        "oa_url": "https://repository.example.com/paper",
        "any_repository_has_fulltext": True,
    },
    "topics": [
        {
            "id": "https://openalex.org/T1234",
            "display_name": "Machine Learning",
            "score": 0.92,
            "subfield": {"id": "...", "display_name": "Artificial Intelligence"},
            "field": {"id": "...", "display_name": "Computer Science"},
            "domain": {"id": "...", "display_name": "Physical Sciences"},
        }
    ],
    "concepts": [
        {
            "id": "https://openalex.org/C123",
            "display_name": "Deep Learning",
            "level": 0,
            "score": 0.85,
        }
    ],
    "keywords": [
        {"id": "https://openalex.org/K1", "display_name": "neural networks", "score": 0.7}
    ],
    "biblio": {
        "volume": "42",
        "issue": "3",
        "first_page": "100",
        "last_page": "110",
    },
    "referenced_works": ["https://openalex.org/W999999"],
    "related_works": ["https://openalex.org/W888888"],
    "counts_by_year": [
        {"year": 2024, "cited_by_count": 80},
        {"year": 2025, "cited_by_count": 62},
    ],
    "updated_date": "2024-06-01T00:00:00",
    "created_date": "2023-01-15",
}

AUTHOR_SEARCH_RESPONSE = {
    "meta": {"count": 2, "page": 1, "per_page": 25},
    "results": [
        {
            "id": "https://openalex.org/A5023888391",
            "display_name": "John Smith",
            "works_count": 87,
            "cited_by_count": 14320,
        },
        {
            "id": "https://openalex/A5023888392",
            "display_name": "Jane Doe",
            "works_count": 45,
            "cited_by_count": 8900,
        },
    ],
}

AUTHOR_DETAIL = {
    "id": "https://openalex.org/A5023888391",
    "orcid": "https://orcid.org/0000-0001-6187-6610",
    "display_name": "John Smith",
    "works_count": 87,
    "cited_by_count": 14320,
    "last_known_institutions": [
        {
            "id": "https://openalex.org/I136199984",
            "display_name": "Harvard University",
            "ror": "https://ror.org/03vek6s52",
            "country_code": "us",
            "type": "education",
        }
    ],
    "summary_stats": {"h_index": 22, "i10_index": 35},
}

INSTITUTION_SEARCH_RESPONSE = {
    "meta": {"count": 1, "page": 1, "per_page": 25},
    "results": [
        {
            "id": "https://openalex.org/I136199984",
            "display_name": "Harvard University",
            "country_code": "us",
            "type": "education",
            "homepage_url": "https://www.harvard.edu",
            "works_count": 870627,
            "cited_by_count": 28450000,
        }
    ],
}

INSTITUTION_DETAIL = {
    "id": "https://openalex.org/I136199984",
    "ror": "https://ror.org/03vek6s52",
    "display_name": "Harvard University",
    "country_code": "us",
    "type": "education",
    "homepage_url": "https://www.harvard.edu",
    "works_count": 870627,
    "cited_by_count": 28450000,
    "geo": {"city": "Cambridge", "region": "Massachusetts", "country": "United States"},
}

TOPIC_SEARCH_RESPONSE = {
    "meta": {"count": 2, "page": 1, "per_page": 25},
    "results": [
        {
            "id": "https://openalex.org/T1234",
            "display_name": "Machine Learning",
            "works_count": 150000,
            "cited_by_count": 5000000,
        },
        {
            "id": "https://openalex.org/T5678",
            "display_name": "Deep Learning",
            "works_count": 80000,
            "cited_by_count": 3000000,
        },
    ],
}

TOPIC_DETAIL = {
    "id": "https://openalex.org/T1234",
    "display_name": "Machine Learning",
    "description": "The study of algorithms that improve through experience.",
    "works_count": 150000,
    "cited_by_count": 5000000,
    "subfield": {"id": "...", "display_name": "Artificial Intelligence"},
    "field": {"id": "...", "display_name": "Computer Science"},
    "domain": {"id": "...", "display_name": "Physical Sciences"},
}

AUTOCOMPLETE_RESPONSE = {
    "meta": {"count": 2},
    "results": [
        {
            "id": "https://openalex.org/W123",
            "display_name": "Machine Learning",
            "hint": "2019 · 1420 citations",
            "cited_by_count": 1420,
            "works_count": None,
            "entity_type": "work",
            "external_id": None,
        },
        {
            "id": "https://openalex.org/W456",
            "display_name": "Machine Learning for Dummies",
            "hint": "2020 · 500 citations",
            "cited_by_count": 500,
            "works_count": None,
            "entity_type": "work",
            "external_id": None,
        },
    ],
}

RATE_LIMIT_RESPONSE = {
    "X-RateLimit-Limit": "1.00",
    "X-RateLimit-Remaining": "0.95",
    "X-RateLimit-Reset": "86399",
}

CITATION_COUNT_RESPONSE = {"cited_by_count": 142}


@pytest.fixture
def client() -> OpenAlexClient:
    return OpenAlexClient()


@pytest.fixture
def authed_client() -> OpenAlexClient:
    return OpenAlexClient(api_key="test_key_456")


class TestOpenAlexClient:
    def test_constructor_defaults(self) -> None:
        c = OpenAlexClient()
        assert c._api_key == ""
        assert c._email == ""
        assert c._rate_limiter._delay == 3.0

    def test_constructor_with_api_key(self) -> None:
        c = OpenAlexClient(api_key="key123", email="test@example.com")
        assert c._api_key == "key123"
        assert c._email == "test@example.com"
        assert c._rate_limiter._delay == 0.1

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_works(self, client: OpenAlexClient) -> None:
        respx.get("https://api.openalex.org/works").mock(
            return_value=Response(200, json=SEARCH_RESPONSE)
        )
        result = await client.search_works("machine learning")
        assert isinstance(result, OpenAlexSearchResult)
        assert result.total_count == 1
        assert result.page == 1
        assert len(result.work_ids) == 1
        assert "W2741809807" in result.work_ids[0]

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_works_empty(self, client: OpenAlexClient) -> None:
        respx.get("https://api.openalex.org/works").mock(
            return_value=Response(200, json=SEARCH_EMPTY)
        )
        result = await client.search_works("nonexistent")
        assert result.total_count == 0
        assert result.work_ids == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_works(self, client: OpenAlexClient) -> None:
        respx.get("https://api.openalex.org/works").mock(
            return_value=Response(200, json=SEARCH_MULTI)
        )
        result = await client.list_works("publication_year:2024")
        assert isinstance(result, OpenAlexSearchResult)
        assert result.total_count == 2
        assert len(result.work_ids) == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_work(self, client: OpenAlexClient) -> None:
        respx.get("https://api.openalex.org/works/W2741809807").mock(
            return_value=Response(200, json=WORK_DETAIL)
        )
        item = await client.fetch_work("W2741809807")
        assert isinstance(item, ReferenceItem)
        assert item.id == "W2741809807"
        assert item.source == ReferenceSource.openalex
        assert item.doi == "10.1038/s41586-019-1093-3"
        assert item.title == "Full Detail Paper on Deep Learning"
        assert item.year == 2024
        assert item.journal == "Nature"
        assert item.volume == "42"
        assert item.issue == "3"
        assert item.pages == "100-110"
        assert item.abstract == "This is a detailed abstract"
        assert len(item.authors) == 1
        assert item.authors[0].full == "John Smith"
        assert item.authors[0].first == "John"
        assert item.authors[0].last == "Smith"
        assert item.extra.get("cited_by_count") == 142
        assert item.extra.get("fwci") == 3.2
        assert item.extra.get("type") == "article"
        assert item.extra.get("language") == "en"
        assert item.extra.get("is_oa") is True
        assert "Machine Learning" in item.keywords
        assert "Deep Learning" in item.keywords
        assert "neural networks" in item.keywords
        assert len(item.extra.get("topics")) == 1
        assert item.extra["topics"][0]["name"] == "Machine Learning"
        assert len(item.extra.get("authorships")) == 1
        assert item.extra["authorships"][0]["author_name"] == "John Smith"
        assert len(item.extra["authorships"][0]["institutions"]) == 1
        assert item.extra["authorships"][0]["institutions"][0]["name"] == "Harvard University"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_work_by_doi(self, client: OpenAlexClient) -> None:
        respx.get("https://api.openalex.org/works/doi:10.1234/test").mock(
            return_value=Response(200, json=WORK_DETAIL)
        )
        item = await client.fetch_work("doi:10.1234/test")
        assert item.id == "W2741809807"
        assert item.doi == "10.1038/s41586-019-1093-3"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_works_batch(self, client: OpenAlexClient) -> None:
        respx.get("https://api.openalex.org/works").mock(
            return_value=Response(200, json=SEARCH_MULTI)
        )
        items = await client.fetch_works_batch(["W111111", "W222222"])
        assert len(items) == 2
        assert items[0].id == "W111111"
        assert items[0].title == "First Paper"
        assert items[1].id == "W222222"
        assert items[1].title == "Second Paper"

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_authors(self, client: OpenAlexClient) -> None:
        respx.get("https://api.openalex.org/authors").mock(
            return_value=Response(200, json=AUTHOR_SEARCH_RESPONSE)
        )
        authors = await client.search_authors("John Smith")
        assert len(authors) == 2
        assert authors[0]["display_name"] == "John Smith"
        assert authors[0]["works_count"] == 87

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_author(self, client: OpenAlexClient) -> None:
        respx.get("https://api.openalex.org/authors/A5023888391").mock(
            return_value=Response(200, json=AUTHOR_DETAIL)
        )
        author = await client.fetch_author("A5023888391")
        assert author["display_name"] == "John Smith"
        assert author["summary_stats"]["h_index"] == 22

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_institutions(self, client: OpenAlexClient) -> None:
        respx.get("https://api.openalex.org/institutions").mock(
            return_value=Response(200, json=INSTITUTION_SEARCH_RESPONSE)
        )
        insts = await client.search_institutions("Harvard")
        assert len(insts) == 1
        assert insts[0]["display_name"] == "Harvard University"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_institution(self, client: OpenAlexClient) -> None:
        respx.get("https://api.openalex.org/institutions/I136199984").mock(
            return_value=Response(200, json=INSTITUTION_DETAIL)
        )
        inst = await client.fetch_institution("I136199984")
        assert inst["display_name"] == "Harvard University"
        assert inst["type"] == "education"

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_topics(self, client: OpenAlexClient) -> None:
        respx.get("https://api.openalex.org/topics").mock(
            return_value=Response(200, json=TOPIC_SEARCH_RESPONSE)
        )
        topics = await client.search_topics("machine learning")
        assert len(topics) == 2
        assert topics[0]["display_name"] == "Machine Learning"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_topic(self, client: OpenAlexClient) -> None:
        respx.get("https://api.openalex.org/topics/T1234").mock(
            return_value=Response(200, json=TOPIC_DETAIL)
        )
        topic = await client.fetch_topic("T1234")
        assert topic["display_name"] == "Machine Learning"
        assert topic["subfield"]["display_name"] == "Artificial Intelligence"
        assert topic["field"]["display_name"] == "Computer Science"
        assert topic["domain"]["display_name"] == "Physical Sciences"

    @pytest.mark.asyncio
    @respx.mock
    async def test_autocomplete(self, client: OpenAlexClient) -> None:
        respx.get("https://api.openalex.org/autocomplete/works").mock(
            return_value=Response(200, json=AUTOCOMPLETE_RESPONSE)
        )
        results = await client.autocomplete("works", "machine learning")
        assert len(results) == 2
        assert results[0]["display_name"] == "Machine Learning"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_author_works(self, client: OpenAlexClient) -> None:
        respx.get("https://api.openalex.org/works").mock(
            return_value=Response(200, json=SEARCH_RESPONSE)
        )
        result = await client.get_author_works("A5023888391")
        assert isinstance(result, OpenAlexSearchResult)
        assert result.total_count == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_related_works(self, client: OpenAlexClient) -> None:
        respx.get("https://api.openalex.org/works").mock(
            return_value=Response(200, json=SEARCH_RESPONSE)
        )
        result = await client.get_related_works("W2741809807")
        assert isinstance(result, OpenAlexSearchResult)
        assert result.total_count == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_citation_count(self, client: OpenAlexClient) -> None:
        respx.get("https://api.openalex.org/works/W2741809807").mock(
            return_value=Response(200, json=CITATION_COUNT_RESPONSE)
        )
        count = await client.fetch_citation_count("W2741809807")
        assert count == 142

    @pytest.mark.asyncio
    @respx.mock
    async def test_check_rate_limit(self, authed_client: OpenAlexClient) -> None:
        respx.get("https://api.openalex.org/rate-limit").mock(
            return_value=Response(200, json=RATE_LIMIT_RESPONSE)
        )
        info = await authed_client.check_rate_limit()
        assert info["X-RateLimit-Remaining"] == "0.95"

    def test_decode_abstract(self) -> None:
        inverted = {"This": [0], "is": [1], "a": [2], "test": [3], "abstract": [4]}
        text = OpenAlexClient.decode_abstract(inverted)
        assert text == "This is a test abstract"

    def test_decode_abstract_empty(self) -> None:
        assert OpenAlexClient.decode_abstract(None) == ""
        assert OpenAlexClient.decode_abstract({}) == ""

    @pytest.mark.asyncio
    @respx.mock
    async def test_http_error(self, client: OpenAlexClient) -> None:
        from openscire.exceptions import ReferenceError

        respx.get("https://api.openalex.org/works").mock(
            return_value=Response(429, json={"error": "too many requests"})
        )
        with pytest.raises(ReferenceError, match="OpenAlex API error: 429"):
            await client.search_works("test")

    @pytest.mark.asyncio
    async def test_close(self, client: OpenAlexClient) -> None:
        await client.close()

    @pytest.mark.asyncio
    async def test_rate_limiter(self) -> None:
        from openscire.references.bridges.openalex import OpenAlexRateLimiter

        limiter = OpenAlexRateLimiter(api_key="test")
        assert limiter._delay == 0.1
        await limiter.wait()
        t1 = time.monotonic()
        await limiter.wait()
        t2 = time.monotonic()
        assert t2 - t1 >= 0.09

    @pytest.mark.asyncio
    async def test_rate_limiter_no_key(self) -> None:
        from openscire.references.bridges.openalex import OpenAlexRateLimiter

        limiter = OpenAlexRateLimiter()
        assert limiter._delay == 3.0

# SPDX-License-Identifier: Apache-2.0

import pytest
import respx
from httpx import Response
from openscire.references.bridges.scielo import ScieloClient
from openscire.references.models import ReferenceItem, ReferenceSource

SEARCH_RESPONSE = {
    "objects": [
        {
            "code": "S0100-204X2024000100001",
            "title": "Machine learning for crop yield prediction",
            "doi": "10.1590/s0100-204x2024000100001",
            "authors": [
                {"name": "João", "surname": "Silva"},
                {"name": "Maria", "surname": "Santos"},
            ],
            "journal_title": "Pesquisa Agropecuária Brasileira",
            "publication_year": 2024,
            "abstract": "This study applies machine learning methods to predict crop yields.",
            "keywords": ["machine learning", "crop yield", "agriculture"],
            "collection": "scl",
            "language": "pt",
        }
    ],
}

ARTICLE_RESPONSE = {
    "code": "S0100-204X2024000100001",
    "pid": "S0100-204X2024000100001",
    "title": "Deep learning for satellite image classification",
    "doi": "https://doi.org/10.1590/s0100-204x2024000100002",
    "authors": [
        {"name": "Carlos", "surname": "Lopez"},
    ],
    "journal_title": "Journal of Applied Remote Sensing",
    "publication_year": 2023,
    "abstract": "A deep learning approach for classifying satellite imagery.",
    "keywords": [
        {"text": "deep learning"},
        {"text": "satellite imagery"},
    ],
    "collection": "esp",
    "language": "en",
}

SEARCH_EMPTY = {"objects": []}

COLLECTION_RESPONSE = [
    {"code": "scl", "name": "Brazil"},
    {"code": "esp", "name": "Spain"},
    {"code": "mex", "name": "Mexico"},
]

ISSN_RESPONSE = {
    "objects": [
        {
            "code": "S0100-204X2024000100001",
            "title": "Paper from ISSN query",
            "doi": "10.1590/issn-test",
            "authors": [],
            "journal_title": "Test Journal",
            "publication_year": 2024,
            "abstract": "Test abstract.",
            "keywords": [],
            "collection": "scl",
            "language": "en",
        }
    ],
}


@pytest.fixture
def client() -> ScieloClient:
    return ScieloClient()


class TestScieloClient:
    def test_constructor(self) -> None:
        c = ScieloClient()
        assert c._rate_limiter._delay == 0.5

    @pytest.mark.asyncio
    @respx.mock
    async def test_search(self, client: ScieloClient) -> None:
        respx.get("https://articlemeta.scielo.org/api/v1/article/").mock(
            return_value=Response(200, json=SEARCH_RESPONSE)
        )
        results = await client.search("machine learning")
        assert len(results) == 1
        item = results[0]
        assert isinstance(item, ReferenceItem)
        assert item.source == ReferenceSource.scielo
        assert item.id == "S0100-204X2024000100001"
        assert item.title == "Machine learning for crop yield prediction"
        assert item.doi == "10.1590/s0100-204x2024000100001"
        assert item.year == 2024
        assert item.journal == "Pesquisa Agropecuária Brasileira"
        assert len(item.authors) == 2
        assert item.authors[0].full == "João Silva"
        assert item.authors[1].full == "Maria Santos"
        assert "machine learning" in item.keywords
        assert item.original_language == "pt"
        assert item.extra.get("collection") == "scl"

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_empty(self, client: ScieloClient) -> None:
        respx.get("https://articlemeta.scielo.org/api/v1/article/").mock(
            return_value=Response(200, json=SEARCH_EMPTY)
        )
        results = await client.search("nonexistent")
        assert results == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_article(self, client: ScieloClient) -> None:
        respx.get("https://articlemeta.scielo.org/api/v1/article/").mock(
            return_value=Response(200, json=ARTICLE_RESPONSE)
        )
        item = await client.fetch_article("S0100-204X2024000100002")
        assert item.title == "Deep learning for satellite image classification"
        assert item.doi == "10.1590/s0100-204x2024000100002"
        assert item.authors[0].full == "Carlos Lopez"
        assert "deep learning" in item.keywords
        assert "satellite imagery" in item.keywords

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_by_doi(self, client: ScieloClient) -> None:
        respx.get("https://articlemeta.scielo.org/api/v1/article/").mock(
            return_value=Response(200, json=ARTICLE_RESPONSE)
        )
        item = await client.fetch_by_doi("10.1590/s0100-204x2024000100002")
        assert item is not None
        assert item.title == "Deep learning for satellite image classification"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_by_doi_not_found(self, client: ScieloClient) -> None:
        respx.get("https://articlemeta.scielo.org/api/v1/article/").mock(
            return_value=Response(404, json={})
        )
        item = await client.fetch_by_doi("10.9999/nonexistent")
        assert item is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_by_title_exact(self, client: ScieloClient) -> None:
        respx.get("https://articlemeta.scielo.org/api/v1/article/").mock(
            return_value=Response(200, json=SEARCH_RESPONSE)
        )
        item = await client.search_by_title("Machine learning for crop yield prediction")
        assert item is not None
        assert item.title == "Machine learning for crop yield prediction"

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_by_title_fallback(self, client: ScieloClient) -> None:
        respx.get("https://articlemeta.scielo.org/api/v1/article/").mock(
            return_value=Response(200, json=SEARCH_RESPONSE)
        )
        item = await client.search_by_title("Different Title")
        assert item is not None
        assert item.title == "Machine learning for crop yield prediction"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_by_issn(self, client: ScieloClient) -> None:
        respx.get("https://articlemeta.scielo.org/api/v1/article/").mock(
            return_value=Response(200, json=ISSN_RESPONSE)
        )
        results = await client.fetch_by_issn("0100-204X")
        assert len(results) == 1
        assert results[0].journal == "Test Journal"

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_collections(self, client: ScieloClient) -> None:
        respx.get("https://articlemeta.scielo.org/api/v1/collection/").mock(
            return_value=Response(200, json=COLLECTION_RESPONSE)
        )
        collections = await client.list_collections()
        assert len(collections) == 3
        assert collections[0]["code"] == "scl"
        assert collections[1]["name"] == "Spain"

    @pytest.mark.asyncio
    @respx.mock
    async def test_http_error(self, client: ScieloClient) -> None:
        from openscire.exceptions import ReferenceError
        respx.get("https://articlemeta.scielo.org/api/v1/article/").mock(
            return_value=Response(429, json={"error": "too many requests"})
        )
        with pytest.raises(ReferenceError, match="SciELO API error: 429"):
            await client.search("test")

    @pytest.mark.asyncio
    async def test_close(self, client: ScieloClient) -> None:
        await client.close()

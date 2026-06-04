# SPDX-License-Identifier: Apache-2.0

import time

import pytest
import respx
from httpx import Response
from openscire.references.bridges.semantic_scholar import SemanticScholarClient
from openscire.references.models import (
    CitationGraphEntry,
    PaperRecommendation,
    ReferenceItem,
    ReferenceSource,
    SemanticScholarSearchResult,
)

SEARCH_RESPONSE = {
    "data": [
        {
            "paperId": "abc123def",
            "title": "  A Test Paper on Machine Learning  ",
            "authors": [{"authorId": "auth1", "name": "John Smith"}],
            "year": 2024,
            "externalIds": {"DOI": "10.1234/test.2024.001", "ArXiv": "2401.12345"},
            "openAccessPdf": {"url": "https://pdf.example.com/paper.pdf", "status": "GREEN"},
        }
    ],
    "next": 10,
    "offset": 0,
    "total": 1,
}

SEARCH_EMPTY = {"data": [], "offset": 0, "total": 0}

SEARCH_MULTI = {
    "data": [
        {
            "paperId": "aaa111",
            "title": "First Paper",
            "authors": [{"authorId": "a1", "name": "Alice A"}],
            "year": 2023,
            "externalIds": {},
        },
        {
            "paperId": "bbb222",
            "title": "Second Paper",
            "authors": [{"authorId": "a2", "name": "Bob B"}],
            "year": 2024,
            "externalIds": {"DOI": "10.1234/test.2024.002"},
        },
    ],
    "next": None,
    "offset": 0,
    "total": 2,
}

DETAIL_RESPONSE = {
    "paperId": "detail001",
    "title": "Detailed Paper Title",
    "authors": [{"authorId": "auth1", "name": "John Smith"}],
    "abstract": "This is a detailed abstract describing the research.",
    "year": 2024,
    "venue": "Journal of Machine Learning",
    "externalIds": {"DOI": "10.1234/test.2024.001"},
    "citationCount": 42,
    "referenceCount": 15,
    "influentialCitationCount": 5,
    "isOpenAccess": True,
    "openAccessPdf": {"url": "https://pdf.example.com/paper.pdf", "status": "GREEN"},
    "embedding": {
        "model": "SPECTER2_2024",
        "vector": [0.1, 0.2, 0.3, 0.4, 0.5],
    },
    "publicationTypes": ["JournalArticle"],
    "fieldsOfStudy": ["Computer Science"],
    "s2FieldsOfStudy": ["Machine Learning"],
    "tldr": {"text": "A short summary of the paper."},
    "publicationDate": "2024-01-15",
    "journal": {"name": "Journal of Machine Learning"},
    "url": "https://semanticscholar.org/paper/detail001",
}

BATCH_RESPONSE = [
    {
        "paperId": "batch001",
        "title": "Batch Paper One",
        "authors": [{"authorId": "a1", "name": "Author One"}],
        "year": 2023,
        "externalIds": {},
    },
    {
        "paperId": "batch002",
        "title": "Batch Paper Two",
        "authors": [{"authorId": "a2", "name": "Author Two"}],
        "year": 2024,
        "externalIds": {"DOI": "10.1234/batch.002"},
    },
]

TITLE_MATCH_RESPONSE = {
    "data": [
        {
            "paperId": "titlematch001",
            "title": "Exact Title Match",
            "authors": [{"authorId": "a1", "name": "Author One"}],
            "year": 2024,
            "externalIds": {"DOI": "10.1234/title.match"},
        }
    ]
}

TITLE_MATCH_EMPTY = {"data": []}

AUTHOR_SEARCH_RESPONSE = {
    "data": [
        {"authorId": "auth1", "name": "John Smith"},
        {"authorId": "auth2", "name": "Jane Doe"},
    ],
    "next": None,
}

AUTHOR_DETAIL_RESPONSE = {
    "authorId": "auth1",
    "name": "John Smith",
    "papers": [
        {"paperId": "p001", "title": "Paper One"},
        {"paperId": "p002", "title": "Paper Two"},
    ],
}

CITATIONS_RESPONSE = {
    "data": [
        {
            "citingPaper": {
                "paperId": "citing001",
                "title": "Citing Paper",
                "authors": [{"authorId": "ca1", "name": "Citing Author"}],
                "year": 2024,
                "externalIds": {},
            },
            "contexts": ["As shown in [1], the method performs well."],
            "isInfluential": True,
        }
    ],
    "next": None,
}

REFERENCES_RESPONSE = {
    "data": [
        {
            "citedPaper": {
                "paperId": "ref001",
                "title": "Cited Paper",
                "authors": [{"authorId": "ra1", "name": "Cited Author"}],
                "year": 2020,
                "externalIds": {"DOI": "10.1234/cited.2020"},
            },
            "contexts": ["The approach builds on [2]."],
            "isInfluential": False,
        }
    ],
    "next": None,
}

RECOMMENDATIONS_POST_RESPONSE = {
    "recommendedPapers": [
        {"paperId": "rec001", "score": 0.95},
        {"paperId": "rec002", "score": 0.87},
    ]
}

RECOMMENDATIONS_GET_RESPONSE = [
    {"paperId": "rec003", "score": 0.91},
    {"paperId": "rec004", "score": 0.78},
]


@pytest.fixture
def client() -> SemanticScholarClient:
    return SemanticScholarClient()


@pytest.fixture
def authed_client() -> SemanticScholarClient:
    return SemanticScholarClient(api_key="test_key_123")


class TestSemanticScholarClient:
    def test_constructor_defaults(self) -> None:
        c = SemanticScholarClient()
        assert c._api_key == ""
        assert c._rate_limiter._delay == 1.0

    def test_constructor_with_api_key(self) -> None:
        c = SemanticScholarClient(api_key="key123")
        assert c._api_key == "key123"
        assert c._rate_limiter._delay == 0.01

    @pytest.mark.asyncio
    @respx.mock
    async def test_search(self, client: SemanticScholarClient) -> None:
        respx.get("https://api.semanticscholar.org/graph/v1/paper/search").mock(
            return_value=Response(200, json=SEARCH_RESPONSE)
        )
        result = await client.search("machine learning")
        assert isinstance(result, SemanticScholarSearchResult)
        assert result.paper_ids == ["abc123def"]
        assert result.total_count == 1
        assert result.offset == 0
        assert result.next_offset == 10

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_empty(self, client: SemanticScholarClient) -> None:
        respx.get("https://api.semanticscholar.org/graph/v1/paper/search").mock(
            return_value=Response(200, json=SEARCH_EMPTY)
        )
        result = await client.search("nonexistent")
        assert result.paper_ids == []
        assert result.total_count == 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_returns_items(self, client: SemanticScholarClient) -> None:
        respx.get("https://api.semanticscholar.org/graph/v1/paper/search").mock(
            return_value=Response(200, json=SEARCH_RESPONSE)
        )
        result = await client.search("machine learning")
        assert len(result.paper_ids) == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_by_id_parses_paper(self, client: SemanticScholarClient) -> None:
        respx.post("https://api.semanticscholar.org/graph/v1/paper/batch").mock(
            return_value=Response(200, json=SEARCH_RESPONSE["data"])
        )
        items = await client.fetch_by_id(["abc123def"])
        assert len(items) == 1
        item = items[0]
        assert item.id == "abc123def"
        assert item.source == ReferenceSource.semantic_scholar
        assert item.doi == "10.1234/test.2024.001"
        assert item.title == "A Test Paper on Machine Learning"
        assert item.year == 2024
        assert item.extra.get("open_access_pdf") == "https://pdf.example.com/paper.pdf"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_detail(self, client: SemanticScholarClient) -> None:
        respx.get("https://api.semanticscholar.org/graph/v1/paper/detail001").mock(
            return_value=Response(200, json=DETAIL_RESPONSE)
        )
        item = await client.fetch_detail("detail001")
        assert isinstance(item, ReferenceItem)
        assert item.id == "detail001"
        assert item.title == "Detailed Paper Title"
        assert item.abstract == "This is a detailed abstract describing the research."
        assert item.year == 2024
        assert item.journal == "Journal of Machine Learning"
        assert len(item.authors) == 1
        assert item.authors[0].full == "John Smith"
        assert item.authors[0].first == "John"
        assert item.authors[0].last == "Smith"
        assert item.extra.get("citationCount") == 42
        assert item.extra.get("isOpenAccess") is True
        assert item.extra.get("open_access_pdf") == "https://pdf.example.com/paper.pdf"
        assert item.extra.get("tldr") == "A short summary of the paper."
        assert item.extra.get("embedding") == [0.1, 0.2, 0.3, 0.4, 0.5]
        assert item.extra.get("publicationDate") == "2024-01-15"
        assert item.extra.get("fieldsOfStudy") == ["Computer Science"]
        assert item.extra.get("publicationTypes") == ["JournalArticle"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_by_id_batch(self, client: SemanticScholarClient) -> None:
        respx.post("https://api.semanticscholar.org/graph/v1/paper/batch").mock(
            return_value=Response(200, json=BATCH_RESPONSE)
        )
        items = await client.fetch_by_id(["batch001", "batch002"])
        assert len(items) == 2
        assert items[0].id == "batch001"
        assert items[0].title == "Batch Paper One"
        assert items[1].id == "batch002"
        assert items[1].doi == "10.1234/batch.002"

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_by_title(self, client: SemanticScholarClient) -> None:
        respx.get("https://api.semanticscholar.org/graph/v1/paper/search/match").mock(
            return_value=Response(200, json=TITLE_MATCH_RESPONSE)
        )
        item = await client.search_by_title("Exact Title Match")
        assert item is not None
        assert item.id == "titlematch001"
        assert item.title == "Exact Title Match"
        assert item.doi == "10.1234/title.match"

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_by_title_not_found(self, client: SemanticScholarClient) -> None:
        respx.get("https://api.semanticscholar.org/graph/v1/paper/search/match").mock(
            return_value=Response(200, json=TITLE_MATCH_EMPTY)
        )
        item = await client.search_by_title("Nonexistent Title")
        assert item is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_author(self, client: SemanticScholarClient) -> None:
        respx.get("https://api.semanticscholar.org/graph/v1/author/search").mock(
            return_value=Response(200, json=AUTHOR_SEARCH_RESPONSE)
        )
        authors = await client.search_author("John Smith")
        assert len(authors) == 2
        assert authors[0]["authorId"] == "auth1"
        assert authors[0]["name"] == "John Smith"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_author(self, client: SemanticScholarClient) -> None:
        respx.get("https://api.semanticscholar.org/graph/v1/author/auth1").mock(
            return_value=Response(200, json=AUTHOR_DETAIL_RESPONSE)
        )
        author = await client.fetch_author("auth1")
        assert author["authorId"] == "auth1"
        assert author["name"] == "John Smith"
        assert len(author["papers"]) == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_citations(self, client: SemanticScholarClient) -> None:
        respx.get("https://api.semanticscholar.org/graph/v1/paper/detail001/citations").mock(
            return_value=Response(200, json=CITATIONS_RESPONSE)
        )
        entries = await client.get_citations("detail001")
        assert len(entries) == 1
        entry = entries[0]
        assert isinstance(entry, CitationGraphEntry)
        assert entry.is_influential is True
        assert len(entry.contexts) == 1
        assert entry.citing_paper is not None
        assert entry.citing_paper.id == "citing001"
        assert entry.citing_paper.title == "Citing Paper"
        assert entry.cited_paper is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_references(self, client: SemanticScholarClient) -> None:
        respx.get("https://api.semanticscholar.org/graph/v1/paper/detail001/references").mock(
            return_value=Response(200, json=REFERENCES_RESPONSE)
        )
        entries = await client.get_references("detail001")
        assert len(entries) == 1
        entry = entries[0]
        assert isinstance(entry, CitationGraphEntry)
        assert entry.is_influential is False
        assert len(entry.contexts) == 1
        assert entry.cited_paper is not None
        assert entry.cited_paper.id == "ref001"
        assert entry.cited_paper.doi == "10.1234/cited.2020"
        assert entry.citing_paper is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_recommendations_post(self, authed_client: SemanticScholarClient) -> None:
        respx.post("https://api.semanticscholar.org/recommendations/v1/papers").mock(
            return_value=Response(200, json=RECOMMENDATIONS_POST_RESPONSE)
        )
        recs = await authed_client.get_recommendations(
            positive_ids=["abc123def"],
            negative_ids=["oldpaper"],
        )
        assert len(recs) == 2
        assert isinstance(recs[0], PaperRecommendation)
        assert recs[0].paper_id == "rec001"
        assert recs[0].score == 0.95
        assert recs[1].paper_id == "rec002"
        assert recs[1].score == 0.87

    @pytest.mark.asyncio
    async def test_get_recommendations_no_key(self, client: SemanticScholarClient) -> None:
        from openscire.exceptions import ReferenceError

        with pytest.raises(ReferenceError, match="requires an API key"):
            await client.get_recommendations(positive_ids=["abc123def"])

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_recommendations_for_paper(self, client: SemanticScholarClient) -> None:
        respx.get(
            "https://api.semanticscholar.org/recommendations/v1/papers/forpaper/detail001"
        ).mock(return_value=Response(200, json=RECOMMENDATIONS_GET_RESPONSE))
        recs = await client.get_recommendations_for_paper("detail001")
        assert len(recs) == 2
        assert recs[0].paper_id == "rec003"
        assert recs[0].score == 0.91
        assert recs[1].paper_id == "rec004"
        assert recs[1].score == 0.78

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_open_access_pdf(self, client: SemanticScholarClient) -> None:
        respx.get("https://api.semanticscholar.org/graph/v1/paper/detail001").mock(
            return_value=Response(200, json=DETAIL_RESPONSE)
        )
        pdf_content = b"%PDF-1.4 test pdf content"
        respx.get("https://pdf.example.com/paper.pdf").mock(
            return_value=Response(200, content=pdf_content)
        )
        result = await client.fetch_open_access_pdf("detail001")
        assert result == pdf_content

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_open_access_pdf_not_oa(self, client: SemanticScholarClient) -> None:
        not_oa = dict(DETAIL_RESPONSE)
        not_oa["openAccessPdf"] = None
        respx.get("https://api.semanticscholar.org/graph/v1/paper/detail001").mock(
            return_value=Response(200, json=not_oa)
        )
        result = await client.fetch_open_access_pdf("detail001")
        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_embedding(self, client: SemanticScholarClient) -> None:
        respx.get("https://api.semanticscholar.org/graph/v1/paper/detail001").mock(
            return_value=Response(200, json=DETAIL_RESPONSE)
        )
        embedding = await client.fetch_embedding("detail001")
        assert embedding == [0.1, 0.2, 0.3, 0.4, 0.5]

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_embedding_not_available(self, client: SemanticScholarClient) -> None:
        no_emb = dict(DETAIL_RESPONSE)
        no_emb["embedding"] = None
        respx.get("https://api.semanticscholar.org/graph/v1/paper/detail001").mock(
            return_value=Response(200, json=no_emb)
        )
        embedding = await client.fetch_embedding("detail001")
        assert embedding is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_http_error(self, client: SemanticScholarClient) -> None:
        from openscire.exceptions import ReferenceError

        respx.get("https://api.semanticscholar.org/graph/v1/paper/search").mock(
            return_value=Response(429, json={"error": "rate limited"})
        )
        with pytest.raises(ReferenceError, match="Semantic Scholar API error: 429"):
            await client.search("test")

    @pytest.mark.asyncio
    async def test_close(self, client: SemanticScholarClient) -> None:
        await client.close()

    @pytest.mark.asyncio
    async def test_rate_limiter(self) -> None:
        from openscire.references.bridges.semantic_scholar import SemanticScholarRateLimiter

        limiter = SemanticScholarRateLimiter(api_key="test")
        assert limiter._delay == 0.01
        await limiter.wait()
        t1 = time.monotonic()
        await limiter.wait()
        t2 = time.monotonic()
        assert t2 - t1 >= 0.009

    @pytest.mark.asyncio
    async def test_rate_limiter_no_key(self) -> None:
        from openscire.references.bridges.semantic_scholar import SemanticScholarRateLimiter

        limiter = SemanticScholarRateLimiter()
        assert limiter._delay == 1.0

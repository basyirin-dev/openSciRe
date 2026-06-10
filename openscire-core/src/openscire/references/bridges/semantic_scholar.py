# SPDX-License-Identifier: Apache-2.0

"""Semantic Scholar Graph API client (search, citations, recommendations, embeddings).

Uses the S2 Graph API (v1) for paper/author lookup and citation traversal,
and the Recommendations API (v1) for paper recommendations.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from openscire.exceptions import ReferenceError
from openscire.references.models import (
    CitationGraphEntry,
    PaperRecommendation,
    ReferenceAuthor,
    ReferenceItem,
    ReferenceSource,
    SemanticScholarSearchResult,
)

logger = logging.getLogger(__name__)

LIGHT_FIELDS = "paperId,title,authors,year,externalIds,openAccessPdf"
FULL_FIELDS = (
    "paperId,title,authors,abstract,year,venue,externalIds,"
    "citationCount,referenceCount,influentialCitationCount,"
    "isOpenAccess,openAccessPdf,embedding,publicationTypes,"
    "fieldsOfStudy,s2FieldsOfStudy,tldr,publicationDate,journal,url"
)


class SemanticScholarRateLimiter:
    """Rate limiter for Semantic Scholar API requests.

    Without API key: 1 req/s (shared pool).
    With API key: 100 req/s (dedicated pool).
    """

    def __init__(self, api_key: str = "") -> None:
        self._delay = 0.01 if api_key else 1.0
        self._last = 0.0

    async def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        if elapsed < self._delay:
            await asyncio.sleep(self._delay - elapsed)
        self._last = time.monotonic()


class SemanticScholarClient:
    """Standalone client for the Semantic Scholar Graph & Recommendations APIs.

    Follows the same pattern as ArXivClient and PubMedBridge — does not
    extend ReferenceBridge (S2 is a paper-graph search engine, not a
    collection/reference manager).
    """

    GRAPH_API = "https://api.semanticscholar.org/graph/v1"
    REC_API = "https://api.semanticscholar.org/recommendations/v1"

    def __init__(self, api_key: str = "", timeout: int = 30) -> None:
        self._api_key = api_key
        self._rate_limiter = SemanticScholarRateLimiter(api_key=api_key)
        headers = {}
        if api_key:
            headers["x-api-key"] = api_key
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            headers=headers,
        )

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:  # noqa: ANN401
        await self._rate_limiter.wait()
        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise ReferenceError(
                f"Semantic Scholar API error: {e.response.status_code} {e.response.text[:200]}",
                source="semantic_scholar",
            ) from e
        except httpx.RequestError as e:
            raise ReferenceError(
                f"Semantic Scholar request failed: {e}",
                source="semantic_scholar",
            ) from e

    async def _post(
        self,
        url: str,
        json_data: dict[str, Any],  # noqa: ANN401
        params: dict[str, Any] | None = None,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        await self._rate_limiter.wait()
        try:
            response = await self._client.post(url, json=json_data, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise ReferenceError(
                f"Semantic Scholar API error: {e.response.status_code} {e.response.text[:200]}",
                source="semantic_scholar",
            ) from e
        except httpx.RequestError as e:
            raise ReferenceError(
                f"Semantic Scholar request failed: {e}",
                source="semantic_scholar",
            ) from e

    def _parse_paper(self, data: dict[str, Any]) -> ReferenceItem:
        authors: list[ReferenceAuthor] = []
        for a in data.get("authors") or []:
            name = a.get("name", "")
            parts = name.rsplit(" ", 1)
            if len(parts) == 2:
                authors.append(ReferenceAuthor(full=name, first=parts[0], last=parts[1]))
            else:
                authors.append(ReferenceAuthor(full=name))

        external_ids = data.get("externalIds") or {}
        doi: str = external_ids.get("DOI", "")

        extra: dict[str, Any] = {}
        for key in (
            "citationCount",
            "referenceCount",
            "influentialCitationCount",
            "isOpenAccess",
            "publicationDate",
            "fieldsOfStudy",
            "s2FieldsOfStudy",
            "publicationTypes",
        ):
            if key in data and data[key] is not None:
                extra[key] = data[key]

        if data.get("openAccessPdf"):
            extra["open_access_pdf"] = data["openAccessPdf"].get("url", "")

        if data.get("tldr"):
            extra["tldr"] = data["tldr"].get("text", "")

        if data.get("embedding"):
            embedding = data["embedding"]
            extra["embedding"] = embedding.get("vector", [])

        journal = data.get("venue") or ""
        if not journal and data.get("journal"):
            journal = data["journal"].get("name", "")

        return ReferenceItem(
            id=data.get("paperId", ""),
            source=ReferenceSource.semantic_scholar,
            doi=doi,
            title=(data.get("title") or "").strip(),
            authors=authors,
            journal=journal,
            year=data.get("year"),
            abstract=data.get("abstract") or "",
            url=data.get("url") or "",
            extra=extra,
        )

    async def search(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        fields: str = LIGHT_FIELDS,
    ) -> SemanticScholarSearchResult:
        """Search papers by query string.

        Returns a SemanticScholarSearchResult with paper IDs and pagination metadata.
        """
        params: dict[str, Any] = {
            "query": query,
            "limit": limit,
            "offset": offset,
            "fields": fields,
        }
        data = await self._get(f"{self.GRAPH_API}/paper/search", params=params)
        papers = data.get("data") or []
        return SemanticScholarSearchResult(
            paper_ids=[p.get("paperId", "") for p in papers],
            total_count=data.get("total", len(papers)),
            offset=offset,
            next_offset=data.get("next"),
        )

    async def fetch_detail(
        self,
        paper_id: str,
        fields: str = FULL_FIELDS,
    ) -> ReferenceItem:
        """Fetch a single paper by S2 PaperId, ArXiv ID, DOI, or PMID."""
        data = await self._get(
            f"{self.GRAPH_API}/paper/{paper_id}",
            params={"fields": fields},
        )
        return self._parse_paper(data)

    async def fetch_by_id(
        self,
        paper_ids: list[str],
        fields: str = LIGHT_FIELDS,
    ) -> list[ReferenceItem]:
        """Batch lookup papers by their IDs (S2 PaperId, ArXiv, DOI, PMID).

        Uses POST /graph/v1/paper/batch.
        """
        data = await self._post(
            f"{self.GRAPH_API}/paper/batch",
            json_data={"ids": paper_ids},
            params={"fields": fields},
        )
        raw_papers: list[dict[str, Any]] = data if isinstance(data, list) else data.get("data", [])
        return [self._parse_paper(p) for p in raw_papers]

    async def search_by_title(
        self,
        query: str,
        fields: str = LIGHT_FIELDS,
    ) -> ReferenceItem | None:
        """Search for a paper by exact title match."""
        data = await self._get(
            f"{self.GRAPH_API}/paper/search/match",
            params={"query": query, "fields": fields},
        )
        papers = data.get("data") or []
        if not papers:
            return None
        return self._parse_paper(papers[0])

    async def search_author(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search authors by name.

        Returns raw author dicts with authorId, name, etc.
        """
        data = await self._get(
            f"{self.GRAPH_API}/author/search",
            params={"query": query, "limit": limit},
        )
        return data.get("data") or []

    async def fetch_author(
        self,
        author_id: str,
        fields: str = "name,papers",
    ) -> dict[str, Any]:
        """Fetch author details by author ID.

        Returns raw dict with name, papers list, etc.
        """
        return await self._get(  # type: ignore[no-any-return]
            f"{self.GRAPH_API}/author/{author_id}",
            params={"fields": fields},
        )

    async def get_citations(
        self,
        paper_id: str,
        limit: int = 100,
        offset: int = 0,
        fields: str = LIGHT_FIELDS,
    ) -> list[CitationGraphEntry]:
        """Get papers that cite the given paper."""
        data = await self._get(
            f"{self.GRAPH_API}/paper/{paper_id}/citations",
            params={"limit": limit, "offset": offset, "fields": fields},
        )
        entries: list[CitationGraphEntry] = []
        for item in data.get("data") or []:
            citing = item.get("citingPaper")
            entries.append(
                CitationGraphEntry(
                    citing_paper=self._parse_paper(citing) if citing else None,
                    contexts=item.get("contexts") or [],
                    is_influential=item.get("isInfluential", False),
                )
            )
        return entries

    async def get_references(
        self,
        paper_id: str,
        limit: int = 100,
        offset: int = 0,
        fields: str = LIGHT_FIELDS,
    ) -> list[CitationGraphEntry]:
        """Get papers that the given paper cites."""
        data = await self._get(
            f"{self.GRAPH_API}/paper/{paper_id}/references",
            params={"limit": limit, "offset": offset, "fields": fields},
        )
        entries: list[CitationGraphEntry] = []
        for item in data.get("data") or []:
            cited = item.get("citedPaper")
            entries.append(
                CitationGraphEntry(
                    cited_paper=self._parse_paper(cited) if cited else None,
                    contexts=item.get("contexts") or [],
                    is_influential=item.get("isInfluential", False),
                )
            )
        return entries

    async def get_recommendations(
        self,
        positive_ids: list[str],
        negative_ids: list[str] | None = None,
        limit: int = 100,
    ) -> list[PaperRecommendation]:
        """Get paper recommendations based on a set of positive (and optionally negative) paper IDs.

        Requires an API key. Raises ReferenceError if no API key is configured.
        Uses POST /recommendations/v1/papers/.
        """
        if not self._api_key:
            raise ReferenceError(
                "Semantic Scholar recommendations POST endpoint requires an API key. "
                "Pass api_key to the constructor or use get_recommendations_for_paper().",
                source="semantic_scholar",
            )
        body: dict[str, Any] = {
            "positivePaperIds": positive_ids,
            "limit": limit,
        }
        if negative_ids:
            body["negativePaperIds"] = negative_ids
        data = await self._post(f"{self.REC_API}/papers", json_data=body)
        raw = data.get("recommendedPapers") or []
        return [
            PaperRecommendation(paper_id=r.get("paperId", ""), score=r.get("score", 0.0))
            for r in raw
        ]

    async def get_recommendations_for_paper(
        self,
        paper_id: str,
        limit: int = 100,
    ) -> list[PaperRecommendation]:
        """Get recommendations for a single paper.

        Uses GET /recommendations/v1/papers/forpaper/{paper_id}.
        Does not require an API key.
        """
        data = await self._get(
            f"{self.REC_API}/papers/forpaper/{paper_id}",
            params={"limit": limit},
        )
        raw = data if isinstance(data, list) else data.get("recommendedPapers", [])
        return [
            PaperRecommendation(paper_id=r.get("paperId", ""), score=r.get("score", 0.0))
            for r in raw
        ]

    async def fetch_open_access_pdf(self, paper_id: str) -> bytes | None:
        """Download the Open Access PDF for a paper, if available.

        Returns raw PDF bytes, or None if the paper is not OA.
        """
        detail = await self.fetch_detail(paper_id, fields="openAccessPdf")
        pdf_url = detail.extra.get("open_access_pdf", "")
        if not pdf_url:
            return None
        await self._rate_limiter.wait()
        try:
            response = await self._client.get(pdf_url)
            response.raise_for_status()
            return response.content
        except httpx.RequestError:
            logger.warning("Failed to download OA PDF from %s", pdf_url)
            return None

    async def fetch_embedding(self, paper_id: str) -> list[float] | None:
        """Fetch the SPECTER embedding vector for a paper.

        Returns the embedding vector as a list of floats, or None if not available.
        """
        detail = await self.fetch_detail(paper_id, fields="embedding")
        embedding = detail.extra.get("embedding")
        if not embedding:
            return None
        return embedding  # type: ignore[no-any-return]

    async def close(self) -> None:
        await self._client.aclose()

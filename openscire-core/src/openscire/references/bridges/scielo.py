# SPDX-License-Identifier: Apache-2.0

"""SciELO (Scientific Electronic Library Online) API client.

SciELO is the primary open access platform for scholarly journals in
Latin America, the Caribbean, Spain, Portugal, and South Africa.
It indexes 1,800+ peer-reviewed journals and 900K+ articles.

API: https://articlemeta.scielo.org/api/v1/
Free, no authentication required.  See https://scielo.readthedocs.io/ for docs.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import Any

import httpx

from openscire.exceptions import ReferenceError
from openscire.references.models import (
    ReferenceAuthor,
    ReferenceItem,
    ReferenceSource,
)

logger = logging.getLogger(__name__)


class ScieloRateLimiter:
    """Rate limiter for SciELO API requests.

    SciELO has no documented rate limit.  A conservative 0.5s delay
    is applied between requests.
    """

    def __init__(self) -> None:
        self._delay = 0.5
        self._last = 0.0

    async def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        if elapsed < self._delay:
            await asyncio.sleep(self._delay - elapsed)
        self._last = time.monotonic()


class ScieloClient:
    """Standalone client for the SciELO ArticleMeta API.

    Provides search and detail retrieval for articles, journals,
    issues, and collections.  No authentication required.
    """

    BASE_URL = "https://articlemeta.scielo.org/api/v1"

    def __init__(self, timeout: int = 30) -> None:
        self._rate_limiter = ScieloRateLimiter()
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )

    async def _get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> Any:  # noqa: ANN401
        await self._rate_limiter.wait()
        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise ReferenceError(
                f"SciELO API error: {e.response.status_code} {e.response.text[:200]}",
                source="scielo",
            ) from e
        except httpx.RequestError as e:
            raise ReferenceError(
                f"SciELO request failed: {e}",
                source="scielo",
            ) from e

    def _parse_article(self, data: dict[str, Any]) -> ReferenceItem:
        authors: list[ReferenceAuthor] = []
        for a in data.get("authors") or []:
            name = a.get("name", "")
            surname = a.get("surname", "")
            full = f"{name} {surname}".strip()
            if not full:
                full = name or ""
            if full:
                parts = full.rsplit(" ", 1)
                if len(parts) == 2:
                    authors.append(ReferenceAuthor(full=full, first=parts[0], last=parts[1]))
                else:
                    authors.append(ReferenceAuthor(full=full))

        article_id = data.get("code") or data.get("pid") or ""
        doi_raw = data.get("doi", "")
        doi = doi_raw.replace("https://doi.org/", "") if doi_raw else ""
        title = (data.get("title") or "").strip()
        journal = (data.get("journal_title") or data.get("journal") or "").strip()
        year_raw = data.get("publication_year") or data.get("year")
        year: int | None = None
        if year_raw is not None:
            with contextlib.suppress(ValueError, TypeError):
                year = int(year_raw)
        abstract = (data.get("abstract") or "").strip()
        keywords: list[str] = []
        for kw in data.get("keywords") or []:
            if isinstance(kw, str) and kw.strip():
                keywords.append(kw.strip())
            elif isinstance(kw, dict):
                text = kw.get("text", "").strip()
                if text:
                    keywords.append(text)

        extra: dict[str, Any] = {}
        collection = data.get("collection")
        if collection:
            extra["collection"] = collection
        language = data.get("language")
        if language:
            extra["original_language"] = language
        issue_data = data.get("issue") or {}
        if issue_data:
            extra["issue"] = issue_data
        processing_date = data.get("processing_date")
        if processing_date:
            extra["processing_date"] = processing_date

        original_language = language or ""

        return ReferenceItem(
            id=article_id,
            source=ReferenceSource.scielo,
            doi=doi,
            title=title,
            authors=authors,
            journal=journal,
            year=year,
            abstract=abstract,
            keywords=keywords,
            original_language=original_language,
            extra=extra,
        )

    async def search(
        self,
        query: str,
        collection: str = "",
        limit: int = 20,
        offset: int = 0,
    ) -> list[ReferenceItem]:
        """Search articles by keyword.

        Args:
            query: Search query string.
            collection: SciELO collection code (e.g., "scl" for Brazil,
                "esp" for Spain).  Empty string searches all collections.
            limit: Maximum results (max 50).
            offset: Result offset for pagination.

        Returns:
            List of ReferenceItem for matching articles.
        """
        params: dict[str, Any] = {
            "q": query,
            "limit": min(limit, 50),
            "offset": offset,
        }
        if collection:
            params["collection"] = collection

        data = await self._get(f"{self.BASE_URL}/article/", params=params)
        articles = (
            data.get("objects") or data.get("results") or
            (data if isinstance(data, list) else [])
        )
        return [self._parse_article(a) for a in articles]

    async def fetch_article(self, article_id: str) -> ReferenceItem:
        """Fetch a single article by SciELO PID or code."""
        data = await self._get(
            f"{self.BASE_URL}/article/",
            params={"code": article_id},
        )
        return self._parse_article(data)

    async def fetch_by_doi(self, doi: str) -> ReferenceItem | None:
        """Fetch an article by DOI."""
        cleaned = doi.replace("https://doi.org/", "").lower()
        try:
            data = await self._get(
                f"{self.BASE_URL}/article/",
                params={"doi": cleaned},
            )
            return self._parse_article(data)
        except ReferenceError:
            return None

    async def search_by_title(self, title: str) -> ReferenceItem | None:
        """Search for an article by exact title. Returns first match or None."""
        results = await self.search(title, limit=5)
        title_lower = title.lower().strip()
        for article in results:
            if article.title.lower().strip() == title_lower:
                return article
        return results[0] if results else None

    async def fetch_by_issn(
        self,
        issn: str,
        limit: int = 50,
    ) -> list[ReferenceItem]:
        """Fetch articles from a journal by ISSN."""
        data = await self._get(
            f"{self.BASE_URL}/article/",
            params={"issn": issn, "limit": min(limit, 100)},
        )
        articles = (
            data.get("objects") or data.get("results") or
            (data if isinstance(data, list) else [])
        )
        return [self._parse_article(a) for a in articles]

    async def list_collections(self) -> list[dict[str, Any]]:
        """List available SciELO collections (countries/regions).

        Returns a list of dicts with collection code, name, and metadata.
        """
        data = await self._get(f"{self.BASE_URL}/collection/")
        return data if isinstance(data, list) else data.get("objects", [])

    async def close(self) -> None:
        await self._client.aclose()

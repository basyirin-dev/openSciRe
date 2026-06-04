# SPDX-License-Identifier: Apache-2.0

"""OpenAlex API client (search, works, authors, institutions, topics).

OpenAlex is a free/open index of scholarly works, authors, institutions,
and research topics.  See https://docs.openalex.org/ for API docs.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from openscire.exceptions import ReferenceError
from openscire.references.models import (
    OpenAlexSearchResult,
    ReferenceAuthor,
    ReferenceItem,
    ReferenceSource,
)

logger = logging.getLogger(__name__)

LIGHT_SELECT = "id,doi,display_name,publication_year,cited_by_count,open_access"
FULL_SELECT = (
    "id,doi,display_name,authorships,publication_date,publication_year,"
    "cited_by_count,referenced_works,related_works,abstract_inverted_index,"
    "open_access,primary_location,topics,concepts,keywords,biblio,"
    "type,language,ids,counts_by_year,fwci"
)


class OpenAlexRateLimiter:
    """Rate limiter for OpenAlex API requests.

    OpenAlex uses a daily dollar budget ($1/day with free API key).
    Singleton fetches are free, but list/search calls consume budget.
    This limiter uses a conservative time-based delay; users can check
    remaining budget via check_rate_limit().
    """

    def __init__(self, api_key: str = "") -> None:
        self._delay = 0.1 if api_key else 3.0
        self._last = 0.0

    async def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        if elapsed < self._delay:
            await asyncio.sleep(self._delay - elapsed)
        self._last = time.monotonic()


class OpenAlexClient:
    """Standalone client for the OpenAlex API.

    Provides search, detail, and batch lookups for works, authors,
    institutions, and topics.  Singleton fetches are free; list and
    search calls consume the daily budget ($1/day with free API key).
    """

    BASE_URL = "https://api.openalex.org"

    def __init__(self, api_key: str = "", email: str = "", timeout: int = 30) -> None:
        self._api_key = api_key
        self._email = email
        self._rate_limiter = OpenAlexRateLimiter(api_key=api_key)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )

    async def _get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> Any:  # noqa: ANN401
        if params is None:
            params = {}
        if self._api_key:
            params["api_key"] = self._api_key
        await self._rate_limiter.wait()
        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise ReferenceError(
                f"OpenAlex API error: {e.response.status_code} {e.response.text[:200]}",
                source="openalex",
            ) from e
        except httpx.RequestError as e:
            raise ReferenceError(
                f"OpenAlex request failed: {e}",
                source="openalex",
            ) from e

    @staticmethod
    def decode_abstract(inverted_index: dict[str, list[int]] | None) -> str:
        """Decode an OpenAlex abstract_inverted_index to plain text.

        OpenAlex stores abstracts as an inverted index mapping words to
        their positional indices.  This method reconstructs the original
        text by sorting words by their positions.
        """
        if not inverted_index:
            return ""
        word_positions: list[tuple[str, int]] = [
            (word, pos)
            for word, positions in inverted_index.items()
            for pos in positions
        ]
        word_positions.sort(key=lambda x: x[1])
        return " ".join(wp[0] for wp in word_positions)

    def _parse_work(self, data: dict[str, Any]) -> ReferenceItem:
        oa_id = data.get("id", "")
        if oa_id.startswith("https://openalex.org/"):
            work_id = oa_id[len("https://openalex.org/"):]
        else:
            work_id = oa_id

        ids = data.get("ids") or {}
        doi_raw = ids.get("doi", "")
        doi = doi_raw.replace("https://doi.org/", "") if doi_raw else ""

        authors: list[ReferenceAuthor] = []
        authorships_data: list[dict[str, Any]] = []
        for a in data.get("authorships") or []:
            author_data = a.get("author") or {}
            name = author_data.get("display_name", "")
            parts = name.rsplit(" ", 1)
            if len(parts) == 2:
                authors.append(ReferenceAuthor(full=name, first=parts[0], last=parts[1]))
            else:
                authors.append(ReferenceAuthor(full=name))

            institutions_raw = a.get("institutions") or []
            insts = [
                {
                    "id": i.get("id"),
                    "name": i.get("display_name"),
                    "ror": i.get("ror"),
                    "country_code": i.get("country_code"),
                }
                for i in institutions_raw
            ]
            authorships_data.append({
                "author_id": author_data.get("id"),
                "author_name": name,
                "orcid": author_data.get("orcid"),
                "institutions": insts,
                "is_corresponding": a.get("is_corresponding"),
            })

        abstract = self.decode_abstract(data.get("abstract_inverted_index"))

        primary_location = data.get("primary_location") or {}
        source = primary_location.get("source") or {}
        journal: str = source.get("display_name") or ""

        extra: dict[str, Any] = {}
        for key in (
            "cited_by_count", "fwci", "is_retracted", "language",
            "type", "publication_date", "ids", "counts_by_year",
            "referenced_works", "related_works", "is_oa",
        ):
            if key in data and data[key] is not None:
                extra[key] = data[key]

        if "topics" in data:
            extra["topics"] = [
                {"id": t.get("id"), "name": t.get("display_name"), "score": t.get("score")}
                for t in data["topics"]
            ]

        if "concepts" in data:
            extra["concepts"] = [
                {"id": c.get("id"), "name": c.get("display_name"), "score": c.get("score")}
                for c in data["concepts"]
            ]

        if "open_access" in data:
            extra["open_access"] = data["open_access"]

        if primary_location:
            extra["primary_location"] = {
                "landing_page_url": primary_location.get("landing_page_url"),
                "pdf_url": primary_location.get("pdf_url"),
                "is_oa": primary_location.get("is_oa"),
                "license": primary_location.get("license"),
            }

        if "keywords" in data:
            extra["keywords_data"] = [
                {"id": k.get("id"), "name": k.get("display_name"), "score": k.get("score")}
                for k in data["keywords"]
            ]

        if authorships_data:
            extra["authorships"] = authorships_data

        volume = ""
        issue = ""
        pages = ""
        if "biblio" in data:
            biblio = data["biblio"]
            volume = biblio.get("volume") or ""
            issue = biblio.get("issue") or ""
            fp = biblio.get("first_page") or ""
            lp = biblio.get("last_page") or ""
            pages = f"{fp}-{lp}" if fp and lp else fp or ""

        keywords_list = data.get("keywords") or []
        keywords = [
            k.get("display_name", "") for k in keywords_list
            if k.get("display_name")
        ]
        for t in data.get("topics") or []:
            name = t.get("display_name", "")
            if name:
                keywords.append(name)
        for c in data.get("concepts") or []:
            name = c.get("display_name", "")
            if name:
                keywords.append(name)

        return ReferenceItem(
            id=work_id,
            source=ReferenceSource.openalex,
            doi=doi,
            title=(data.get("display_name") or "").strip(),
            authors=authors,
            journal=journal,
            year=data.get("publication_year"),
            volume=volume,
            issue=issue,
            pages=pages,
            abstract=abstract,
            url=oa_id,
            keywords=keywords,
            extra=extra,
        )

    async def search_works(
        self,
        query: str,
        filters: str | None = None,
        sort: str | None = None,
        page: int = 1,
        per_page: int = 25,
        select: str | None = LIGHT_SELECT,
    ) -> OpenAlexSearchResult:
        """Full-text search for works.

        Costs ~$0.001 per call (search endpoint pricing).
        """
        params: dict[str, Any] = {
            "search": query,
            "page": page,
            "per-page": per_page,
        }
        if filters:
            params["filter"] = filters
        if sort:
            params["sort"] = sort
        if select:
            params["select"] = select

        data = await self._get(f"{self.BASE_URL}/works", params=params)
        meta = data.get("meta") or {}
        results = data.get("results") or []
        return OpenAlexSearchResult(
            work_ids=[w.get("id", "") for w in results],
            total_count=meta.get("count", 0),
            page=page,
            per_page=per_page,
        )

    async def list_works(
        self,
        filters: str,
        sort: str | None = None,
        page: int = 1,
        per_page: int = 25,
        select: str | None = LIGHT_SELECT,
    ) -> OpenAlexSearchResult:
        """Filter-based listing of works (no full-text search).

        Costs ~$0.0001 per call (list/filter pricing).
        """
        params: dict[str, Any] = {
            "filter": filters,
            "page": page,
            "per-page": per_page,
        }
        if sort:
            params["sort"] = sort
        if select:
            params["select"] = select

        data = await self._get(f"{self.BASE_URL}/works", params=params)
        meta = data.get("meta") or {}
        results = data.get("results") or []
        return OpenAlexSearchResult(
            work_ids=[w.get("id", "") for w in results],
            total_count=meta.get("count", 0),
            page=page,
            per_page=per_page,
        )

    async def fetch_work(
        self,
        work_id: str,
        select: str | None = FULL_SELECT,
    ) -> ReferenceItem:
        """Fetch a single work by OpenAlex ID, DOI, or other identifier.

        Singleton fetch — free (no budget consumed).
        """
        data = await self._get(
            f"{self.BASE_URL}/works/{work_id}",
            params={"select": select} if select else None,
        )
        return self._parse_work(data)

    async def fetch_works_batch(
        self,
        work_ids: list[str],
        select: str | None = LIGHT_SELECT,
    ) -> list[ReferenceItem]:
        """Batch-fetch multiple works using the OpenAlex ID filter.

        Uses piped OR filter: filter=openalex_id:id1|id2|...
        OpenAlex supports up to 100 values per filter.
        """
        pipe_ids = "|".join(work_ids)
        result = await self.list_works(
            filters=f"openalex_id:{pipe_ids}",
            select=select,
            per_page=min(len(work_ids), 100),
        )
        if not result.work_ids:
            return []
        ids_param = "|".join(result.work_ids)
        params: dict[str, Any] = {
            "filter": f"openalex_id:{ids_param}",
            "per-page": min(len(work_ids), 100),
        }
        if select:
            params["select"] = select
        data = await self._get(f"{self.BASE_URL}/works", params=params)
        results = data.get("results") or []
        return [self._parse_work(w) for w in results]

    async def search_authors(
        self,
        query: str,
        page: int = 1,
        per_page: int = 25,
    ) -> list[dict[str, Any]]:
        """Search authors by name.

        Returns raw author dicts from OpenAlex.
        """
        data = await self._get(
            f"{self.BASE_URL}/authors",
            params={"search": query, "page": page, "per-page": per_page},
        )
        return data.get("results") or []

    async def fetch_author(
        self,
        author_id: str,
        select: str | None = None,
    ) -> dict[str, Any]:
        """Fetch author details by OpenAlex Author ID or ORCID.

        Singleton fetch — free.
        """
        params = {}
        if select:
            params["select"] = select
        return await self._get(  # type: ignore[no-any-return]
            f"{self.BASE_URL}/authors/{author_id}",
            params=params or None,
        )

    async def search_institutions(
        self,
        query: str,
        page: int = 1,
        per_page: int = 25,
    ) -> list[dict[str, Any]]:
        """Search institutions by name."""
        data = await self._get(
            f"{self.BASE_URL}/institutions",
            params={"search": query, "page": page, "per-page": per_page},
        )
        return data.get("results") or []

    async def fetch_institution(
        self,
        institution_id: str,
    ) -> dict[str, Any]:
        """Fetch institution details by OpenAlex ID or ROR ID.

        Singleton fetch — free.
        """
        return await self._get(  # type: ignore[no-any-return]
            f"{self.BASE_URL}/institutions/{institution_id}",
        )

    async def search_topics(
        self,
        query: str,
        page: int = 1,
        per_page: int = 25,
    ) -> list[dict[str, Any]]:
        """Search topics by name."""
        data = await self._get(
            f"{self.BASE_URL}/topics",
            params={"search": query, "page": page, "per-page": per_page},
        )
        return data.get("results") or []

    async def fetch_topic(
        self,
        topic_id: str,
    ) -> dict[str, Any]:
        """Fetch a topic with its hierarchy (subfield → field → domain).

        Singleton fetch — free.
        """
        params = {
            "select": "id,display_name,description,works_count,"
            "cited_by_count,subfield,field,domain",
        }
        return await self._get(  # type: ignore[no-any-return]
            f"{self.BASE_URL}/topics/{topic_id}",
            params=params,
        )

    async def autocomplete(
        self,
        entity_type: str,
        query: str,
    ) -> list[dict[str, Any]]:
        """Autocomplete for any entity type.

        Supported types: works, authors, sources, institutions, topics,
        keywords, publishers, funders.
        """
        data = await self._get(
            f"{self.BASE_URL}/autocomplete/{entity_type}",
            params={"q": query},
        )
        return data.get("results") or []

    async def get_author_works(
        self,
        author_id: str,
        page: int = 1,
        per_page: int = 25,
        select: str | None = LIGHT_SELECT,
    ) -> OpenAlexSearchResult:
        """Get works authored by a specific author."""
        return await self.list_works(
            filters=f"authorships.author.id:{author_id}",
            page=page,
            per_page=per_page,
            select=select,
        )

    async def get_related_works(
        self,
        work_id: str,
        page: int = 1,
        per_page: int = 25,
        select: str | None = LIGHT_SELECT,
    ) -> OpenAlexSearchResult:
        """Get works related to a specific work."""
        return await self.list_works(
            filters=f"related_works:{work_id}",
            page=page,
            per_page=per_page,
            select=select,
        )

    async def fetch_citation_count(self, work_id: str) -> int:
        """Fetch citation count for a work.

        Free singleton call — uses ?select=cited_by_count for efficiency.
        """
        data = await self._get(
            f"{self.BASE_URL}/works/{work_id}",
            params={"select": "cited_by_count"},
        )
        return data.get("cited_by_count", 0)  # type: ignore[no-any-return]

    async def check_rate_limit(self) -> dict[str, Any]:
        """Check remaining daily budget.

        Calls the /rate-limit endpoint which returns budget info.
        Requires an API key.
        """
        return await self._get(f"{self.BASE_URL}/rate-limit")  # type: ignore[no-any-return]

    async def close(self) -> None:
        await self._client.aclose()

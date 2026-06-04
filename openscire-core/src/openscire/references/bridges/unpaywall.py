# SPDX-License-Identifier: Apache-2.0

"""Unpaywall API client for Open Access PDF resolution.

Unpaywall resolves DOIs to their best available Open Access full-text
locations.  This client does NOT extend ReferenceBridge — Unpaywall is
an OA-resolution service, not a paper metadata source.

See https://unpaywall.org/products/api for API docs.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import Any

import httpx

from openscire.exceptions import ReferenceError
from openscire.references.models import OALocation, UnpaywallResult

logger = logging.getLogger(__name__)


class UnpaywallRateLimiter:
    """Rate limiter for Unpaywall API requests.

    Unpaywall has a soft rate limit of ~100k requests/day.
    A conservative 0.1s delay is applied between requests.
    """

    def __init__(self) -> None:
        self._delay = 0.1
        self._last = 0.0

    async def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        if elapsed < self._delay:
            await asyncio.sleep(self._delay - elapsed)
        self._last = time.monotonic()


class UnpaywallClient:
    """Standalone client for the Unpaywall API v2.

    Unpaywall resolves DOIs to their best available Open Access full-text
    locations.  An email address is mandatory for API access.

    This client can optionally hold references to OpenAlex and Semantic Scholar
    clients for a fallback chain when Unpaywall has no OA location for a DOI.
    """

    BASE_URL = "https://api.unpaywall.org/v2"

    def __init__(
        self,
        email: str,
        timeout: int = 30,
        max_concurrent: int = 5,
        fallback_clients: dict[str, Any] | None = None,
    ) -> None:
        self._email = email
        self._rate_limiter = UnpaywallRateLimiter()
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._fallback_clients = fallback_clients or {}
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
        params.setdefault("email", self._email)
        await self._rate_limiter.wait()
        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise ReferenceError(
                f"Unpaywall API error: {e.response.status_code} {e.response.text[:200]}",
                source="unpaywall",
            ) from e
        except httpx.RequestError as e:
            raise ReferenceError(
                f"Unpaywall request failed: {e}",
                source="unpaywall",
            ) from e

    def _parse_oa_location(self, data: dict[str, Any] | None) -> OALocation | None:
        if not data:
            return None
        return OALocation(
            url_for_pdf=data.get("url_for_pdf"),
            url_for_landing_page=data.get("url_for_landing_page", ""),
            url=data.get("url", ""),
            host_type=data.get("host_type", ""),
            is_best=data.get("is_best", False),
            license=data.get("license"),
            version=data.get("version", ""),
            oa_date=data.get("oa_date"),
            repository_institution=data.get("repository_institution"),
            endpoint_id=data.get("endpoint_id"),
            pmh_id=data.get("pmh_id"),
        )

    def _parse_result(self, data: dict[str, Any]) -> UnpaywallResult:
        raw_locations = data.get("oa_locations") or []
        oa_locations = [
            self._parse_oa_location(loc)
            for loc in raw_locations
        ]
        best_raw = data.get("best_oa_location")
        first_raw = data.get("first_oa_location")

        published_date = data.get("published_date", "")
        year: int | None = None
        if published_date and len(published_date) >= 4:
            with contextlib.suppress(ValueError):
                year = int(published_date[:4])

        pdf_url = ""
        best = self._parse_oa_location(best_raw)
        first = self._parse_oa_location(first_raw)
        if best and best.url_for_pdf:
            pdf_url = best.url_for_pdf
        elif first and first.url_for_pdf:
            pdf_url = first.url_for_pdf

        return UnpaywallResult(
            doi=data.get("doi", ""),
            doi_url=data.get("doi_url", ""),
            title=data.get("title", ""),
            genre=data.get("genre", ""),
            is_oa=data.get("is_oa", False),
            oa_status=data.get("oa_status", ""),
            has_repository_copy=data.get("has_repository_copy", False),
            best_oa_location=best,
            first_oa_location=first,
            oa_locations=[loc for loc in oa_locations if loc is not None],
            journal_name=data.get("journal_name", ""),
            journal_issns=data.get("journal_issns", ""),
            journal_issn_l=data.get("journal_issn_l", ""),
            journal_is_oa=data.get("journal_is_oa", False),
            journal_is_in_doaj=data.get("journal_is_in_doaj", False),
            publisher=data.get("publisher", ""),
            published_date=published_date,
            year=year,
            pdf_url=pdf_url,
            data_standard=data.get("data_standard", 2),
            updated=data.get("updated", ""),
        )

    async def fetch_by_doi(
        self,
        doi: str,
    ) -> UnpaywallResult:
        """Fetch OA information for a single DOI.

        This is the primary Unpaywall endpoint.  Returns an UnpaywallResult
        with all OA locations for the given DOI.
        """
        data = await self._get(f"{self.BASE_URL}/{doi}")
        return self._parse_result(data)

    async def get_pdf_url(self, doi: str) -> str | None:
        """Quickly retrieve the best OA PDF URL for a DOI, or None."""
        result = await self.fetch_by_doi(doi)
        return result.pdf_url or None

    async def search_by_title(
        self,
        query: str,
    ) -> list[UnpaywallResult]:
        """Search for DOIs by title fragment.

        Unpaywall does not have a dedicated title-search endpoint, so we
        attempt a direct DOI lookup with the query as a DOI.  This method
        exists for API consistency with other clients.

        Returns a list with at most one result (if the query is a valid DOI).
        """
        cleaned = query.strip().lower()
        if not cleaned.startswith("10."):
            return []
        try:
            result = await self.fetch_by_doi(cleaned)
            return [result]
        except ReferenceError:
            return []

    async def fetch_batch(
        self,
        dois: list[str],
    ) -> list[UnpaywallResult]:
        """Batch-fetch OA info for multiple DOIs concurrently.

        Unpaywall has no native batch endpoint, so we use an asyncio
        Semaphore to control concurrency and run parallel single-DOI lookups.
        Failed lookups are skipped with a warning.
        """
        async def fetch_one(doi: str) -> UnpaywallResult | None:
            async with self._semaphore:
                try:
                    return await self.fetch_by_doi(doi)
                except ReferenceError as e:
                    logger.warning("Unpaywall batch fetch failed for %s: %s", doi, e)
                    return None

        tasks = [fetch_one(doi) for doi in dois]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]

    async def resolve_oa_url(
        self,
        doi: str,
    ) -> str | None:
        """Resolve a DOI to its best OA PDF URL using a fallback chain.

        Tries, in order:
        1. Unpaywall
        2. OpenAlex (via fallback_clients["openalex"])
        3. Semantic Scholar (via fallback_clients["semantic_scholar"])

        Returns the first OA PDF URL found, or None if none exists.
        """
        try:
            result = await self.fetch_by_doi(doi)
            if result.pdf_url:
                return result.pdf_url
        except ReferenceError:
            pass

        openalex = self._fallback_clients.get("openalex")
        if openalex is not None:
            try:
                work = await openalex.fetch_work(f"doi:{doi}")
                oa = work.extra.get("open_access") or {}
                oa_url = oa.get("oa_url") or ""
                if oa_url:
                    return oa_url
            except ReferenceError:
                pass

        s2 = self._fallback_clients.get("semantic_scholar")
        if s2 is not None:
            try:
                detail = await s2.fetch_detail(f"DOI:{doi}", fields="openAccessPdf")
                pdf = detail.extra.get("open_access_pdf", "")
                if pdf:
                    return pdf  # type: ignore[no-any-return]
            except ReferenceError:
                pass

        return None

    @staticmethod
    def classify_oa(result: UnpaywallResult) -> str:
        """Classify a paper into a high-level OA category.

        Returns one of:
        - "gold" — OA journal (DOAJ or otherwise)
        - "hybrid" — open in an otherwise subscription journal
        - "green" — author manuscript/repository copy
        - "bronze" — free to read but no clear license
        - "closed" — paywalled
        - "unknown" — could not determine
        """
        if not result.is_oa:
            return "closed"

        status = (result.oa_status or "").lower()
        if status in ("gold", "hybrid", "green", "bronze"):
            return status

        if result.journal_is_in_doaj:
            return "gold"

        best = result.best_oa_location
        if best is not None:
            host = (best.host_type or "").lower()
            if host == "repository":
                return "green"
            lic = (best.license or "").lower()
            if host in ("publisher", "journal"):
                if "cc" in lic:
                    return "gold"
                return "hybrid"
            if lic:
                return "bronze"

        if result.oa_locations:
            return "green"

        return "unknown"

    async def close(self) -> None:
        await self._client.aclose()

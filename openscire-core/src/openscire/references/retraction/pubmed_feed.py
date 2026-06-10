from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import Any, cast

import httpx

from openscire.exceptions import ReferenceError
from openscire.references.retraction.models import (
    RetractionRecord,
    RetractionSource,
    RetractionStatus,
)

logger = logging.getLogger(__name__)

PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
RETRACTED_QUERY = '"retracted publication"[Filter]'


class PubMedRateLimiter:
    def __init__(self) -> None:
        self._delay = 0.35
        self._last = 0.0

    async def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        if elapsed < self._delay:
            await asyncio.sleep(self._delay - elapsed)
        self._last = time.monotonic()


class PubMedRetractionClient:
    def __init__(self, email: str = "research@example.com") -> None:
        self._email = email
        self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        self._rate_limiter = PubMedRateLimiter()

    async def search_retracted(
        self,
        since_date: datetime | None = None,
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        mindate, maxdate = self._format_date_range(since_date)
        params: dict[str, Any] = {
            "db": "pubmed",
            "term": RETRACTED_QUERY,
            "retmode": "json",
            "retmax": str(max_results),
            "email": self._email,
            "mindate": mindate,
            "maxdate": maxdate,
            "datetype": "edat",
        }
        data = await self._get(f"{PUBMED_BASE}/esearch.fcgi", params=params)
        id_list = (data.get("esearchresult") or {}).get("idlist") or []
        if not id_list:
            return []
        return await self._fetch_summaries(id_list)

    async def fetch_retraction_notice(self, pmid: str) -> dict[str, Any]:
        params: dict[str, Any] = {
            "db": "pubmed",
            "id": pmid,
            "retmode": "xml",
            "email": self._email,
        }
        result = await self._get(f"{PUBMED_BASE}/efetch.fcgi", params=params)
        return cast("dict[str, Any]", result)

    async def _fetch_summaries(
        self,
        pmids: list[str],
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "json",
            "email": self._email,
        }
        data = await self._get(f"{PUBMED_BASE}/esummary.fcgi", params=params)
        result = data.get("result", {})
        uids = result.get("uids", [])
        summaries = []
        for uid in uids:
            entry = result.get(uid, {})
            summaries.append(
                {
                    "pmid": str(uid),
                    "title": entry.get("title", ""),
                    "doi": self._extract_doi(entry.get("elocationid", "")),
                    "source": entry.get("source", ""),
                    "pubdate": entry.get("pubdate", ""),
                }
            )
        return summaries

    async def to_retraction_record(
        self,
        summary: dict[str, Any],
    ) -> RetractionRecord | None:
        doi = summary.get("doi", "")
        if not doi:
            return None
        return RetractionRecord(
            identifier=doi,
            retraction_status=RetractionStatus.retracted,
            source=RetractionSource.pubmed,
            detected_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            notice_text=f"Retracted per PubMed: {summary.get('title', '')}",
            details={"pmid": summary.get("pmid", "")},
        )

    async def close(self) -> None:
        await self._client.aclose()

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
                f"PubMed API error ({e.response.status_code})",
                source="pubmed_retraction",
            ) from e
        except httpx.RequestError as e:
            raise ReferenceError(
                f"PubMed request failed: {e}",
                source="pubmed_retraction",
            ) from e

    @staticmethod
    def _format_date_range(
        since_date: datetime | None,
    ) -> tuple[str, str]:
        if since_date is None:
            return "1900/01/01", datetime.now(UTC).strftime("%Y/%m/%d")
        return since_date.strftime("%Y/%m/%d"), datetime.now(UTC).strftime("%Y/%m/%d")

    @staticmethod
    def _extract_doi(elocation_id: str) -> str:
        if elocation_id.lower().startswith("doi:"):
            return elocation_id[4:].strip()
        return elocation_id.strip()

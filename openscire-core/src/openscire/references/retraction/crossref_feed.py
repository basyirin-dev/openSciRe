from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from openscire.exceptions import ReferenceError
from openscire.references.retraction.models import (
    RetractionRecord,
    RetractionSource,
    RetractionStatus,
)

logger = logging.getLogger(__name__)

CROSSREF_BASE = "https://api.crossref.org"


class CrossrefRateLimiter:
    def __init__(self) -> None:
        self._delay = 1.0
        self._last = 0.0

    async def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        if elapsed < self._delay:
            await asyncio.sleep(self._delay - elapsed)
        self._last = time.monotonic()


_UPDATE_TYPE_MAP: dict[str, RetractionStatus] = {
    "retraction": RetractionStatus.retracted,
    "correction": RetractionStatus.corrected,
    "expression-of-concern": RetractionStatus.expression_of_concern,
}


class CrossrefRetractionClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        self._rate_limiter = CrossrefRateLimiter()
        self._user_agent = "OpenSciRe/0.1 (mailto:research@example.com)"

    async def search_recent_corrections(
        self,
        since_date: datetime | None = None,
        rows: int = 100,
    ) -> list[dict[str, Any]]:
        cutoff = since_date or datetime.now(UTC)
        params: dict[str, Any] = {
            "filter": f"from-update-date:{cutoff.strftime('%Y-%m-%d')}",
            "select": "DOI,title,update-to,container-title,publisher,issued",
            "rows": min(rows, 1000),
        }
        data = await self._get(
            f"{CROSSREF_BASE}/works",
            params=params,
        )
        items = (data.get("message") or {}).get("items") or []
        return self._filter_correction_items(items)

    async def get_correction_detail(self, doi: str) -> dict[str, Any]:
        data = await self._get(f"{CROSSREF_BASE}/works/{doi}")
        return data.get("message") or {}

    async def to_retraction_record(
        self,
        item: dict[str, Any],
        update: dict[str, Any],
    ) -> RetractionRecord:
        doi = (item.get("DOI") or "").lower()
        update_type = (update.get("type") or "").lower()
        status = _UPDATE_TYPE_MAP.get(update_type, RetractionStatus.unknown)
        return RetractionRecord(
            identifier=f"https://doi.org/{doi}",
            retraction_status=status,
            source=RetractionSource.crossref,
            detected_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            notice_text=update.get("label", "") or update_type.replace("-", " ").title() or "",
            notice_url=update.get("DOI", ""),
            reason=update.get("label", "") or "",
            details={
                "doi": doi,
                "update_type": update_type,
                "title": item.get("title", [""])[0] if isinstance(item.get("title"), list) else "",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> Any:  # noqa: ANN401
        await self._rate_limiter.wait()
        headers = {"User-Agent": self._user_agent}
        try:
            response = await self._client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise ReferenceError(
                f"Crossref API error ({e.response.status_code})",
                source="crossref_retraction",
            ) from e
        except httpx.RequestError as e:
            raise ReferenceError(
                f"Crossref request failed: {e}",
                source="crossref_retraction",
            ) from e

    @staticmethod
    def _filter_correction_items(
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        result = []
        for item in items:
            updates = item.get("update-to") or []
            filtered_updates = [
                u for u in updates
                if (u.get("type") or "").lower() in _UPDATE_TYPE_MAP
            ]
            if filtered_updates:
                result.append({
                    "item": item,
                    "updates": filtered_updates,
                })
        return result

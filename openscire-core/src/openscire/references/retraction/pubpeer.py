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

PUBPEER_BASE = "https://pubpeer.com/api/v3"


class PubPeerRateLimiter:
    def __init__(self) -> None:
        self._delay = 1.0
        self._last = 0.0

    async def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        if elapsed < self._delay:
            await asyncio.sleep(self._delay - elapsed)
        self._last = time.monotonic()


class PubPeerClient:
    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        self._rate_limiter = PubPeerRateLimiter()

    async def search_by_doi(self, doi: str) -> list[dict[str, Any]]:
        if not self._api_key:
            logger.warning("PubPeer API key not configured — skipping search_by_doi")
            return []
        params: dict[str, Any] = {"doi": doi}
        data = await self._get(f"{PUBPEER_BASE}/search", params=params)
        return (data.get("results") or []) if isinstance(data, dict) else (data or [])

    async def get_recent_activity(
        self,
        since_date: datetime | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if not self._api_key:
            logger.warning("PubPeer API key not configured — skipping get_recent_activity")
            return []
        params: dict[str, Any] = {"limit": limit}
        if since_date:
            params["since"] = since_date.isoformat()
        data = await self._get(f"{PUBPEER_BASE}/recent", params=params)
        return (data.get("results") or []) if isinstance(data, dict) else (data or [])

    async def get_concerns(self, doi: str) -> list[dict[str, Any]]:
        results = await self.search_by_doi(doi)
        concerns = []
        for r in results:
            if self._is_concern(r):
                concerns.append(r)
        return concerns

    async def to_retraction_record(
        self,
        comment: dict[str, Any],
    ) -> RetractionRecord | None:
        doi = (comment.get("doi") or "").strip().lower()
        if not doi:
            return None
        return RetractionRecord(
            identifier=doi,
            retraction_status=RetractionStatus.concern_raised,
            source=RetractionSource.pubpeer,
            detected_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            notice_text=comment.get("title", "") or comment.get("text", "")[:500] or "",
            notice_url=comment.get("url", "") or comment.get("link", ""),
            reason=comment.get("category", "") or "",
            details={
                "comment_id": comment.get("id", ""),
                "comment_type": comment.get("type", ""),
                "authors": comment.get("authors", ""),
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
        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            response = await self._client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise ReferenceError(
                f"PubPeer API error ({e.response.status_code})",
                source="pubpeer",
            ) from e
        except httpx.RequestError as e:
            raise ReferenceError(
                f"PubPeer request failed: {e}",
                source="pubpeer",
            ) from e

    @staticmethod
    def _is_concern(comment: dict[str, Any]) -> bool:
        category = (comment.get("category") or "").lower()
        text = (comment.get("title") or "").lower() + (comment.get("text") or "").lower()
        concern_keywords = [
            "concern", "retraction", "error", "fabrication", "falsification",
            "plagiarism", "duplicate", "unreliable", "misconduct",
        ]
        if category in ("concern", "retraction", "expression_of_concern"):
            return True
        return any(kw in text for kw in concern_keywords)

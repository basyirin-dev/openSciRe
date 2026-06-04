# SPDX-License-Identifier: Apache-2.0

"""Wanfang Data discovery client.

Wanfang Data has no public metadata search API.  This client searches
OpenAlex for works affiliated with Chinese institutions, which covers
most Wanfang-indexed content.

Source attribution: results carry ReferenceSource.openalex.
"""

from __future__ import annotations

from openscire.references.bridges.openalex import OpenAlexClient
from openscire.references.models import OpenAlexSearchResult, ReferenceItem


class WanfangClient:
    """Discovery client for Chinese scientific metadata via OpenAlex.

    Searches OpenAlex with language:zh and Chinese institution filters
    to find papers indexed in Wanfang Data.
    """

    def __init__(
        self,
        openalex_client: OpenAlexClient | None = None,
    ) -> None:
        self._oa = openalex_client or OpenAlexClient()

    async def search(
        self,
        query: str,
        page: int = 1,
        per_page: int = 25,
    ) -> OpenAlexSearchResult:
        """Search Chinese-institution papers by query string."""
        return await self._oa.search_works(
            query=query,
            filters="language:zh,institutions.country_code:cn",
            page=page,
            per_page=per_page,
        )

    async def fetch_detail(self, work_id: str) -> ReferenceItem:
        """Fetch a single work and tag as Chinese."""
        item = await self._oa.fetch_work(work_id)
        if not item.original_language:
            item.original_language = "zh"
        return item

    async def search_by_title(self, title: str) -> ReferenceItem | None:
        """Search by exact title in Chinese-institution works."""
        result = await self._oa.list_works(
            filters="language:zh,institutions.country_code:cn",
            page=1,
            per_page=50,
        )
        if not result.work_ids:
            return None
        title_lower = title.lower().strip()
        ids_param = "|".join(result.work_ids)
        data = await self._oa._get(
            f"{self._oa.BASE_URL}/works",
            params={
                "filter": f"openalex_id:{ids_param}",
                "per-page": min(len(result.work_ids), 50),
                "select": "id,display_name",
            },
        )
        for work in data.get("results") or []:
            if work.get("display_name", "").lower().strip() == title_lower:
                return await self.fetch_detail(work["id"])
        return None

    async def fetch_batch(
        self,
        work_ids: list[str],
    ) -> list[ReferenceItem]:
        """Batch-fetch multiple works, tagging language."""
        items = await self._oa.fetch_works_batch(work_ids)
        for item in items:
            if not item.original_language:
                item.original_language = "zh"
        return items

    async def close(self) -> None:
        await self._oa.close()

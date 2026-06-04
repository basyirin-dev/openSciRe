# SPDX-License-Identifier: Apache-2.0

"""eLibrary.ru (РИНЦ — Russian Science Citation Index) discovery client.

eLibrary.ru has no public API — access requires a paid institutional
subscription.  This client searches OpenAlex for Russian-language works
to find papers indexed in the RSCI.

Source attribution: results carry ReferenceSource.openalex.
"""

from __future__ import annotations

from openscire.references.bridges.openalex import OpenAlexClient
from openscire.references.models import OpenAlexSearchResult, ReferenceItem


class ElibraryClient:
    """Discovery client for Russian scientific metadata via OpenAlex.

    Searches OpenAlex for Russian-language works (language:ru) to
    discover papers that would be indexed in eLibrary.ru / RSCI.
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
        """Search Russian-language papers by query string."""
        return await self._oa.search_works(
            query=query,
            filters="language:ru",
            page=page,
            per_page=per_page,
        )

    async def fetch_detail(self, work_id: str) -> ReferenceItem:
        """Fetch a single work and tag as Russian."""
        item = await self._oa.fetch_work(work_id)
        if not item.original_language:
            item.original_language = "ru"
        return item

    async def search_by_title(self, title: str) -> ReferenceItem | None:
        """Search by exact title in Russian-language works."""
        result = await self._oa.list_works(
            filters="language:ru",
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
                item.original_language = "ru"
        return items

    async def close(self) -> None:
        await self._oa.close()

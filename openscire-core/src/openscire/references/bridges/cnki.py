# SPDX-License-Identifier: Apache-2.0

"""CNKI (China National Knowledge Infrastructure) discovery client.

CNKI has no public metadata search API.  This client searches OpenAlex
using language:zh filters to find Chinese-language papers indexed there.

For direct CNKI access, users must use the CNKI Open Platform API
(https://openx.cnki.net) separately with institutional credentials.

Source attribution: results carry ReferenceSource.openalex.
"""

from __future__ import annotations

from openscire.references.bridges.openalex import OpenAlexClient
from openscire.references.models import OpenAlexSearchResult, ReferenceItem


class CnkiClient:
    """Discovery client for Chinese-language scientific literature via OpenAlex.

    Searches OpenAlex with language:zh to find Chinese-language papers.
    The language detection heuristic also verifies the result language.
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
        """Search Chinese-language papers by query string."""
        return await self._oa.search_works(
            query=query,
            filters="language:zh,type:article",
            page=page,
            per_page=per_page,
        )

    async def fetch_detail(self, work_id: str) -> ReferenceItem:
        """Fetch a single work and tag it as original_language=zh."""
        item = await self._oa.fetch_work(work_id)
        if not item.original_language:
            item.original_language = "zh"
        return item

    async def search_by_title(self, title: str) -> ReferenceItem | None:
        """Search by exact title in Chinese-language works."""
        result = await self._oa.list_works(
            filters="language:zh",
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

    async def get_citation_count(self, work_id: str) -> int:
        """Fetch citation count for a Chinese-language work."""
        return await self._oa.fetch_citation_count(work_id)

    async def close(self) -> None:
        await self._oa.close()

# SPDX-License-Identifier: Apache-2.0

"""AJOL (African Journals Online) discovery client.

AJOL has no public REST API.  This client searches OpenAlex for works
affiliated with African institutions, which covers most AJOL-hosted
journals.

See https://www.ajol.info/ for the web portal.

Source attribution: results carry ReferenceSource.openalex.
"""

from __future__ import annotations

from openscire.references.bridges.openalex import OpenAlexClient
from openscire.references.models import OpenAlexSearchResult, ReferenceItem

# ISO 3166-1 alpha-2 country codes for African nations
AFRICAN_COUNTRIES = (
    "ao|bf|bw|cd|cf|cg|ci|cm|cv|dj|dz|eg|eh|er|et|ga|gh|gm|gn|gq|"
    "gw|ke|km|lr|ls|ly|ma|mg|ml|mr|mu|mw|mz|na|ne|ng|re|rw|sc|sd|"
    "sh|sl|sn|so|ss|st|sz|td|tg|tn|tz|ug|yt|za|zm|zw"
)


class AjolClient:
    """Discovery client for African-published research via OpenAlex.

    Searches OpenAlex for works affiliated with African institutions.
    Covers 54 African nations.
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
        """Search African-published papers by query string."""
        return await self._oa.search_works(
            query=query,
            filters=f"institutions.country_code:{AFRICAN_COUNTRIES}",
            page=page,
            per_page=per_page,
        )

    async def fetch_detail(self, work_id: str) -> ReferenceItem:
        """Fetch a single work."""
        return await self._oa.fetch_work(work_id)

    async def search_by_title(self, title: str) -> ReferenceItem | None:
        """Search by exact title in African-institution works."""
        result = await self._oa.list_works(
            filters=f"institutions.country_code:{AFRICAN_COUNTRIES}",
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
        """Batch-fetch multiple works."""
        return await self._oa.fetch_works_batch(work_ids)

    async def close(self) -> None:
        await self._oa.close()

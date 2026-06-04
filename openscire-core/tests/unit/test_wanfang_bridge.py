# SPDX-License-Identifier: Apache-2.0

import pytest
import respx
from httpx import Response
from openscire.references.bridges.wanfang import WanfangClient
from openscire.references.models import OpenAlexSearchResult, ReferenceItem

SEARCH_RESPONSE = {
    "meta": {"count": 1, "page": 1, "per_page": 25},
    "results": [
        {
            "id": "https://openalex.org/W888888",
            "display_name": "数据挖掘在医学中的应用",
            "publication_year": 2024,
            "cited_by_count": 15,
        }
    ],
}

WORK_DETAIL = {
    "id": "https://openalex.org/W888888",
    "display_name": "数据挖掘在医学中的应用",
    "doi": "https://doi.org/10.1234/wanfang-test",
    "publication_year": 2024,
    "cited_by_count": 15,
    "language": "zh",
    "authorships": [],
    "abstract_inverted_index": None,
    "open_access": {"is_oa": False},
    "primary_location": {"source": {"display_name": "中华医学杂志"}},
}


@pytest.fixture
def client() -> WanfangClient:
    return WanfangClient()


class TestWanfangClient:
    @pytest.mark.asyncio
    @respx.mock
    async def test_search(self, client: WanfangClient) -> None:
        respx.get("https://api.openalex.org/works").mock(
            return_value=Response(200, json=SEARCH_RESPONSE)
        )
        result = await client.search("data mining medicine")
        assert isinstance(result, OpenAlexSearchResult)
        assert result.total_count == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_detail(self, client: WanfangClient) -> None:
        respx.get("https://api.openalex.org/works/W888888").mock(
            return_value=Response(200, json=WORK_DETAIL)
        )
        item = await client.fetch_detail("W888888")
        assert isinstance(item, ReferenceItem)
        assert item.original_language == "zh"

    @pytest.mark.asyncio
    async def test_close(self, client: WanfangClient) -> None:
        await client.close()

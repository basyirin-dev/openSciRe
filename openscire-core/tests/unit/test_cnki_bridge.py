# SPDX-License-Identifier: Apache-2.0

import pytest
import respx
from httpx import Response
from openscire.references.bridges.cnki import CnkiClient
from openscire.references.models import OpenAlexSearchResult, ReferenceItem

SEARCH_RESPONSE = {
    "meta": {"count": 1, "page": 1, "per_page": 25},
    "results": [
        {
            "id": "https://openalex.org/W2741809807",
            "doi": "https://doi.org/10.1234/zh-paper",
            "display_name": "机器学习在农业中的应用",
            "publication_year": 2024,
            "cited_by_count": 42,
        }
    ],
}

WORK_DETAIL = {
    "id": "https://openalex.org/W2741809807",
    "display_name": "机器学习在农业中的应用",
    "doi": "https://doi.org/10.1234/zh-paper",
    "publication_year": 2024,
    "cited_by_count": 42,
    "language": "zh",
    "authorships": [],
    "abstract_inverted_index": None,
    "open_access": {"is_oa": True},
    "primary_location": {"source": {"display_name": "中国农业科学"}},
}


@pytest.fixture
def client() -> CnkiClient:
    return CnkiClient()


class TestCnkiClient:
    @pytest.mark.asyncio
    @respx.mock
    async def test_search(self, client: CnkiClient) -> None:
        respx.get("https://api.openalex.org/works").mock(
            return_value=Response(200, json=SEARCH_RESPONSE)
        )
        result = await client.search("machine learning agriculture")
        assert isinstance(result, OpenAlexSearchResult)
        assert result.total_count == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_detail(self, client: CnkiClient) -> None:
        respx.get("https://api.openalex.org/works/W2741809807").mock(
            return_value=Response(200, json=WORK_DETAIL)
        )
        item = await client.fetch_detail("W2741809807")
        assert isinstance(item, ReferenceItem)
        assert item.original_language == "zh"
        assert "机器学习" in item.title

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_by_title(self, client: CnkiClient) -> None:
        respx.get("https://api.openalex.org/works").mock(
            side_effect=[
                Response(200, json=SEARCH_RESPONSE),
                Response(200, json={"results": [WORK_DETAIL], "meta": {"count": 1}}),
            ]
        )
        respx.get("https://api.openalex.org/works/https://openalex.org/W2741809807").mock(
            return_value=Response(200, json=WORK_DETAIL)
        )
        item = await client.search_by_title("机器学习在农业中的应用")
        assert item is not None
        assert item.original_language == "zh"

    @pytest.mark.asyncio
    async def test_close(self, client: CnkiClient) -> None:
        await client.close()

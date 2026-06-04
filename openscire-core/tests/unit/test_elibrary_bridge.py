# SPDX-License-Identifier: Apache-2.0

import pytest
import respx
from httpx import Response
from openscire.references.bridges.elibrary import ElibraryClient
from openscire.references.models import OpenAlexSearchResult, ReferenceItem

SEARCH_RESPONSE = {
    "meta": {"count": 1, "page": 1, "per_page": 25},
    "results": [
        {
            "id": "https://openalex.org/W999999",
            "display_name": "Исследование квантовых вычислений",
            "publication_year": 2024,
            "cited_by_count": 25,
        }
    ],
}

WORK_DETAIL = {
    "id": "https://openalex.org/W999999",
    "display_name": "Исследование квантовых вычислений",
    "doi": "https://doi.org/10.1234/elibrary-test",
    "publication_year": 2024,
    "cited_by_count": 25,
    "language": "ru",
    "authorships": [],
    "abstract_inverted_index": None,
    "open_access": {"is_oa": False},
    "primary_location": {"source": {"display_name": "Успехи физических наук"}},
}


@pytest.fixture
def client() -> ElibraryClient:
    return ElibraryClient()


class TestElibraryClient:
    @pytest.mark.asyncio
    @respx.mock
    async def test_search(self, client: ElibraryClient) -> None:
        respx.get("https://api.openalex.org/works").mock(
            return_value=Response(200, json=SEARCH_RESPONSE)
        )
        result = await client.search("quantum computing")
        assert isinstance(result, OpenAlexSearchResult)
        assert result.total_count == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_detail(self, client: ElibraryClient) -> None:
        respx.get("https://api.openalex.org/works/W999999").mock(
            return_value=Response(200, json=WORK_DETAIL)
        )
        item = await client.fetch_detail("W999999")
        assert isinstance(item, ReferenceItem)
        assert item.original_language == "ru"

    @pytest.mark.asyncio
    async def test_close(self, client: ElibraryClient) -> None:
        await client.close()

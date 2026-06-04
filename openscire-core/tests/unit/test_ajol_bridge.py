# SPDX-License-Identifier: Apache-2.0

import pytest
import respx
from httpx import Response
from openscire.references.bridges.ajol import AjolClient
from openscire.references.models import OpenAlexSearchResult, ReferenceItem

SEARCH_RESPONSE = {
    "meta": {"count": 1, "page": 1, "per_page": 25},
    "results": [
        {
            "id": "https://openalex.org/W555555",
            "display_name": "Malaria prevention in Sub-Saharan Africa",
            "publication_year": 2024,
            "cited_by_count": 30,
        }
    ],
}

WORK_DETAIL = {
    "id": "https://openalex.org/W555555",
    "display_name": "Malaria prevention in Sub-Saharan Africa",
    "doi": "https://doi.org/10.1234/ajol-test",
    "publication_year": 2024,
    "cited_by_count": 30,
    "authorships": [
        {
            "author": {"display_name": "John Kamau"},
            "institutions": [{"display_name": "University of Nairobi", "country_code": "ke"}],
        }
    ],
    "abstract_inverted_index": None,
    "open_access": {"is_oa": True},
    "primary_location": {"source": {"display_name": "African Journal of Health Sciences"}},
}


@pytest.fixture
def client() -> AjolClient:
    return AjolClient()


class TestAjolClient:
    @pytest.mark.asyncio
    @respx.mock
    async def test_search(self, client: AjolClient) -> None:
        respx.get("https://api.openalex.org/works").mock(
            return_value=Response(200, json=SEARCH_RESPONSE)
        )
        result = await client.search("malaria prevention")
        assert isinstance(result, OpenAlexSearchResult)
        assert result.total_count == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_detail(self, client: AjolClient) -> None:
        respx.get("https://api.openalex.org/works/W555555").mock(
            return_value=Response(200, json=WORK_DETAIL)
        )
        item = await client.fetch_detail("W555555")
        assert isinstance(item, ReferenceItem)
        assert "Malaria" in item.title
        assert len(item.authors) == 1

    @pytest.mark.asyncio
    async def test_close(self, client: AjolClient) -> None:
        await client.close()

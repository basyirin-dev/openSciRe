import pytest
import respx
from httpx import Response
from openscire.bridge.resolver import CrossReferenceResolver


class TestCrossReferenceResolver:
    @pytest.mark.asyncio
    @respx.mock
    async def test_doi_to_pmid(self) -> None:
        resolver = CrossReferenceResolver()
        respx.get("https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/").mock(
            return_value=Response(
                200,
                json={
                    "records": [
                        {"doi": "10.1234/abc", "pmid": "12345", "pmcid": "PMC67890"},
                    ],
                },
            ),
        )
        pmid = await resolver.doi_to_pmid("10.1234/abc")
        assert pmid == "12345"
        await resolver.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_pmid_to_pmcid(self) -> None:
        resolver = CrossReferenceResolver()
        respx.get("https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/").mock(
            return_value=Response(
                200,
                json={
                    "records": [
                        {"pmid": "12345", "pmcid": "PMC67890"},
                    ],
                },
            ),
        )
        pmcid = await resolver.pmid_to_pmcid("12345")
        assert pmcid == "PMC67890"
        await resolver.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_doi_to_pmcid(self) -> None:
        resolver = CrossReferenceResolver()
        respx.get("https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/").mock(
            return_value=Response(
                200,
                json={
                    "records": [
                        {"doi": "10.1234/abc", "pmcid": "PMC67890"},
                    ],
                },
            ),
        )
        pmcid = await resolver.doi_to_pmcid("10.1234/abc")
        assert pmcid == "PMC67890"
        await resolver.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_pdb_to_uniprot(self) -> None:
        resolver = CrossReferenceResolver()
        pdb_id = "1ake"
        respx.get(f"https://www.ebi.ac.uk/pdbe/api/mappings/{pdb_id}").mock(
            return_value=Response(
                200,
                json={
                    pdb_id: {
                        "UniProt": {
                            "P12345": [{"identifier": "P12345"}],
                            "P67890": [{"identifier": "P67890"}],
                        },
                    },
                },
            ),
        )
        result = await resolver.pdb_to_uniprot(pdb_id)
        assert sorted(result) == ["P12345", "P67890"]
        await resolver.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_uniprot_to_pdb(self) -> None:
        resolver = CrossReferenceResolver()
        uniprot_id = "P12345"
        respx.get(
            f"https://www.ebi.ac.uk/pdbe/api/mappings/uniprot/{uniprot_id}",
        ).mock(
            return_value=Response(
                200,
                json={
                    uniprot_id: {
                        "1ake": {"pdb_id": "1ake"},
                        "2ake": {"pdb_id": "2ake"},
                    },
                },
            ),
        )
        result = await resolver.uniprot_to_pdb(uniprot_id)
        assert sorted(result) == ["1ake", "2ake"]
        await resolver.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_invalid_input_returns_none(self) -> None:
        resolver = CrossReferenceResolver()
        respx.get("https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/").mock(
            return_value=Response(200, json={"records": []}),
        )
        pmid = await resolver.doi_to_pmid("nonexistent")
        assert pmid is None
        await resolver.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_multiple_results(self) -> None:
        resolver = CrossReferenceResolver()
        respx.get("https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/").mock(
            return_value=Response(
                200,
                json={
                    "records": [
                        {"doi": "10.1234/a", "pmid": "1"},
                        {"doi": "10.1234/b", "pmid": "2"},
                    ],
                },
            ),
        )
        pmid = await resolver.doi_to_pmid("10.1234/a")
        assert pmid == "1"
        await resolver.close()

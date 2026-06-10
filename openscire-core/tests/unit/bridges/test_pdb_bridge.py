# SPDX-License-Identifier: Apache-2.0

import pytest
import respx
from httpx import Response
from openscire.bridge.evidence_label import EvidenceTypeLabel
from openscire.bridges.pdb import (
    PdbClient,
    PdbQueryBuilder,
    PdbSearchResult,
    PdbStructureResult,
)
from openscire.exceptions import ReferenceError

GRAPHQL_URL = "https://data.rcsb.org/graphql"
SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"

STRUCTURE_RESPONSE = {
    "data": {
        "entry": {
            "rcsb_id": "4HHB",
            "struct": {
                "title": "THE CRYSTAL STRUCTURE OF HUMAN DEOXYHAEMOGLOBIN AT 1.74 ANGSTROMS",
            },
            "exptl": [{"method": "X-RAY DIFFRACTION"}],
            "rcsb_entry_info": {
                "resolution_combined": [1.74],
                "experimental_method": "X-ray",
                "structure_determination_methodology": "experimental",
                "molecular_weight": 64.74,
            },
            "rcsb_accession_info": {
                "initial_release_date": "1984-07-17T00:00:00Z",
            },
            "rcsb_primary_citation": {
                "title": "The crystal structure of human deoxyhaemoglobin at 1.74 A resolution",
                "journal_abbrev": "J.Mol.Biol.",
                "year": 1984,
                "pdbx_database_id_PubMed": 6726807,
                "pdbx_database_id_DOI": "10.1016/0022-2836(84)90472-8",
                "rcsb_authors": ["Fermi, G.", "Perutz, M.F.", "Shaanan, B."],
            },
            "refine": [
                {
                    "ls_d_res_high": 1.74,
                    "ls_R_factor_R_free": None,
                    "ls_R_factor_R_work": 0.135,
                },
            ],
            "audit_author": [
                {"name": "Fermi, G."},
                {"name": "Perutz, M.F."},
            ],
            "polymer_entities": [
                {
                    "rcsb_id": "4HHB_1",
                    "entity_poly": {
                        "rcsb_entity_polymer_type": "Protein",
                        "pdbx_seq_one_letter_code_can": "VLSPADKTNVK",
                    },
                    "rcsb_polymer_entity_container_identifiers": {
                        "asym_ids": ["A", "C"],
                    },
                    "uniprots": [
                        {
                            "rcsb_uniprot_accession": ["P69905", "P01922"],
                        },
                    ],
                    "pfams": [
                        {
                            "rcsb_pfam_accession": "PF00042",
                        },
                    ],
                    "rcsb_polymer_entity_annotation": [
                        {
                            "type": "GO",
                            "name": "hemoglobin complex",
                            "provenance_source": "UNIPROT",
                        },
                        {
                            "type": "InterPro",
                            "name": "Hemoglobin, alpha-type",
                            "provenance_source": "UNIPROT",
                        },
                        {"type": "SCOP", "name": "Globin-like", "provenance_source": "SCOP"},
                    ],
                },
                {
                    "rcsb_id": "4HHB_2",
                    "entity_poly": {
                        "rcsb_entity_polymer_type": "Protein",
                        "pdbx_seq_one_letter_code_can": "VHLTPEEKSA",
                    },
                    "rcsb_polymer_entity_container_identifiers": {
                        "asym_ids": ["B", "D"],
                    },
                    "uniprots": [
                        {
                            "rcsb_uniprot_accession": ["P68871", "P02023"],
                        },
                    ],
                    "pfams": [
                        {
                            "rcsb_pfam_accession": "PF00042",
                        },
                    ],
                    "rcsb_polymer_entity_annotation": [
                        {"type": "GO", "name": "oxygen binding", "provenance_source": "UNIPROT"},
                        {
                            "type": "InterPro",
                            "name": "Hemoglobin, beta-type",
                            "provenance_source": "UNIPROT",
                        },
                    ],
                },
            ],
            "database_2": [
                {"database_id": "PDB", "database_code": "4HHB"},
                {"database_id": "WWPDB", "database_code": "D_1000200000"},
            ],
            "rcsb_entry_container_identifiers": {
                "entry_id": "4HHB",
                "emdb_ids": ["EMD-1234"],
            },
        },
    },
}

COMPUTATIONAL_RESPONSE = {
    "data": {
        "entry": {
            "rcsb_id": "AF_P69905_F1",
            "struct": {"title": "Alpha hemoglobin (AlphaFold prediction)"},
            "exptl": [{"method": "COMPUTATIONAL MODEL"}],
            "rcsb_entry_info": {
                "resolution_combined": [None],
                "experimental_method": "Computational",
                "structure_determination_methodology": "computational",
                "molecular_weight": None,
            },
            "rcsb_accession_info": {
                "initial_release_date": "2024-01-01T00:00:00Z",
            },
            "rcsb_primary_citation": None,
            "refine": [],
            "audit_author": [],
            "polymer_entities": [],
            "database_2": [],
            "rcsb_entry_container_identifiers": {
                "entry_id": "AF_P69905_F1",
            },
        },
    },
}

NOT_FOUND_RESPONSE = {
    "errors": [{"message": "No entry found with identifier 4ZZZ"}],
}

SEARCH_RESPONSE = {
    "total_count": 3,
    "result_type": "entry",
    "result_set": [
        {"identifier": "4HHB", "score": 1.0},
        {"identifier": "1A3N", "score": 0.9},
        {"identifier": "2DN1", "score": 0.8},
    ],
}

SEARCH_EMPTY = {
    "total_count": 0,
    "result_type": "entry",
    "result_set": [],
}


@pytest.fixture
def client() -> PdbClient:
    return PdbClient(rate=100.0, burst=10)


class TestPdbQueryBuilder:
    def test_resolution_max_only(self) -> None:
        qb = PdbQueryBuilder().resolution(2.0)
        built = qb.build()
        assert built["query"]["parameters"]["attribute"] == "rcsb_entry_info.resolution_combined"
        assert built["query"]["parameters"]["operator"] == "less_or_equal"
        assert built["query"]["parameters"]["value"] == 2.0

    def test_resolution_range(self) -> None:
        qb = PdbQueryBuilder().resolution(3.0, 1.0)
        built = qb.build()
        assert built["query"]["type"] == "group"
        assert built["query"]["logical_operator"] == "and"
        assert len(built["query"]["nodes"]) == 2

    def test_ligand(self) -> None:
        qb = PdbQueryBuilder().ligand("ATP")
        built = qb.build()
        params = built["query"]["parameters"]
        assert params["attribute"] == "rcsb_chem_comp_annotation.comp_id"
        assert params["operator"] == "exact_match"
        assert params["value"] == "ATP"

    def test_author(self) -> None:
        qb = PdbQueryBuilder().author("Fermi")
        built = qb.build()
        params = built["query"]["parameters"]
        assert params["attribute"] == "rcsb_entry_info.author_last_name"
        assert params["value"] == "Fermi"

    def test_sequence_search(self) -> None:
        qb = PdbQueryBuilder().sequence("VLSPADKTNVK", identity=0.9)
        built = qb.build()
        params = built["query"]["parameters"]
        assert built["query"]["service"] == "sequence"
        assert params["value"] == "VLSPADKTNVK"
        assert params["identity_cutoff"] == 0.9

    def test_structure_id(self) -> None:
        qb = PdbQueryBuilder().structure_id("4hhb")
        built = qb.build()
        params = built["query"]["parameters"]
        assert params["attribute"] == "rcsb_entry_info.entry_id"
        assert params["value"] == "4HHB"

    def test_chained_filters(self) -> None:
        qb = PdbQueryBuilder()
        qb.resolution(2.0).experimental_method("X-ray")
        built = qb.build()
        assert built["query"]["type"] == "group"
        assert len(built["query"]["nodes"]) == 2

    def test_empty_builder(self) -> None:
        built = PdbQueryBuilder().build()
        assert built == {}


class TestPdbClient:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_structure(self, client: PdbClient) -> None:
        respx.post(GRAPHQL_URL).mock(
            return_value=Response(200, json=STRUCTURE_RESPONSE),
        )
        result = await client.get("4HHB")
        assert isinstance(result, PdbStructureResult)
        assert result.pdb_id == "4HHB"
        assert "HUMAN DEOXYHAEMOGLOBIN" in result.title
        assert result.experimental_method == "X-RAY DIFFRACTION"
        assert result.experimental_method_category == "X-ray"
        assert result.resolution == 1.74
        assert result.r_work == 0.135
        assert result.r_free is None
        assert result.release_date == "1984-07-17T00:00:00Z"
        assert result.molecular_weight == 64.74
        assert len(result.authors) == 2
        assert result.authors[0].name == "Fermi, G."
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_computational(self, client: PdbClient) -> None:
        respx.post(GRAPHQL_URL).mock(
            return_value=Response(200, json=COMPUTATIONAL_RESPONSE),
        )
        result = await client.get("AF_P69905_F1")
        assert result.evidence_label == EvidenceTypeLabel.PREDICTED
        assert result.experimental_method == "COMPUTATIONAL MODEL"
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_nonexistent(self, client: PdbClient) -> None:
        respx.post(GRAPHQL_URL).mock(
            return_value=Response(200, json=NOT_FOUND_RESPONSE),
        )
        with pytest.raises(ReferenceError, match="PDB API error"):
            await client.get("4ZZZ")
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_search(self, client: PdbClient) -> None:
        respx.post(SEARCH_URL).mock(
            return_value=Response(200, json=SEARCH_RESPONSE),
        )
        result = await client.search_by_resolution(2.0)
        assert isinstance(result, PdbSearchResult)
        assert result.total_count == 3
        assert result.pdb_ids == ["4HHB", "1A3N", "2DN1"]
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_empty(self, client: PdbClient) -> None:
        respx.post(SEARCH_URL).mock(
            return_value=Response(200, json=SEARCH_EMPTY),
        )
        result = await client.search_by_author("Nonexistent")
        assert result.total_count == 0
        assert result.pdb_ids == []
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_by_ligand(self, client: PdbClient) -> None:
        respx.post(SEARCH_URL).mock(
            return_value=Response(200, json=SEARCH_RESPONSE),
        )
        result = await client.search_by_ligand("HEM")
        assert len(result.pdb_ids) == 3
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_by_sequence(self, client: PdbClient) -> None:
        respx.post(SEARCH_URL).mock(
            return_value=Response(200, json=SEARCH_RESPONSE),
        )
        result = await client.search_by_sequence("VLSPADKTNVK")
        assert len(result.pdb_ids) == 3
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_http_error(self, client: PdbClient) -> None:
        respx.post(GRAPHQL_URL).mock(
            return_value=Response(429, json={}),
        )
        with pytest.raises(ReferenceError, match="PDB API error: 429"):
            await client.get("4HHB")
        await client.close()

    @pytest.mark.asyncio
    async def test_close(self, client: PdbClient) -> None:
        await client.close()


class TestPdbEvidence:
    def test_experimental_method(self) -> None:
        assert (
            PdbClient._extract_evidence_label(
                "experimental",
                "X-RAY DIFFRACTION",
            )
            == EvidenceTypeLabel.EXPERIMENTAL
        )

    def test_computational_method(self) -> None:
        assert (
            PdbClient._extract_evidence_label(
                "computational",
                "COMPUTATIONAL MODEL",
            )
            == EvidenceTypeLabel.PREDICTED
        )

    def test_integrative_method(self) -> None:
        assert (
            PdbClient._extract_evidence_label(
                "integrative",
                "ELECTRON MICROSCOPY",
            )
            == EvidenceTypeLabel.REVIEWED
        )


class TestPdbQuality:
    def test_filter_by_resolution(self) -> None:
        results = [
            PdbStructureResult(pdb_id="1ABC", resolution=1.5),
            PdbStructureResult(pdb_id="2DEF", resolution=2.5),
            PdbStructureResult(pdb_id="3GHI", resolution=None),
        ]
        filtered = PdbClient.filter_by_resolution(results, 2.0)
        assert len(filtered) == 1
        assert filtered[0].pdb_id == "1ABC"

    def test_filter_by_resolution_empty(self) -> None:
        assert PdbClient.filter_by_resolution([], 2.0) == []

    def test_check_quality_pass(self) -> None:
        result = PdbStructureResult(
            pdb_id="4HHB",
            experimental_method="X-RAY DIFFRACTION",
            r_work=0.135,
            r_free=0.18,
        )
        assert PdbClient.check_quality(result) is True

    def test_check_quality_fail(self) -> None:
        result = PdbStructureResult(
            pdb_id="BAD",
            experimental_method="X-RAY DIFFRACTION",
            r_work=0.5,
            r_free=0.6,
        )
        assert PdbClient.check_quality(result, max_r_work=0.3, max_r_free=0.4) is False

    def test_check_quality_no_experimental(self) -> None:
        result = PdbStructureResult(pdb_id="NOPE")
        assert PdbClient.check_quality(result) is False


class TestPdbParsing:
    def test_parse_authors(self) -> None:
        raw = [{"name": "Fermi, G."}, {"name": "Perutz, M.F."}]
        authors = PdbClient._parse_authors(raw)
        assert len(authors) == 2
        assert authors[0].name == "Fermi, G."
        assert authors[1].name == "Perutz, M.F."

    def test_parse_authors_empty(self) -> None:
        assert PdbClient._parse_authors([]) == []

    def test_parse_citation(self) -> None:
        raw = {
            "title": "Test title",
            "journal_abbrev": "J.Test",
            "year": 2024,
            "pdbx_database_id_DOI": "10.1234/test",
            "pdbx_database_id_PubMed": 12345,
            "rcsb_authors": ["Alice", "Bob"],
        }
        citation = PdbClient._parse_citation(raw)
        assert citation is not None
        assert citation.title == "Test title"
        assert citation.journal == "J.Test"
        assert citation.year == 2024
        assert citation.doi == "10.1234/test"
        assert citation.pubmed_id == 12345
        assert citation.authors == ["Alice", "Bob"]

    def test_parse_citation_none(self) -> None:
        assert PdbClient._parse_citation(None) is None

    def test_parse_citation_empty(self) -> None:
        assert PdbClient._parse_citation({}) is None

    def test_parse_polymer_entities(self) -> None:
        raw = [
            {
                "rcsb_id": "4HHB_1",
                "entity_poly": {
                    "rcsb_entity_polymer_type": "Protein",
                    "pdbx_seq_one_letter_code_can": "VLSPADKTNVK",
                },
                "rcsb_polymer_entity_container_identifiers": {
                    "asym_ids": ["A", "C"],
                },
                "uniprots": [{"rcsb_uniprot_accession": ["P69905"]}],
                "pfams": [{"rcsb_pfam_accession": "PF00042"}],
            },
        ]
        entities = PdbClient._parse_polymer_entities(raw)
        assert len(entities) == 1
        assert entities[0].entity_id == "4HHB_1"
        assert entities[0].polymer_type == "Protein"
        assert entities[0].sequence == "VLSPADKTNVK"
        assert entities[0].chain_ids == ["A", "C"]
        assert entities[0].uniprot_accessions == ["P69905"]
        assert entities[0].pfam_accessions == ["PF00042"]

    def test_parse_polymer_entities_empty(self) -> None:
        assert PdbClient._parse_polymer_entities([]) == []


class TestPdbCrossReferences:
    @pytest.mark.asyncio
    @respx.mock
    async def test_cross_reference_extraction(self, client: PdbClient) -> None:
        respx.post(GRAPHQL_URL).mock(
            return_value=Response(200, json=STRUCTURE_RESPONSE),
        )
        result = await client.get("4HHB")
        uniprot_ids = {x.identifier for x in result.cross_references if x.database == "UniProt"}
        assert "P69905" in uniprot_ids
        assert "P68871" in uniprot_ids
        pfam_ids = {x.identifier for x in result.cross_references if x.database == "Pfam"}
        assert "PF00042" in pfam_ids
        emdb_ids = {x.identifier for x in result.cross_references if x.database == "EMDB"}
        assert "EMD-1234" in emdb_ids
        pubmed_ids = {x.identifier for x in result.cross_references if x.database == "PubMed"}
        assert "6726807" in pubmed_ids
        go_names = {x.identifier for x in result.cross_references if x.database == "GO"}
        assert "hemoglobin complex" in go_names
        interpro_names = {x.identifier for x in result.cross_references if x.database == "InterPro"}
        assert "Hemoglobin, alpha-type" in interpro_names
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_cross_reference_pubmed(self, client: PdbClient) -> None:
        respx.post(GRAPHQL_URL).mock(
            return_value=Response(200, json=STRUCTURE_RESPONSE),
        )
        result = await client.get("4HHB")
        pubmed_xrefs = [x for x in result.cross_references if x.database == "PubMed"]
        assert len(pubmed_xrefs) == 1
        assert pubmed_xrefs[0].identifier == "6726807"
        await client.close()


class TestPdbFullParse:
    @pytest.mark.asyncio
    @respx.mock
    async def test_full_structure_parse(self, client: PdbClient) -> None:
        respx.post(GRAPHQL_URL).mock(
            return_value=Response(200, json=STRUCTURE_RESPONSE),
        )
        result = await client.get("4HHB")
        assert result.pdb_id == "4HHB"
        assert "DEOXYHAEMOGLOBIN" in result.title
        assert result.experimental_method == "X-RAY DIFFRACTION"
        assert result.experimental_method_category == "X-ray"
        assert result.structure_determination_methodology == "experimental"
        assert result.resolution == 1.74
        assert result.r_work == 0.135
        assert result.release_date == "1984-07-17T00:00:00Z"
        assert result.molecular_weight == 64.74
        assert result.evidence_label == EvidenceTypeLabel.EXPERIMENTAL
        assert len(result.authors) == 2
        assert result.polymer_entities is not None
        assert len(result.polymer_entities) == 2
        assert result.citation is not None
        assert result.citation.pubmed_id == 6726807
        assert result.citation.doi == "10.1016/0022-2836(84)90472-8"
        xref_dbs = {x.database for x in result.cross_references}
        assert "UniProt" in xref_dbs
        assert "Pfam" in xref_dbs
        assert "GO" in xref_dbs
        assert "InterPro" in xref_dbs
        assert "PubMed" in xref_dbs
        assert "EMDB" in xref_dbs
        assert "SCOP" in xref_dbs
        await client.close()

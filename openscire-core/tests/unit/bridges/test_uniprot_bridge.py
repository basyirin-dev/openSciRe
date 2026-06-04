# SPDX-License-Identifier: Apache-2.0

import pytest
import respx
from httpx import Response
from openscire.bridge.evidence_label import EvidenceTypeLabel
from openscire.bridges.uniprot import (
    UniProtClient,
    UniProtQueryBuilder,
    UniProtResult,
    UniProtSearchResult,
)
from openscire.exceptions import ReferenceError

SWISSPROT_ENTRY = {
    "primaryAccession": "Q12888",
    "uniProtkbId": "TP53B_HUMAN",
    "entryType": "UniProtKB reviewed (Swiss-Prot)",
    "proteinDescription": {
        "recommendedName": {
            "fullName": {"value": "TP53-binding protein 1"},
        },
        "alternativeNames": [
            {"fullName": {"value": "p53-binding protein 1"}},
            {"fullName": {"value": "53BP1"}},
        ],
    },
    "genes": [
        {
            "geneName": {"value": "TP53BP1"},
            "synonyms": [{"value": "53BP1"}],
        },
    ],
    "organism": {
        "scientificName": "Homo sapiens",
        "taxonId": 9606,
    },
    "proteinExistence": "1: Evidence at protein level",
    "comments": [
        {
            "commentType": "FUNCTION",
            "texts": [
                {
                    "value": "Double-strand break repair protein.",
                    "evidences": [{"evidenceCode": "ECO:0000269"}],
                },
            ],
        },
        {
            "commentType": "SUBCELLULAR LOCATION",
            "texts": [
                {
                    "value": "Nucleus.",
                    "evidences": [{"evidenceCode": "ECO:0000269"}],
                },
                {
                    "value": "Chromosome.",
                    "evidences": [{"evidenceCode": "ECO:0000269"}],
                },
            ],
        },
        {
            "commentType": "PTM",
            "texts": [
                {
                    "value": "Phosphorylated by ATM.",
                    "evidences": [{"evidenceCode": "ECO:0000269"}],
                },
            ],
        },
    ],
    "features": [
        {
            "type": "Chain",
            "description": "TP53-binding protein 1",
            "featureId": "PRO_0000072643",
            "location": {"start": {"value": 1}, "end": {"value": 1972}},
            "evidences": [{"evidenceCode": "ECO:0000269"}],
        },
        {
            "type": "Domain",
            "description": "BRCT 1",
            "featureId": "",
            "location": {},
            "evidences": [],
        },
    ],
    "sequence": {
        "length": 1972,
        "molWeight": 213574,
        "value": "MAAAAA",
    },
    "uniProtKBCrossReferences": [
        {"database": "PDB", "id": "1KZY", "properties": [{"key": "method", "value": "X-ray"}]},
        {"database": "PDB", "id": "2LVM", "properties": []},
        {"database": "EMBL", "id": "AF078776", "properties": []},
        {"database": "Pfam", "id": "PF00633",
         "properties": [{"key": "description", "value": "BRCT"}]},
        {"database": "InterPro", "id": "IPR001357", "properties": []},
        {"database": "STRING", "id": "9606.ENSP00000415927", "properties": []},
        {"database": "Reactome", "id": "R-HSA-5693565", "properties": []},
        {"database": "GO", "id": "GO:0005634",
         "properties": [{"key": "term", "value": "nucleus"}]},
        {"database": "GO", "id": "GO:0006974",
         "properties": [{"key": "term", "value": "DNA damage"}]},
        {"database": "AlphaFoldDB", "id": "Q12888", "properties": []},
        {"database": "BioGRID", "id": "123456", "properties": []},
    ],
    "entryAudit": {
        "firstPublicDate": "1998-07-15",
        "lastAnnotationUpdateDate": "2026-01-28",
        "lastSequenceUpdateDate": "2000-12-01",
        "entryVersion": 244,
        "sequenceVersion": 2,
    },
    "keywords": [
        {"name": "DNA damage"},
        {"name": "Nucleus"},
        {"name": "Phosphoprotein"},
    ],
    "annotationScore": 5.0,
    "secondaryAccessions": ["Q9Y4A3", "Q9Y4A4"],
}

TREMBL_ENTRY = {
    "primaryAccession": "A0A015JYU2",
    "uniProtkbId": "A0A015JYU2_RHIIW",
    "entryType": "UniProtKB unreviewed (TrEMBL)",
    "proteinDescription": {
        "recommendedName": {
            "fullName": {"value": "Putative uncharacterized protein"},
        },
    },
    "genes": [],
    "organism": {
        "scientificName": "Rhizopus",
        "taxonId": 4843,
    },
    "proteinExistence": "3: Inferred from homology",
    "comments": [
        {
            "commentType": "FUNCTION",
            "texts": [
                {
                    "value": "Hypothetical function.",
                    "evidences": [{"evidenceCode": "ECO:0000256"}],
                },
            ],
        },
    ],
    "features": [],
    "sequence": {
        "length": 863,
        "molWeight": 95000,
        "value": "MSK",
    },
    "uniProtKBCrossReferences": [],
    "entryAudit": {
        "firstPublicDate": "2015-01-01",
        "lastAnnotationUpdateDate": "2025-06-01",
        "lastSequenceUpdateDate": "2015-01-01",
        "entryVersion": 42,
        "sequenceVersion": 1,
    },
    "keywords": [],
    "annotationScore": 3.0,
    "secondaryAccessions": [],
}

SEARCH_RESPONSE = {
    "results": [SWISSPROT_ENTRY],
    "pageInfo": {
        "totalRecords": 1,
        "size": 25,
        "offset": 0,
    },
}

SEARCH_EMPTY = {
    "results": [],
    "pageInfo": {
        "totalRecords": 0,
        "size": 25,
        "offset": 0,
    },
}


@pytest.fixture
def client() -> UniProtClient:
    return UniProtClient(rate=100.0, burst=10)


class TestUniProtQueryBuilder:
    def test_organism_filter(self) -> None:
        qb = UniProtQueryBuilder()
        qb.organism(9606)
        assert qb.build() == "organism_id:9606"

    def test_chained_filters(self) -> None:
        qb = UniProtQueryBuilder()
        qb.organism(9606).gene("TP53").reviewed(True)
        assert qb.build() == "organism_id:9606 AND gene:TP53 AND reviewed:true"

    def test_sequence_length_range(self) -> None:
        qb = UniProtQueryBuilder()
        qb.sequence_length(100, 500)
        assert qb.build() == "length:[100 TO 500]"

    def test_sequence_length_min_only(self) -> None:
        qb = UniProtQueryBuilder()
        qb.sequence_length(min_len=100)
        assert qb.build() == "length:[100 TO *]"

    def test_taxonomy_filter(self) -> None:
        qb = UniProtQueryBuilder()
        qb.taxonomy("Homo sapiens")
        assert qb.build() == "taxonomy_name:Homo sapiens"

    def test_protein_filter(self) -> None:
        qb = UniProtQueryBuilder()
        qb.protein("p53")
        assert qb.build() == "protein_name:p53"


class TestUniProtClient:
    @pytest.mark.asyncio
    @respx.mock
    async def test_search(self, client: UniProtClient) -> None:
        respx.get("https://rest.uniprot.org/uniprotkb/search").mock(
            return_value=Response(200, json=SEARCH_RESPONSE),
        )
        result = await client.search("TP53BP1")
        assert isinstance(result, UniProtSearchResult)
        assert result.total_count == 1
        assert len(result.results) == 1
        entry = result.results[0]
        assert entry.primary_accession == "Q12888"
        assert entry.entry_name == "TP53B_HUMAN"
        assert entry.is_reviewed is True
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_with_query_builder(self, client: UniProtClient) -> None:
        respx.get("https://rest.uniprot.org/uniprotkb/search").mock(
            return_value=Response(200, json=SEARCH_RESPONSE),
        )
        qb = UniProtQueryBuilder().organism(9606).gene("TP53BP1")
        result = await client.search(qb)
        assert result.total_count == 1
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_empty(self, client: UniProtClient) -> None:
        respx.get("https://rest.uniprot.org/uniprotkb/search").mock(
            return_value=Response(200, json=SEARCH_EMPTY),
        )
        result = await client.search("nonexistent")
        assert result.total_count == 0
        assert result.results == []
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_by_accession(self, client: UniProtClient) -> None:
        respx.get("https://rest.uniprot.org/uniprotkb/Q12888").mock(
            return_value=Response(200, json=SWISSPROT_ENTRY),
        )
        entry = await client.get("Q12888")
        assert isinstance(entry, UniProtResult)
        assert entry.primary_accession == "Q12888"
        assert entry.entry_name == "TP53B_HUMAN"
        assert entry.entry_type == "UniProtKB reviewed (Swiss-Prot)"
        assert entry.is_reviewed is True
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_trembl_entry(self, client: UniProtClient) -> None:
        respx.get("https://rest.uniprot.org/uniprotkb/A0A015JYU2").mock(
            return_value=Response(200, json=TREMBL_ENTRY),
        )
        entry = await client.get("A0A015JYU2")
        assert entry.primary_accession == "A0A015JYU2"
        assert entry.is_reviewed is False
        assert entry.evidence_label == EvidenceTypeLabel.PREDICTED
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_nonexistent(self, client: UniProtClient) -> None:
        respx.get("https://rest.uniprot.org/uniprotkb/NOPE").mock(
            return_value=Response(404, json={"error": "Not found"}),
        )
        with pytest.raises(ReferenceError, match="UniProt API error: 404"):
            await client.get("NOPE")
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_http_error(self, client: UniProtClient) -> None:
        respx.get("https://rest.uniprot.org/uniprotkb/search").mock(
            return_value=Response(429, json={"error": "rate limited"}),
        )
        with pytest.raises(ReferenceError, match="UniProt API error: 429"):
            await client.search("test")
        await client.close()

    @pytest.mark.asyncio
    async def test_close(self, client: UniProtClient) -> None:
        await client.close()


class TestUniProtParsing:
    def test_extract_protein_names(self) -> None:
        pd = {
            "recommendedName": {"fullName": {"value": "TP53-binding protein 1"}},
            "alternativeNames": [
                {"fullName": {"value": "p53-binding protein 1"}},
                {"fullName": {"value": "53BP1"}},
            ],
        }
        names = UniProtClient._extract_protein_names(pd)
        assert names == ["TP53-binding protein 1", "p53-binding protein 1", "53BP1"]

    def test_extract_protein_names_empty(self) -> None:
        assert UniProtClient._extract_protein_names({}) == []

    def test_extract_gene_names(self) -> None:
        genes = [
            {
                "geneName": {"value": "TP53BP1"},
                "synonyms": [{"value": "53BP1"}],
            },
        ]
        names = UniProtClient._extract_gene_names(genes)
        assert names == ["TP53BP1", "53BP1"]

    def test_extract_gene_names_empty(self) -> None:
        assert UniProtClient._extract_gene_names([]) == []

    def test_extract_comments(self) -> None:
        comments = [
            {
                "commentType": "FUNCTION",
                "texts": [
                    {"value": "Repair protein.", "evidences": [{"evidenceCode": "ECO:0000269"}]},
                ],
            },
            {
                "commentType": "SUBCELLULAR LOCATION",
                "texts": [
                    {"value": "Nucleus.", "evidences": [{"evidenceCode": "ECO:0000269"}]},
                    {"value": "Chromosome.", "evidences": [{"evidenceCode": "ECO:0000269"}]},
                ],
            },
            {
                "commentType": "PTM",
                "texts": [
                    {"value": "Phosphorylated.", "evidences": [{"evidenceCode": "ECO:0000269"}]},
                ],
            },
        ]
        function, subcellular, ptms, parsed = UniProtClient._extract_comments(comments)
        assert function == "Repair protein."
        assert subcellular == ["Nucleus.", "Chromosome."]
        assert ptms == ["Phosphorylated."]
        assert len(parsed) == 3
        assert parsed[0].comment_type == "FUNCTION"

    def test_extract_comments_empty(self) -> None:
        function, subcellular, ptms, parsed = UniProtClient._extract_comments([])
        assert function == ""
        assert subcellular == []
        assert ptms == []
        assert parsed == []

    def test_parse_features(self) -> None:
        features = [
            {
                "type": "Chain",
                "description": "TP53-binding protein 1",
                "featureId": "PRO_0000072643",
                "location": {"start": {"value": 1}, "end": {"value": 1972}},
                "evidences": [{"evidenceCode": "ECO:0000269"}],
            },
            {
                "type": "Domain",
                "description": "BRCT 1",
                "featureId": "",
                "location": {},
                "evidences": [],
            },
        ]
        parsed = UniProtClient._parse_features(features)
        assert len(parsed) == 2
        assert parsed[0].type == "Chain"
        assert parsed[0].description == "TP53-binding protein 1"
        assert parsed[0].feature_id == "PRO_0000072643"
        assert parsed[0].start == 1
        assert parsed[0].end == 1972
        assert parsed[0].evidence_codes == ["ECO:0000269"]
        assert parsed[1].type == "Domain"
        assert parsed[1].evidence_codes == []

    def test_parse_features_empty(self) -> None:
        assert UniProtClient._parse_features([]) == []


class TestUniProtEvidence:
    def test_evidence_label_swissprot(self) -> None:
        label = UniProtClient._extract_evidence_label("UniProtKB reviewed (Swiss-Prot)")
        assert label == EvidenceTypeLabel.EXPERIMENTAL

    def test_evidence_label_trembl(self) -> None:
        label = UniProtClient._extract_evidence_label("UniProtKB unreviewed (TrEMBL)")
        assert label == EvidenceTypeLabel.PREDICTED

    def test_evidence_codes_extraction(self) -> None:
        evidences = [
            {"evidenceCode": "ECO:0000269"},
            {"evidenceCode": "ECO:0000256"},
        ]
        codes = UniProtClient._extract_evidence_codes(evidences)
        assert codes == ["ECO:0000269", "ECO:0000256"]

    def test_evidence_codes_empty(self) -> None:
        assert UniProtClient._extract_evidence_codes([]) == []


class TestUniProtEntryAudit:
    def test_entry_audit_tracking(self) -> None:
        audit = {
            "entryVersion": 244,
            "sequenceVersion": 2,
            "firstPublicDate": "1998-07-15",
            "lastAnnotationUpdateDate": "2026-01-28",
            "lastSequenceUpdateDate": "2000-12-01",
        }
        result = UniProtClient._extract_entry_audit(audit)
        assert result["entry_version"] == 244
        assert result["sequence_version"] == 2
        assert result["first_public_date"] == "1998-07-15"

    def test_entry_audit_empty(self) -> None:
        result = UniProtClient._extract_entry_audit({})
        assert result["entry_version"] == 0


class TestUniProtCrossReferences:
    def test_cross_reference_extraction(self) -> None:
        xrefs = [
            {"database": "PDB", "id": "1KZY", "properties": [{"key": "method", "value": "X-ray"}]},
            {"database": "PDB", "id": "2LVM", "properties": []},
            {"database": "EMBL", "id": "AF078776", "properties": []},
            {"database": "Pfam", "id": "PF00633",
             "properties": [{"key": "description", "value": "BRCT"}]},
            {"database": "InterPro", "id": "IPR001357", "properties": []},
            {"database": "STRING", "id": "9606.ENSP00000415927", "properties": []},
            {"database": "Reactome", "id": "R-HSA-5693565", "properties": []},
            {"database": "GO", "id": "GO:0005634",
             "properties": [{"key": "term", "value": "nucleus"}]},
            {"database": "GO", "id": "GO:0006974",
             "properties": [{"key": "term", "value": "DNA damage"}]},
        ]
        parsed = UniProtClient._extract_cross_references(xrefs)
        assert len(parsed) == 9  # all target databases
        pdb_refs = [x for x in parsed if x.database == "PDB"]
        assert len(pdb_refs) == 2
        assert pdb_refs[0].properties.get("method") == "X-ray"
        go_refs = [x for x in parsed if x.database == "GO"]
        assert len(go_refs) == 2

    def test_cross_reference_filtering(self) -> None:
        xrefs = [
            {"database": "PDB", "id": "1KZY", "properties": []},
            {"database": "AlphaFoldDB", "id": "Q12888", "properties": []},
            {"database": "BioGRID", "id": "123456", "properties": []},
        ]
        parsed = UniProtClient._extract_cross_references(xrefs)
        # Only PDB is in target; AlphaFoldDB and BioGRID should be filtered out
        assert len(parsed) == 1
        assert parsed[0].database == "PDB"

    def test_cross_reference_empty(self) -> None:
        assert UniProtClient._extract_cross_references([]) == []

    def test_cross_reference_no_id_skipped(self) -> None:
        xrefs = [
            {"database": "PDB", "id": "", "properties": []},
        ]
        assert UniProtClient._extract_cross_references(xrefs) == []


class TestUniProtFullParse:
    @pytest.mark.asyncio
    @respx.mock
    async def test_full_entry_parse(self, client: UniProtClient) -> None:
        respx.get("https://rest.uniprot.org/uniprotkb/Q12888").mock(
            return_value=Response(200, json=SWISSPROT_ENTRY),
        )
        entry = await client.get("Q12888")
        assert entry.protein_names == [
            "TP53-binding protein 1",
            "p53-binding protein 1",
            "53BP1",
        ]
        assert entry.gene_names == ["TP53BP1", "53BP1"]
        assert entry.organism == "Homo sapiens"
        assert entry.organism_taxon_id == 9606
        assert entry.protein_existence == "1: Evidence at protein level"
        assert entry.function == "Double-strand break repair protein."
        assert entry.subcellular_location == ["Nucleus.", "Chromosome."]
        assert entry.ptms == ["Phosphorylated by ATM."]
        assert entry.sequence == "MAAAAA"
        assert entry.sequence_length == 1972
        assert entry.molecular_weight == 213574
        assert entry.evidence_label == EvidenceTypeLabel.EXPERIMENTAL
        assert entry.entry_version == 244
        assert entry.sequence_version == 2
        assert entry.first_public_date == "1998-07-15"
        assert entry.last_annotation_update == "2026-01-28"
        assert entry.last_sequence_update == "2000-12-01"
        assert len(entry.keywords) == 3
        assert len(entry.features) == 2
        assert len(entry.comments) == 3
        assert len(entry.cross_references) > 0
        assert entry.extra.get("annotation_score") == 5.0
        await client.close()

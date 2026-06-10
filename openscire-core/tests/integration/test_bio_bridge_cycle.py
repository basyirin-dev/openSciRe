# SPDX-License-Identifier: Apache-2.0

"""Integration test: UniProt -> AlphaFold -> confidence -> PDB cross-ref.

Tests the bio-bridge pipeline: fetch a UniProt entry, retrieve its AlphaFold
prediction, propagate confidence traces, and resolve PDB cross-references.
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response
from openscire.bridge.confidence import ConfidenceTrace
from openscire.bridge.evidence_label import EvidencePropagator, EvidenceTypeLabel
from openscire.bridge.resolver import CrossReferenceResolver
from openscire.bridges.alphafold import AlphaFoldClient
from openscire.bridges.pdb import PdbClient
from openscire.bridges.uniprot import UniProtClient

pytestmark = [
    pytest.mark.integration,
]

UNIPROT_ENTRY = {
    "entryType": "UniProtKB_reviewed_%28Swiss-Prot%29",
    "primaryAccession": "P05067",
    "uniProtkbId": "A4_HUMAN",
    "proteinDescription": {
        "recommendedName": {"fullName": {"value": "Amyloid-beta precursor protein"}},
    },
    "genes": [{"geneName": {"value": "APP"}}],
    "organism": {"scientificName": "Homo sapiens", "taxonId": 9606},
    "sequence": {
        "value": "MLPGLALLLLAAWTARALEVPTDGN",
        "length": 21,
        "molWeight": 2345,
        "crc64": "ABC123",
    },
    "features": [
        {
            "type": "MOD_RES",
            "location": {"start": {"value": 1}, "end": {"value": 1}},
            "description": "Phosphorylation site",
        },
    ],
    "entryAudit": {
        "firstPublicDate": "1986-01-01",
        "lastAnnotationUpdate": "2024-06-01",
        "lastSequenceUpdate": "2024-01-01",
        "entryVersion": 42,
    },
    "uniProtKBCrossReferences": [
        {"database": "PDB", "id": "1AAP"},
    ],
    "comments": [
        {
            "commentType": "FUNCTION",
            "texts": [{"value": "Functions in synaptic adhesion."}],
        },
    ],
}

ALPHAFOLD_PREDICTION = [
    {
        "entryId": "AF-P05067-F1",
        "uniprotAccession": "P05067",
        "gene": "APP",
        "organismScientificName": "Homo sapiens",
        "sequence": "MLPGLALLLLAAWTARALEVPTDGN",
        "globalMetricValue": 67.38,
        "latestVersion": 6,
        "pdbUrl": "https://alphafold.ebi.ac.uk/files/AF-P05067-F1-model_v6.pdb",
        "cifUrl": "https://alphafold.ebi.ac.uk/files/AF-P05067-F1-model_v6.cif",
        "paeDocUrl": "https://alphafold.ebi.ac.uk/files/AF-P05067-F1-predicted_aligned_error_v6.json",
        "plddtDocUrl": "https://alphafold.ebi.ac.uk/files/AF-P05067-F1-confidence_v6.json",
        "entityType": "protein",
    },
]

PLDDT_JSON = {
    "residueNumber": [1, 2, 3, 4, 5],
    "confidenceScore": [95.0, 88.0, 45.0, 72.0, 30.0],
    "confidenceCategory": [
        "VERY HIGH",
        "HIGH",
        "LOW",
        "CONFIDENT",
        "VERY LOW",
    ],
}

PAE_JSON = [
    {
        "predicted_aligned_error": [
            [0.0, 2.0, 3.0, 10.0],
            [2.0, 0.0, 2.5, 12.0],
            [3.0, 2.5, 0.0, 11.0],
            [10.0, 12.0, 11.0, 0.0],
        ],
    },
]

PDB_GRAPHQL_RESPONSE = {
    "data": {
        "entry": {
            "rcsb_id": "1AAP",
            "struct_title": "Amyloid Precursor Protein Structure",
            "exptl": [{"method": "X-RAY DIFFRACTION"}],
            "rcsb_entry_info": {
                "resolution_combined": [2.3],
                "r_free": [0.25],
                "r_work": [0.22],
            },
            "rcsb_accession_info": {"initial_release_date": "2020-01-01"},
            "rcsb_entity_source_organism": [{"scientific_name": "Homo sapiens"}],
            "polymer_entities": [
                {
                    "entity_poly": {
                        "pdbx_strand_id": "A",
                        "type": "polypeptide(L)",
                    },
                    "rcsb_entity_host_organism": None,
                },
            ],
        },
    },
}


class TestBioBridgeCycle:
    """UniProt -> AlphaFold -> confidence -> PDB cross-ref."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_uniprot_alphafold_confidence_cycle(self) -> None:
        uni = UniProtClient()
        af = AlphaFoldClient()

        respx.get("https://rest.uniprot.org/uniprotkb/P05067").mock(
            return_value=Response(200, json=UNIPROT_ENTRY),
        )
        respx.get("https://alphafold.ebi.ac.uk/api/prediction/P05067").mock(
            return_value=Response(200, json=ALPHAFOLD_PREDICTION),
        )
        respx.get(ALPHAFOLD_PREDICTION[0]["plddtDocUrl"]).mock(
            return_value=Response(200, json=PLDDT_JSON),
        )
        respx.get(ALPHAFOLD_PREDICTION[0]["paeDocUrl"]).mock(
            return_value=Response(200, json=PAE_JSON),
        )

        entry = await uni.get("P05067")
        assert entry.primary_accession == "P05067"
        assert "APP" in entry.gene_names
        assert entry.evidence_label == EvidenceTypeLabel.EXPERIMENTAL

        predictions = await af.fetch_prediction("P05067")
        assert len(predictions) >= 1
        pred = predictions[0]
        assert pred.uniprot_accession == "P05067"
        assert pred.gene == "APP"
        assert pred.evidence_label == EvidenceTypeLabel.PREDICTED

        conf = await af.fetch_plddt(pred)
        assert conf is not None
        assert len(conf) == 5

        avg_plddt = sum(c.plddt_score for c in conf) / len(conf)
        ct = ConfidenceTrace(value=avg_plddt / 100.0, source="alphafold_plddt")
        assert 0.0 <= ct.value <= 1.0

        pae = await af.fetch_pae(pred)
        assert pae is not None
        assert isinstance(pae.pae_values, list)

        warnings = af.check_confidence(pred, cutoff=70.0)
        assert isinstance(warnings, list)

        disorder = await af.fetch_disorder_report(pred)
        assert disorder is not None
        assert len(disorder.regions) > 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_pdb_crossref_cycle(self) -> None:
        uni = UniProtClient()
        pdb = PdbClient()

        respx.get("https://rest.uniprot.org/uniprotkb/P05067").mock(
            return_value=Response(200, json=UNIPROT_ENTRY),
        )
        respx.post("https://data.rcsb.org/graphql").mock(
            return_value=Response(200, json=PDB_GRAPHQL_RESPONSE),
        )

        entry = await uni.get("P05067")
        pdb_ids = [x.identifier for x in entry.cross_references if x.database == "PDB"]
        assert len(pdb_ids) >= 1
        assert pdb_ids[0] == "1AAP"

        struct = await pdb.get(pdb_ids[0])
        assert struct is not None
        assert struct.pdb_id == "1AAP"
        assert struct.experimental_method == "X-RAY DIFFRACTION"
        assert struct.evidence_label == EvidenceTypeLabel.EXPERIMENTAL

        filtered = PdbClient.filter_by_resolution([struct], max_res=3.0)
        assert len(filtered) == 1

        is_quality = PdbClient.check_quality(struct, max_r_free=0.3, max_r_work=0.25)
        assert is_quality

    @pytest.mark.asyncio
    @respx.mock
    async def test_crossref_resolver_cycle(self) -> None:
        resolver = CrossReferenceResolver()

        respx.get("https://www.ebi.ac.uk/pdbe/api/mappings/1aap").respond(
            json={
                "1aap": {
                    "UniProt": {
                        "P05067": [
                            {"identifier": "P05067", "molecule_name": "APP"},
                        ],
                    },
                },
            },
        )

        results = await resolver.pdb_to_uniprot("1AAP")
        assert "P05067" in results

    async def test_evidence_label_chain(self) -> None:
        combined = EvidencePropagator.combine(
            [
                EvidenceTypeLabel.EXPERIMENTAL,
                EvidenceTypeLabel.PREDICTED,
                EvidenceTypeLabel.EXPERIMENTAL,
            ]
        )
        assert combined == EvidenceTypeLabel.EXPERIMENTAL

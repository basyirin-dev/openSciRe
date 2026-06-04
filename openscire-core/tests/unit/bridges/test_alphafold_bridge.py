# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

import pytest
import respx
from httpx import Response
from openscire.bridge.evidence_label import EvidenceTypeLabel
from openscire.bridges.alphafold import (
    AlphaFoldClient,
    AlphaFoldPrediction,
    PaeMatrix,
    ResidueConfidence,
)
from openscire.exceptions import ReferenceError

BASE_URL = "https://alphafold.ebi.ac.uk"


# ── Mock data ──────────────────────────────────────────────────────────────

PREDICTION_RESPONSE = [
    {
        "entryId": "AF-P05067-F1",
        "uniprotAccession": "P05067",
        "uniprotId": "A4_HUMAN",
        "uniprotDescription": "Amyloid-beta precursor protein",
        "gene": "APP",
        "organismScientificName": "Homo sapiens",
        "organismCommonName": "human",
        "taxId": 9606,
        "isUniProtReviewed": True,
        "isUniProtReferenceProteome": True,
        "sequence": "MLPGLALLLLAAWTARALEVPTDGN",
        "globalMetricValue": 67.38,
        "fractionPlddtVeryHigh": 0.288,
        "fractionPlddtConfident": 0.266,
        "fractionPlddtLow": 0.088,
        "fractionPlddtVeryLow": 0.357,
        "latestVersion": 6,
        "allVersions": [1, 2, 3, 4, 5, 6],
        "modelCreatedDate": "2025-08-01T00:00:00Z",
        "pdbUrl": "https://alphafold.ebi.ac.uk/files/AF-P05067-F1-model_v6.pdb",
        "cifUrl": "https://alphafold.ebi.ac.uk/files/AF-P05067-F1-model_v6.cif",
        "bcifUrl": "https://alphafold.ebi.ac.uk/files/AF-P05067-F1-model_v6.bcif",
        "paeDocUrl": "https://alphafold.ebi.ac.uk/files/AF-P05067-F1-predicted_aligned_error_v6.json",
        "plddtDocUrl": "https://alphafold.ebi.ac.uk/files/AF-P05067-F1-confidence_v6.json",
        "paeImageUrl": "https://alphafold.ebi.ac.uk/files/AF-P05067-F1-predicted_aligned_error_v6.png",
        "msaUrl": "https://alphafold.ebi.ac.uk/files/msa/AF-P05067-F1-msa_v6.a3m",
        "isComplex": False,
        "providerId": "GDM",
        "toolUsed": "AlphaFold Monomer v2.0 pipeline",
        "entityType": "protein",
    },
]

PLDDT_RESPONSE = {
    "residueNumber": [1, 2, 3, 4, 5],
    "confidenceScore": [48.28, 37.94, 51.91, 40.59, 40.38],
    "confidenceCategory": ["VL", "VL", "L", "VL", "VL"],
}

PAE_RESPONSE = [
    {
        "predicted_aligned_error": [
            [0.0, 1.0, 3.0, 5.0, 8.0],
            [1.0, 0.0, 2.0, 4.0, 7.0],
            [3.0, 2.0, 0.0, 1.0, 6.0],
            [5.0, 4.0, 1.0, 0.0, 5.0],
            [8.0, 7.0, 6.0, 5.0, 0.0],
        ],
    },
]

PDB_CONTENT = b"ATOM      1  N   ALA A   1       1.234   2.345   3.456  1.00  0.00           C"

CIF_CONTENT = b"data_AF-P05067-F1\n#\n_entry.id AF-P05067-F1\n"

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def client() -> AlphaFoldClient:
    return AlphaFoldClient()


# ── 4.18.1: REST API client ────────────────────────────────────────────────


class TestPredictionAPI:
    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_prediction(self, client: AlphaFoldClient) -> None:
        respx.get(f"{BASE_URL}/api/prediction/P05067").mock(
            return_value=Response(200, json=PREDICTION_RESPONSE),
        )

        results = await client.fetch_prediction("P05067")
        assert len(results) == 1
        pred = results[0]
        assert isinstance(pred, AlphaFoldPrediction)
        assert pred.entry_id == "AF-P05067-F1"
        assert pred.uniprot_accession == "P05067"
        assert pred.uniprot_id == "A4_HUMAN"
        assert pred.gene == "APP"
        assert pred.organism_scientific_name == "Homo sapiens"
        assert pred.tax_id == 9606
        assert pred.is_reviewed is True
        assert pred.is_reference_proteome is True
        assert pred.global_metric_value == 67.38
        assert pred.latest_version == 6
        assert pred.pdb_url.endswith(".pdb")
        assert pred.cif_url.endswith(".cif")
        assert pred.pae_url.endswith(".json")
        assert pred.plddt_url.endswith(".json")
        assert pred.evidence_label == EvidenceTypeLabel.PREDICTED
        assert pred.extra["provider_id"] == "GDM"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_prediction_multiple(self, client: AlphaFoldClient) -> None:
        respx.get(f"{BASE_URL}/api/prediction/P05067").mock(
            return_value=Response(200, json=PREDICTION_RESPONSE),
        )

        results = await client.fetch_prediction_by_accessions(["P05067"])
        assert len(results) == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_prediction_not_found(self, client: AlphaFoldClient) -> None:
        respx.get(f"{BASE_URL}/api/prediction/INVALID").mock(
            return_value=Response(404),
        )

        with pytest.raises(ReferenceError, match="AlphaFold API error: 404"):
            await client.fetch_prediction("INVALID")

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_prediction_network_error(self, client: AlphaFoldClient) -> None:
        import httpx
        respx.get(f"{BASE_URL}/api/prediction/P05067").mock(
            side_effect=httpx.ConnectError("connection failed"),
        )

        with pytest.raises(ReferenceError, match="AlphaFold request failed"):
            await client.fetch_prediction("P05067")

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_by_gene(self, client: AlphaFoldClient) -> None:
        class _MockUniProtClient:
            async def search(self, query: str = "", size: int = 50) -> object:  # noqa: ARG002
                class _Result:
                    primary_accession = "P05067"
                class _SearchResult:
                    results = [_Result()]
                return _SearchResult()

        respx.get(f"{BASE_URL}/api/prediction/P05067").mock(
            return_value=Response(200, json=PREDICTION_RESPONSE),
        )

        results = await client.search_by_gene("APP", _MockUniProtClient())
        assert len(results) == 1
        assert results[0].gene == "APP"
        await client.close()


# ── 4.18.2: Structure download ─────────────────────────────────────────────


class TestStructureDownload:
    @pytest.mark.asyncio
    @respx.mock
    async def test_download_pdb(self, client: AlphaFoldClient) -> None:
        respx.get(f"{BASE_URL}/api/prediction/P05067").mock(
            return_value=Response(200, json=PREDICTION_RESPONSE),
        )
        pdb_url = PREDICTION_RESPONSE[0]["pdbUrl"]
        respx.get(pdb_url).mock(
            return_value=Response(200, content=PDB_CONTENT),
        )

        results = await client.fetch_prediction("P05067")
        content = await client.download_structure(results[0], format="pdb")
        assert content == PDB_CONTENT

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_cif(self, client: AlphaFoldClient) -> None:
        respx.get(f"{BASE_URL}/api/prediction/P05067").mock(
            return_value=Response(200, json=PREDICTION_RESPONSE),
        )
        cif_url = PREDICTION_RESPONSE[0]["cifUrl"]
        respx.get(cif_url).mock(
            return_value=Response(200, content=CIF_CONTENT),
        )

        results = await client.fetch_prediction("P05067")
        content = await client.download_structure(results[0], format="cif")
        assert content == CIF_CONTENT

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_to_file(self, client: AlphaFoldClient, tmp_path: Any) -> None:  # noqa: ANN401
        import os
        respx.get(f"{BASE_URL}/api/prediction/P05067").mock(
            return_value=Response(200, json=PREDICTION_RESPONSE),
        )
        pdb_url = PREDICTION_RESPONSE[0]["pdbUrl"]
        respx.get(pdb_url).mock(
            return_value=Response(200, content=PDB_CONTENT),
        )

        results = await client.fetch_prediction("P05067")
        out = os.path.join(tmp_path, "test.pdb")
        result_path = await client.download_structure(results[0], output_path=out)
        assert result_path == out
        with open(out, "rb") as f:
            assert f.read() == PDB_CONTENT

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_batch(self, client: AlphaFoldClient, tmp_path: Any) -> None:  # noqa: ANN401
        import os
        respx.get(f"{BASE_URL}/api/prediction/P05067").mock(
            return_value=Response(200, json=PREDICTION_RESPONSE),
        )
        pdb_url = PREDICTION_RESPONSE[0]["pdbUrl"]
        respx.get(pdb_url).mock(
            return_value=Response(200, content=PDB_CONTENT),
        )

        results = await client.fetch_prediction("P05067")
        paths = await client.download_batch(results, str(tmp_path))
        assert len(paths) == 1
        assert os.path.exists(paths[0])
        assert paths[0].endswith(".pdb")

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_no_url(self, client: AlphaFoldClient) -> None:
        pred = AlphaFoldPrediction(entry_id="test")
        with pytest.raises(ReferenceError, match="No PDB URL"):
            await client.download_structure(pred)


# ── 4.18.3: pLDDT confidence propagation ────────────────────────────────────


class TestConfidence:
    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_plddt(self, client: AlphaFoldClient) -> None:
        respx.get(f"{BASE_URL}/api/prediction/P05067").mock(
            return_value=Response(200, json=PREDICTION_RESPONSE),
        )
        plddt_url = PREDICTION_RESPONSE[0]["plddtDocUrl"]
        respx.get(plddt_url).mock(
            return_value=Response(200, json=PLDDT_RESPONSE),
        )

        results = await client.fetch_prediction("P05067")
        residues = await client.fetch_plddt(results[0])
        assert len(residues) == 5
        assert residues[0].residue_number == 1
        assert residues[0].plddt_score == 48.28
        assert residues[0].confidence_category == "VL"
        assert residues[0].is_disordered is True
        assert residues[2].plddt_score == 51.91
        assert residues[2].confidence_category == "L"
        assert residues[2].is_disordered is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_plddt_no_url(self, client: AlphaFoldClient) -> None:
        pred = AlphaFoldPrediction(entry_id="test")
        with pytest.raises(ReferenceError, match="No pLDDT URL"):
            await client.fetch_plddt(pred)

    def test_get_confidence_trace(self, client: AlphaFoldClient) -> None:
        pred = AlphaFoldPrediction(entry_id="test", global_metric_value=75.0)
        trace = client.get_confidence_trace(pred)
        assert trace.value == 0.75
        assert trace.source == "alphafold"

    def test_get_per_residue_trace(self, client: AlphaFoldClient) -> None:
        residues = [
            ResidueConfidence(residue_number=1, plddt_score=80.0),
            ResidueConfidence(residue_number=2, plddt_score=60.0),
        ]
        trace = client.get_per_residue_trace(residues)
        assert isinstance(trace.value, float)
        assert trace.source == "alphafold"
        assert len(trace.children) == 2
        assert trace.children[0].value == 0.8
        assert trace.children[1].value == 0.6


# ── 4.18.4: PAE data extraction ─────────────────────────────────────────────


class TestPAE:
    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_pae(self, client: AlphaFoldClient) -> None:
        respx.get(f"{BASE_URL}/api/prediction/P05067").mock(
            return_value=Response(200, json=PREDICTION_RESPONSE),
        )
        pae_url = PREDICTION_RESPONSE[0]["paeDocUrl"]
        respx.get(pae_url).mock(
            return_value=Response(200, json=PAE_RESPONSE),
        )

        results = await client.fetch_prediction("P05067")
        pae = await client.fetch_pae(results[0])
        assert isinstance(pae, PaeMatrix)
        assert pae.residue_count == 5
        assert len(pae.pae_values) == 5
        assert pae.pae_values[0][0] == 0.0
        assert pae.pae_values[0][1] == 1.0

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_pae_no_url(self, client: AlphaFoldClient) -> None:
        pred = AlphaFoldPrediction(entry_id="test")
        with pytest.raises(ReferenceError, match="No PAE URL"):
            await client.fetch_pae(pred)

    def test_domain_clustering(self) -> None:
        matrix = [
            [0.0, 1.0, 6.0, 7.0],
            [1.0, 0.0, 6.0, 7.0],
            [6.0, 6.0, 0.0, 1.0],
            [7.0, 7.0, 1.0, 0.0],
        ]
        domains = AlphaFoldClient._cluster_domains(matrix, threshold=5.0)
        assert len(domains) == 2
        assert domains[0].start == 0
        assert domains[0].end == 1
        assert domains[0].size == 2
        assert domains[1].start == 2
        assert domains[1].end == 3
        assert domains[1].size == 2

    def test_domain_clustering_single(self) -> None:
        matrix = [
            [0.0, 1.0],
            [1.0, 0.0],
        ]
        domains = AlphaFoldClient._cluster_domains(matrix, threshold=5.0)
        assert len(domains) == 1
        assert domains[0].size == 2

    def test_domain_clustering_empty(self) -> None:
        domains = AlphaFoldClient._cluster_domains([])
        assert domains == []


# ── 4.18.5: Explicit P-labeling ─────────────────────────────────────────────


class TestEvidenceLabeling:
    def test_predicted_label_default(self) -> None:
        pred = AlphaFoldPrediction()
        assert pred.evidence_label == EvidenceTypeLabel.PREDICTED

    def test_check_confidence_below_cutoff(self) -> None:
        client = AlphaFoldClient(confidence_cutoff=70.0)
        pred = AlphaFoldPrediction(global_metric_value=65.0)
        warnings = client.check_confidence(pred)
        assert len(warnings) == 1
        assert "below confidence cutoff" in warnings[0]

    def test_check_confidence_above_cutoff(self) -> None:
        client = AlphaFoldClient(confidence_cutoff=70.0)
        pred = AlphaFoldPrediction(global_metric_value=85.0)
        warnings = client.check_confidence(pred)
        assert warnings == []

    def test_check_confidence_custom_cutoff(self) -> None:
        client = AlphaFoldClient()
        pred = AlphaFoldPrediction(global_metric_value=65.0)
        warnings = client.check_confidence(pred, cutoff=60.0)
        assert warnings == []

    def test_check_residue_confidence(self) -> None:
        residues = [
            ResidueConfidence(residue_number=1, plddt_score=50.0),
            ResidueConfidence(residue_number=2, plddt_score=80.0),
            ResidueConfidence(residue_number=3, plddt_score=60.0),
        ]
        client = AlphaFoldClient()
        warnings = client.check_residue_confidence(residues, cutoff=70.0)
        assert len(warnings) == 1
        assert "2/3" in warnings[0]

    def test_check_residue_confidence_all_high(self) -> None:
        residues = [
            ResidueConfidence(residue_number=1, plddt_score=90.0),
            ResidueConfidence(residue_number=2, plddt_score=85.0),
        ]
        client = AlphaFoldClient()
        warnings = client.check_residue_confidence(residues, cutoff=70.0)
        assert warnings == []


# ── 4.18.6: Disordered region flagging ──────────────────────────────────────


class TestDisorder:
    def test_analyze_disorder_no_residues(self) -> None:
        client = AlphaFoldClient()
        report = client.analyze_disorder([])
        assert report.total_disordered_residues == 0
        assert report.fraction_disordered == 0.0

    def test_analyze_disorder_no_regions(self) -> None:
        client = AlphaFoldClient()
        residues = [
            ResidueConfidence(residue_number=1, plddt_score=80.0),
            ResidueConfidence(residue_number=2, plddt_score=75.0),
        ]
        report = client.analyze_disorder(residues)
        assert len(report.regions) == 0
        assert report.total_disordered_residues == 0

    def test_analyze_disorder_single_region(self) -> None:
        client = AlphaFoldClient()
        residues = [
            ResidueConfidence(residue_number=1, plddt_score=80.0),
            ResidueConfidence(residue_number=2, plddt_score=40.0),
            ResidueConfidence(residue_number=3, plddt_score=35.0),
            ResidueConfidence(residue_number=4, plddt_score=85.0),
        ]
        report = client.analyze_disorder(residues)
        assert len(report.regions) == 1
        region = report.regions[0]
        assert region.start == 2
        assert region.end == 3
        assert region.length == 2
        assert region.mean_plddt == 37.5
        assert report.total_disordered_residues == 2
        assert report.fraction_disordered == 0.5

    def test_analyze_disorder_multiple_regions(self) -> None:
        client = AlphaFoldClient()
        residues = [
            ResidueConfidence(residue_number=1, plddt_score=30.0),
            ResidueConfidence(residue_number=2, plddt_score=80.0),
            ResidueConfidence(residue_number=3, plddt_score=25.0),
            ResidueConfidence(residue_number=4, plddt_score=20.0),
            ResidueConfidence(residue_number=5, plddt_score=90.0),
        ]
        report = client.analyze_disorder(residues)
        assert len(report.regions) == 2
        assert report.regions[0].length == 1
        assert report.regions[1].length == 2
        assert report.total_disordered_residues == 3

    def test_analyze_disorder_trailing_region(self) -> None:
        client = AlphaFoldClient()
        residues = [
            ResidueConfidence(residue_number=1, plddt_score=80.0),
            ResidueConfidence(residue_number=2, plddt_score=30.0),
            ResidueConfidence(residue_number=3, plddt_score=25.0),
        ]
        report = client.analyze_disorder(residues)
        assert len(report.regions) == 1
        assert report.regions[0].end == 3


# ── 4.18.7: Bulk download ────────────────────────────────────────────────────


class TestBulkDownload:
    def test_get_proteome_download_url_known(self) -> None:
        url = AlphaFoldClient.get_proteome_download_url(
            taxon_id=9606,
            proteome_id="UP000005640",
            version="latest",
        )
        assert "UP000005640_9606_HUMAN" in url
        assert "latest" in url
        assert url.startswith("https://ftp.ebi.ac.uk")

    def test_get_proteome_download_url_unknown(self) -> None:
        url = AlphaFoldClient.get_proteome_download_url(
            taxon_id=99999,
            proteome_id="UP999999999",
        )
        assert "UP999999999_99999" in url

    def test_list_known_proteomes(self) -> None:
        proteomes = AlphaFoldClient.list_known_proteomes()
        assert "UP000005640_9606" in proteomes
        assert len(proteomes) >= 8


# ── Client lifecycle ────────────────────────────────────────────────────────


class TestClientLifecycle:
    @pytest.mark.asyncio
    @respx.mock
    async def test_close(self) -> None:
        client = AlphaFoldClient()
        await client.close()

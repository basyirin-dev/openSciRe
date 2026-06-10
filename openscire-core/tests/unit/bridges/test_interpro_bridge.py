# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest
import respx
from httpx import Response
from openscire.bridge.evidence_label import EvidenceTypeLabel
from openscire.bridges.interpro import (
    InterProClient,
    InterProMatch,
    InterProScanClient,
    InterProScanResult,
)
from openscire.exceptions import ReferenceError

API_URL = "https://www.ebi.ac.uk/interpro/api"
SCAN_URL = "https://www.ebi.ac.uk/Tools/services/rest/iprscan5"

# ── Mock data ──────────────────────────────────────────────────────────────

ENTRY_RESPONSE = {
    "metadata": {
        "accession": "IPR023411",
        "entry_id": None,
        "type": "active_site",
        "source_database": "interpro",
        "name": {
            "name": "Ribonuclease A, active site",
            "short": "RNaseA_AS",
        },
        "description": [
            {"text": "<p>Pancreatic ribonucleases are enzymes.</p>", "llm": False},
        ],
        "go_terms": [
            {
                "identifier": "GO:0004522",
                "name": "pancreatic ribonuclease activity",
                "category": {"code": "F", "name": "molecular_function"},
            },
        ],
        "member_databases": {
            "prosite": {
                "PS00127": "Pancreatic ribonuclease family signature",
            },
        },
        "literature": {
            "PUB00001546": {
                "PMID": 3940901,
                "title": "Comparison of turtle pancreatic ribonuclease",
                "authors": ["Beintema JJ", "van der Laan JM."],
                "year": 1986,
                "DOI_URL": "http://dx.doi.org/10.1016/0014-5793(86)80113-2",
            },
        },
        "counters": {
            "proteins": 2855,
            "structures": 515,
            "taxa": 1780,
            "matches": 2881,
        },
        "cross_references": {},
        "wikipedia": None,
        "integrated": None,
    },
}

ENTRY_LIST_RESPONSE = {
    "count": 2,
    "next": None,
    "previous": None,
    "results": [
        {
            "metadata": {
                "accession": "IPR000001",
                "name": "Kringle",
                "source_database": "interpro",
                "type": "domain",
                "integrated": None,
                "member_databases": {
                    "pfam": {"PF00051": "Kringle"},
                },
                "go_terms": None,
            },
        },
        {
            "metadata": {
                "accession": "IPR000003",
                "name": "Retinoid X receptor",
                "source_database": "interpro",
                "type": "family",
                "integrated": None,
                "member_databases": {
                    "prints": {"PR00545": "Retinoid X receptor"},
                },
                "go_terms": [
                    {
                        "identifier": "GO:0003677",
                        "name": "DNA binding",
                        "category": {"code": "F", "name": "molecular_function"},
                    },
                ],
            },
        },
    ],
}

PROTEIN_ENTRIES_RESPONSE = {
    "results": [
        {
            "metadata": {
                "accession": "IPR000001",
                "name": "Kringle",
                "source_database": "interpro",
                "type": "domain",
            },
        },
    ],
}

PROTEIN_MATCHES_RESPONSE = {
    "metadata": {
        "accession": "P04637",
        "entries": [
            {
                "metadata": {
                    "accession": "IPR012346",
                    "name": "p53/RUNT-type transcription factor",
                    "type": "domain",
                    "source_database": "interpro",
                },
                "locations": [
                    {
                        "fragments": [
                            {"start": 94, "end": 289},
                        ],
                    },
                ],
            },
        ],
    },
}

SCAN_RESULTS_JSON: list[dict] = [
    {
        "match": {
            "signature": {
                "accession": "PF00051",
                "name": "Kringle",
                "database": {"name": "Pfam", "version": "36.0"},
                "description": "Kringle domain",
                "e_value": 1.2e-15,
                "score": 65.4,
            },
            "entry": {
                "accession": "IPR000001",
                "type": "domain",
            },
            "locations": [
                {"start": 42, "end": 86},
                {"start": 120, "end": 168},
            ],
        },
    },
    {
        "match": {
            "signature": {
                "accession": "PS50070",
                "name": "Kringle domain profile",
                "database": {"name": "PROSITE", "version": "2024_01"},
                "description": "",
                "e_value": None,
                "score": None,
            },
            "entry": {
                "accession": "IPR000001",
                "type": "domain",
            },
            "locations": [
                {"start": 42, "end": 168},
            ],
        },
    },
]


@pytest.fixture
def client() -> InterProClient:
    return InterProClient()


@pytest.fixture
def scan_client() -> InterProScanClient:
    return InterProScanClient(poll_interval=0.1, poll_timeout=5.0)


# ── TestEntryAPI ────────────────────────────────────────────────────────────


class TestEntryAPI:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_entry(self, client: InterProClient) -> None:
        respx.get(f"{API_URL}/entry/interpro/IPR023411").mock(
            return_value=Response(200, json=ENTRY_RESPONSE),
        )
        entry = await client.get_entry("IPR023411")
        assert entry.accession == "IPR023411"
        assert entry.name == "Ribonuclease A, active site"
        assert entry.short_name == "RNaseA_AS"
        assert entry.type == "active_site"
        assert entry.source_database == "interpro"
        assert "Pancreatic ribonucleases are enzymes" in entry.description
        assert len(entry.go_terms) == 1
        assert entry.go_terms[0].identifier == "GO:0004522"
        assert len(entry.literature) == 1
        assert entry.literature[0].pmid == "3940901"
        assert entry.evidence_label == EvidenceTypeLabel.PREDICTED

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_entry_not_found(self, client: InterProClient) -> None:
        respx.get(f"{API_URL}/entry/interpro/IPR000000").mock(
            return_value=Response(404),
        )
        with pytest.raises(ReferenceError):
            await client.get_entry("IPR000000")

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_entry_network_error(self, client: InterProClient) -> None:
        respx.get(f"{API_URL}/entry/interpro/IPR023411").mock(
            side_effect=Exception("Connection refused"),
        )
        with pytest.raises(ReferenceError):
            await client.get_entry("IPR023411")

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_entries(self, client: InterProClient) -> None:
        respx.get(
            f"{API_URL}/entry/interpro",
            params={"page_size": "20"},
        ).mock(return_value=Response(200, json=ENTRY_LIST_RESPONSE))
        entries = await client.search_entries(page_size=20)
        assert len(entries) == 2
        assert entries[0].accession == "IPR000001"
        assert entries[0].name == "Kringle"
        assert entries[1].accession == "IPR000003"

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_entries_empty(self, client: InterProClient) -> None:
        respx.get(
            f"{API_URL}/entry/interpro",
            params={"page_size": "20"},
        ).mock(return_value=Response(200, json={"count": 0, "results": []}))
        entries = await client.search_entries(page_size=20)
        assert len(entries) == 0


# ── TestEntryBySource ─────────────────────────────────────────────────────


class TestEntryBySource:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_entry_by_source(self, client: InterProClient) -> None:
        respx.get(f"{API_URL}/entry/pfam/PF00051").mock(
            return_value=Response(
                200,
                json={
                    "metadata": {
                        "accession": "PF00051",
                        "name": {"name": "Kringle"},
                        "source_database": "pfam",
                        "type": "domain",
                    },
                },
            ),
        )
        entry = await client.get_entry_by_source("pfam", "PF00051")
        assert entry.accession == "PF00051"
        assert entry.name == "Kringle"
        assert entry.source_database == "pfam"


# ── TestProteinAPI ────────────────────────────────────────────────────────


class TestProteinAPI:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_protein_entries(self, client: InterProClient) -> None:
        respx.get(
            f"{API_URL}/entry/interpro/protein/uniprot/P04637",
        ).mock(return_value=Response(200, json=PROTEIN_ENTRIES_RESPONSE))
        entries = await client.get_protein_entries("P04637")
        assert len(entries) == 1
        assert entries[0].accession == "IPR000001"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_protein_entries_empty(self, client: InterProClient) -> None:
        respx.get(
            f"{API_URL}/entry/interpro/protein/uniprot/N0NEX1ST",
        ).mock(return_value=Response(200, json={"results": []}))
        entries = await client.get_protein_entries("N0NEX1ST")
        assert len(entries) == 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_protein_matches(self, client: InterProClient) -> None:
        respx.get(
            f"{API_URL}/protein/uniprot/P04637?residues",
        ).mock(return_value=Response(200, json=PROTEIN_MATCHES_RESPONSE))
        matches = await client.get_protein_matches("P04637")
        assert len(matches) == 1
        assert matches[0].accession == "IPR012346"
        assert len(matches[0].locations) == 1
        assert matches[0].locations[0].start == 94
        assert matches[0].locations[0].end == 289

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_protein_matches_no_matches(self, client: InterProClient) -> None:
        respx.get(
            f"{API_URL}/protein/uniprot/N0NEX1ST?residues",
        ).mock(return_value=Response(200, json={"metadata": {"accession": "N0NEX1ST"}}))
        matches = await client.get_protein_matches("N0NEX1ST")
        assert len(matches) == 0


# ── TestEValueFiltering ───────────────────────────────────────────────────


class TestEValueFiltering:
    def test_filter_matches_keeps_below(self) -> None:
        m1 = InterProMatch(accession="IPR001", e_value=1e-20)
        m2 = InterProMatch(accession="IPR002", e_value=0.5)
        filtered = InterProClient.filter_matches([m1, m2], threshold=0.01)
        assert len(filtered) == 1
        assert filtered[0].accession == "IPR001"

    def test_filter_matches_keeps_none(self) -> None:
        m1 = InterProMatch(accession="IPR001", e_value=None)
        filtered = InterProClient.filter_matches([m1], threshold=0.01)
        assert len(filtered) == 1

    def test_filter_matches_all_below(self) -> None:
        m1 = InterProMatch(accession="IPR001", e_value=1e-50)
        m2 = InterProMatch(accession="IPR002", e_value=1e-30)
        filtered = InterProClient.filter_matches([m1, m2], threshold=1.0)
        assert len(filtered) == 2

    def test_confidence_trace_high_evalue(self) -> None:
        m = InterProMatch(accession="IPR001", e_value=1.0)
        ct = m.to_confidence_trace()
        assert ct.value == pytest.approx(0.367879, abs=1e-5)

    def test_confidence_trace_low_evalue(self) -> None:
        m = InterProMatch(accession="IPR001", e_value=1e-100)
        ct = m.to_confidence_trace()
        assert ct.value == pytest.approx(1.0, abs=1e-10)

    def test_confidence_trace_zero_evalue(self) -> None:
        m = InterProMatch(accession="IPR001", e_value=0.0)
        ct = m.to_confidence_trace()
        assert ct.value == 1.0

    def test_confidence_trace_none_evalue(self) -> None:
        m = InterProMatch(accession="IPR001", e_value=None)
        ct = m.to_confidence_trace()
        assert ct.value == 0.5


# ── TestSignatureMetadata ─────────────────────────────────────────────────


class TestSignatureMetadata:
    def test_known_db(self) -> None:
        meta = InterProClient.get_signature_metadata("pfam")
        assert meta is not None
        assert meta.database == "Pfam"
        assert meta.method.value == "HMM"

    def test_profile_db(self) -> None:
        meta = InterProClient.get_signature_metadata("profile")
        assert meta is not None
        assert meta.method.value == "profile"

    def test_unknown_db(self) -> None:
        meta = InterProClient.get_signature_metadata("nonexistent")
        assert meta is None

    def test_list_databases(self) -> None:
        dbs = InterProClient.list_signature_databases()
        assert "pfam" in dbs
        assert "cdd" in dbs
        assert "profile" in dbs
        assert "prints" in dbs

    def test_get_match_method_hmm(self) -> None:
        m = InterProMatch(accession="IPR001", source_db="pfam")
        assert InterProClient.get_match_method(m) == "HMM"

    def test_get_match_method_fingerprint(self) -> None:
        m = InterProMatch(accession="IPR001", source_db="prints")
        assert InterProClient.get_match_method(m) == "fingerprint"

    def test_get_match_method_unknown(self) -> None:
        m = InterProMatch(accession="IPR001", source_db="unknown_db")
        assert InterProClient.get_match_method(m) == "unknown"


# ── TestScanAPI ──────────────────────────────────────────────────────────


class TestScanAPI:
    @pytest.mark.asyncio
    @respx.mock
    async def test_submit_sequence(self, scan_client: InterProScanClient) -> None:
        respx.post(f"{SCAN_URL}/run").mock(
            return_value=Response(200, text="iprscan-R20240101-000000-0000-00000000"),
        )
        job_id = await scan_client.submit_sequence("MLPGLALLLL", stype="p")
        assert job_id.startswith("iprscan-R")

    @pytest.mark.asyncio
    @respx.mock
    async def test_submit_empty_sequence(self, scan_client: InterProScanClient) -> None:
        with pytest.raises(ReferenceError):
            await scan_client.submit_sequence("   ", stype="p")

    @pytest.mark.asyncio
    @respx.mock
    async def test_poll_status_finished(self, scan_client: InterProScanClient) -> None:
        respx.get(f"{SCAN_URL}/status/JOB1").mock(
            return_value=Response(200, text="FINISHED"),
        )
        status = await scan_client.poll_status("JOB1")
        assert status == "FINISHED"

    @pytest.mark.asyncio
    @respx.mock
    async def test_poll_status_running(self, scan_client: InterProScanClient) -> None:
        respx.get(f"{SCAN_URL}/status/JOB1").mock(
            return_value=Response(200, text="RUNNING"),
        )
        status = await scan_client.poll_status("JOB1")
        assert status == "RUNNING"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_results(self, scan_client: InterProScanClient) -> None:
        respx.get(f"{SCAN_URL}/result/JOB1/json").mock(
            return_value=Response(200, json=SCAN_RESULTS_JSON),
        )
        matches = await scan_client.get_results("JOB1")
        assert len(matches) == 2
        assert matches[0].accession == "IPR000001"
        assert matches[0].signature_accession == "PF00051"
        assert matches[0].source_db == "pfam"
        assert matches[0].e_value == 1.2e-15
        assert matches[0].score == 65.4
        assert len(matches[0].locations) == 2
        assert matches[1].signature_accession == "PS50070"
        assert matches[1].source_db == "prosite"

    @pytest.mark.asyncio
    @respx.mock
    async def test_scan_sequence_full(self, scan_client: InterProScanClient) -> None:
        respx.post(f"{SCAN_URL}/run").mock(
            return_value=Response(200, text="iprscan-JOB1"),
        )
        respx.get(f"{SCAN_URL}/status/iprscan-JOB1").mock(
            return_value=Response(200, text="FINISHED"),
        )
        respx.get(f"{SCAN_URL}/result/iprscan-JOB1/json").mock(
            return_value=Response(200, json=SCAN_RESULTS_JSON),
        )
        result = await scan_client.scan_sequence("MLPGLALLLL")
        assert result.status == "FINISHED"
        assert len(result.matches) == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_scan_sequence_error(self, scan_client: InterProScanClient) -> None:
        respx.post(f"{SCAN_URL}/run").mock(
            return_value=Response(200, text="iprscan-JOB2"),
        )
        respx.get(f"{SCAN_URL}/status/iprscan-JOB2").mock(
            return_value=Response(200, text="ERROR"),
        )
        result = await scan_client.scan_sequence("MLPGLALLLL")
        assert result.status == "ERROR"
        assert len(result.matches) == 0


# ── TestParsing ──────────────────────────────────────────────────────────


class TestParsing:
    def test_go_term_parse(self) -> None:
        from openscire.bridges.interpro import GoTerm

        term = GoTerm(identifier="GO:0004522", name="activity", category="F")
        assert term.identifier == "GO:0004522"
        assert term.category == "F"

    def test_member_database_describe(self) -> None:
        from openscire.bridges.interpro import MemberDatabaseEntry

        mdb = MemberDatabaseEntry(
            database="pfam",
            accession="PF00051",
            name="Kringle",
        )
        assert mdb.database == "pfam"
        assert mdb.accession == "PF00051"

    def test_match_evidence_label_default(self) -> None:
        m = InterProMatch(accession="IPR001")
        assert m.evidence_label == EvidenceTypeLabel.PREDICTED

    def test_literature_ref(self) -> None:
        from openscire.bridges.interpro import LiteratureRef

        ref = LiteratureRef(pmid="3940901", title="Test", year=1986)
        assert ref.doi == ""


# ── TestEdgeCases ─────────────────────────────────────────────────────────


class TestEdgeCases:
    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self, client: InterProClient) -> None:
        respx.get(f"{API_URL}/entry/interpro/IPR000000").mock(
            return_value=Response(200, json={}),
        )
        entry = await client.get_entry("IPR000000")
        assert entry.accession == ""

    @pytest.mark.asyncio
    @respx.mock
    async def test_partial_metadata(self, client: InterProClient) -> None:
        respx.get(f"{API_URL}/entry/interpro/IPR000X").mock(
            return_value=Response(
                200,
                json={
                    "metadata": {"accession": "IPR000X", "type": "family"},
                },
            ),
        )
        entry = await client.get_entry("IPR000X")
        assert entry.accession == "IPR000X"
        assert entry.type == "family"
        assert entry.name == ""
        assert len(entry.go_terms) == 0

    def test_evalue_threshold_constructor(self) -> None:
        c = InterProClient(e_value_threshold=0.001)
        assert c.e_value_threshold == 0.001

    def test_scan_result_model(self) -> None:
        result = InterProScanResult(job_id="JOB1", status="FINISHED")
        assert result.job_id == "JOB1"
        assert len(result.matches) == 0


# ── TestClientLifecycle ──────────────────────────────────────────────────


class TestClientLifecycle:
    @pytest.mark.asyncio
    @respx.mock
    async def test_interpro_close(self, client: InterProClient) -> None:
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_scan_close(self, scan_client: InterProScanClient) -> None:
        await scan_client.close()

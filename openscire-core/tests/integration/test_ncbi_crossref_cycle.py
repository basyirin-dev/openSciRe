# SPDX-License-Identifier: Apache-2.0

"""Integration test: PubMed -> NCBI elink -> cross-ref -> evidence labels.

Tests identifier resolution and cross-referencing via NCBI E-Utilities,
then tags resolved records with evidence type labels.
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response
from openscire.bridge.evidence_label import EvidencePropagator, EvidenceTypeLabel
from openscire.bridge.resolver import CrossReferenceResolver
from openscire.bridges.entrez import EntrezClient

pytestmark = [
    pytest.mark.integration,
]

ESEARCH_JSON = {
    "esearchresult": {
        "count": "1",
        "retstart": "0",
        "idlist": ["12345678"],
        "webenv": "",
        "querykey": "",
    },
}

ESUMMARY_JSON = {
    "header": {"type": "esummary", "version": "0.3"},
    "result": {
        "uids": [12345678],
        "12345678": {
            "uid": "12345678",
            "title": "A Test PubMed Article",
            "pubdate": "2025 Jan 1",
            "source": "Journal of Test Studies",
            "authors": [{"name": "Alice A", "authtype": "author"}],
            "elocationid": "doi: 10.1234/pmid.2025.001",
            "pmcid": "PMC9876543",
            "pubtype": "Journal Article",
        },
    },
}

ELINK_JSON = {
    "linksets": [
        {
            "dbfrom": "pubmed",
            "ids": ["12345678"],
            "linksetdbs": [
                {"dbto": "pmc", "linkname": "pubmed_pmc", "links": ["PMC9876543"]},
                {"dbto": "gene", "linkname": "pubmed_gene", "links": ["7157"]},
            ],
        },
    ],
}

IDCONV_RESPONSE = {
    "status": "ok",
    "records": [
        {
            "doi": "10.1234/pmid.2025.001",
            "pmid": "12345678",
            "pmcid": "PMC9876543",
            "current": True,
        },
    ],
}


class TestNcbiCrossrefCycle:
    """PubMed -> NCBI elink -> cross-ref -> evidence labels."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_pubmed_to_crossref_cycle(self) -> None:
        entrez = EntrezClient(email="test@example.com")
        resolver = CrossReferenceResolver()

        respx.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        ).mock(return_value=Response(200, json=ESEARCH_JSON))

        respx.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
        ).mock(return_value=Response(200, json=ESUMMARY_JSON))

        respx.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi",
        ).mock(return_value=Response(200, json=ELINK_JSON))

        respx.get(
            "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/",
        ).mock(return_value=Response(200, json=IDCONV_RESPONSE))

        result = await entrez.esearch("pubmed", "test query", retmax=10)
        assert len(result.ids) >= 1
        pmid = result.ids[0]
        assert pmid == "12345678"

        summaries = await entrez.esummary("pubmed", [pmid])
        assert len(summaries) >= 1
        first = summaries[0]
        assert first.data.get("title") == "A Test PubMed Article"
        assert first.data.get("elocationid") == "doi: 10.1234/pmid.2025.001"

        linksets = await entrez.elink(dbfrom="pubmed", ids=[pmid])
        assert len(linksets) >= 1
        found_pmc = False
        found_gene = False
        for ls in linksets:
            for link in ls.links:
                if link.db_to == "pmc":
                    found_pmc = True
                    assert "PMC9876543" in link.ids
                if link.db_to == "gene":
                    found_gene = True
                    assert "7157" in link.ids
        assert found_pmc
        assert found_gene

        pmcid = await resolver.pmid_to_pmcid(pmid)
        assert pmcid == "PMC9876543"

        doi_pmid = await resolver.doi_to_pmid("10.1234/pmid.2025.001")
        assert doi_pmid == "12345678"

    async def test_evidence_labeling_from_ncbi(self) -> None:
        combined = EvidencePropagator.combine([
            EvidenceTypeLabel.EXPERIMENTAL,
            EvidenceTypeLabel.REVIEWED,
            EvidenceTypeLabel.REVIEWED,
        ])
        assert combined == EvidenceTypeLabel.REVIEWED

        predicted_only = EvidencePropagator.combine([
            EvidenceTypeLabel.PREDICTED,
            EvidenceTypeLabel.PREDICTED,
        ])
        assert predicted_only == EvidenceTypeLabel.PREDICTED

    @pytest.mark.asyncio
    @respx.mock
    async def test_idconv_resolution_chain(self) -> None:
        resolver = CrossReferenceResolver()

        respx.get(
            "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/",
        ).mock(return_value=Response(200, json=IDCONV_RESPONSE))

        pmid = await resolver.doi_to_pmid("10.1234/pmid.2025.001")
        assert pmid == "12345678"

        pmcid = await resolver.doi_to_pmcid("10.1234/pmid.2025.001")
        assert pmcid == "PMC9876543"

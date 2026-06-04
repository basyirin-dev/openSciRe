# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest
import respx
from httpx import Response
from openscire.bridges.entrez import (
    AssemblyRecord,
    EntrezClient,
    EntrezSearchResult,
    NucleotideRecord,
    TaxonomyRecord,
)
from openscire.exceptions import ReferenceError

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def client() -> EntrezClient:
    return EntrezClient(email="test@example.com")


@pytest.fixture
def client_with_key() -> EntrezClient:
    return EntrezClient(email="test@example.com", api_key="test-key-123")


# ── Helpers ────────────────────────────────────────────────────────────────


def _search_json(ids: list[str], count: int = 0, webenv: str = "", querykey: str = "") -> Response:
    return Response(
        200,
        json={
            "esearchresult": {
                "count": str(count or len(ids)),
                "retstart": "0",
                "idlist": ids,
                "webenv": webenv,
                "querykey": querykey,
            }
        },
    )


def _summary_json(ids: list[str], entries: list[dict]) -> Response:
    uids = [int(i) for i in ids]
    result: dict = {"uids": uids}
    for uid, entry in zip(uids, entries, strict=False):
        result[str(uid)] = entry
    return Response(200, json={"result": result, "header": {"type": "esummary", "version": "0.3"}})


def _links_json() -> Response:
    return Response(
        200,
        json={
            "linksets": [
                {
                    "dbfrom": "pubmed",
                    "ids": ["12345"],
                    "linksetdbs": [
                        {
                            "dbto": "pmc",
                            "linkname": "pubmed_pmc",
                            "links": ["654321"],
                        }
                    ],
                }
            ]
        },
    )


GENBANK_XML = """<?xml version="1.0"?>
<GBSet>
  <GBSeq>
    <GBSeq_locus>NM_000001</GBSeq_locus>
    <GBSeq_length>5000</GBSeq_length>
    <GBSeq_strandedness>single</GBSeq_strandedness>
    <GBSeq_moltype>mRNA</GBSeq_moltype>
    <GBSeq_topology>linear</GBSeq_topology>
    <GBSeq_definition>Homo sapiens hypothetical gene</GBSeq_definition>
    <GBSeq_primary-accession>NM_000001</GBSeq_primary-accession>
    <GBSeq_accession-version>NM_000001.1</GBSeq_accession-version>
    <GBSeq_organism>Homo sapiens</GBSeq_organism>
    <GBSeq_taxonomy>Eukaryota; Metazoa; Chordata</GBSeq_taxonomy>
    <GBSeq_comment>Test record</GBSeq_comment>
    <GBSeq_feature-table>
      <GBFeature>
        <GBFeature_key>gene</GBFeature_key>
        <GBFeature_location>1..5000</GBFeature_location>
        <GBFeature_quals>
          <GBQualifier>
            <GBQualifier_name>gene</GBQualifier_name>
            <GBQualifier_value>BRCA1</GBQualifier_value>
          </GBQualifier>
        </GBFeature_quals>
      </GBFeature>
    </GBSeq_feature-table>
    <GBSeq_sequence>atgcgatcgatcgtagctagctagctagctagctagcgtagc</GBSeq_sequence>
  </GBSeq>
</GBSet>"""

FASTA_TEXT = (
    ">NM_000001.1 Homo sapiens hypothetical gene\n"
    "ATGCGATCGATCGTAGCTAGCTAGCTAGCTAGCTAGCGTAGC\n"
)

ASSEMBLY_XML = """<?xml version="1.0"?>
<AssemblySet>
  <Assembly>
    <Assembly_accession>GCF_000001405.40</Assembly_accession>
    <Assembly_name>GRCh38.p14</Assembly_name>
    <Organism>
      <Organism_scientific>Homo sapiens</Organism_scientific>
      <Organism_taxid>9606</Organism_taxid>
    </Organism>
    <Assembly_level>Chromosome</Assembly_level>
    <Assembly_type>haploid-with-alt-loci</Assembly_type>
    <Genome_representation>full</Genome_representation>
    <Date>2022-03-16</Date>
    <Submitter>
      <Submitter_full>Genome Reference Consortium</Submitter_full>
    </Submitter>
    <Stat>
      <Stat_category>total_length</Stat_category>
      <Stat_value>3100000000</Stat_value>
    </Stat>
  </Assembly>
</AssemblySet>"""

_LINEAGE = (
    "Eukaryota; Metazoa; Chordata; Craniata; Vertebrata; Euteleostomi; "
    "Mammalia; Eutheria; Euarchontoglires; Primates; Haplorrhini; "
    "Catarrhini; Hominidae; Homo"
)

TAXONOMY_XML = f"""<?xml version="1.0"?>
<TaxonSet>
  <Taxon>
    <TaxId>9606</TaxId>
    <ScientificName>Homo sapiens</ScientificName>
    <CommonName>human</CommonName>
    <GenbankCommonName>human</GenbankCommonName>
    <Lineage>{_LINEAGE}</Lineage>
    <GeneticCode>
      <GCId>1</GCId>
    </GeneticCode>
    <MitoGeneticCode>
      <MGCId>2</MGCId>
    </MitoGeneticCode>
    <Rank>species</Rank>
    <Division>Primates</Division>
  </Taxon>
</TaxonSet>"""


# ── 4.17.1: Core E-utilities ──────────────────────────────────────────────


class TestCoreEUtilities:
    @pytest.mark.asyncio
    @respx.mock
    async def test_esearch_basic(self, client: EntrezClient) -> None:
        route = respx.get(f"{BASE_URL}/esearch.fcgi").mock(
            return_value=_search_json(["12345", "67890"], count=2),
        )

        result = await client.esearch("pubmed", "cancer", retmax=2)
        assert isinstance(result, EntrezSearchResult)
        assert result.ids == ["12345", "67890"]
        assert result.total_count == 2
        assert result.db == "pubmed"
        assert result.webenv == ""

        query = route.calls[0].request.url.query.decode()
        assert "db=pubmed" in query
        assert "term=cancer" in query
        assert "retmax=2" in query

    @pytest.mark.asyncio
    @respx.mock
    async def test_esearch_with_history(self, client: EntrezClient) -> None:
        route = respx.get(f"{BASE_URL}/esearch.fcgi").mock(
            return_value=_search_json(["12345"], count=1, webenv="WEB_1", querykey="1"),
        )

        result = await client.esearch("pubmed", "cancer", usehistory=True)
        assert result.webenv == "WEB_1"
        assert result.query_key == "1"

        query = route.calls[0].request.url.query.decode()
        assert "usehistory=y" in query

    @pytest.mark.asyncio
    @respx.mock
    async def test_esummary(self, client: EntrezClient) -> None:
        respx.get(f"{BASE_URL}/esummary.fcgi").mock(
            return_value=_summary_json(
                ["12345", "67890"],
                [
                    {"uid": "12345", "title": "Paper A", "source": "Journal A",
                     "pubdate": "2024 Jan"},
                    {"uid": "67890", "title": "Paper B", "source": "Journal B",
                     "pubdate": "2023 Jun"},
                ],
            ),
        )

        results = await client.esummary("pubmed", ["12345", "67890"])
        assert len(results) == 2
        assert results[0].id == "12345"
        assert results[0].data["title"] == "Paper A"
        assert results[1].id == "67890"
        assert results[1].data["title"] == "Paper B"

    @pytest.mark.asyncio
    @respx.mock
    async def test_efetch_xml(self, client: EntrezClient) -> None:
        route = respx.get(f"{BASE_URL}/efetch.fcgi").mock(
            return_value=Response(200, text=GENBANK_XML),
        )

        xml_str = await client.efetch("nucleotide", ["NM_000001"])
        assert "<GBSeq>" in xml_str
        assert "NM_000001" in xml_str

        query = route.calls[0].request.url.query.decode()
        assert "retmode=xml" in query
        assert "rettype=xml" in query

    @pytest.mark.asyncio
    @respx.mock
    async def test_efetch_text(self, client: EntrezClient) -> None:
        respx.get(f"{BASE_URL}/efetch.fcgi").mock(
            return_value=Response(200, text=FASTA_TEXT),
        )

        text = await client.efetch("nucleotide", ["NM_000001"], rettype="fasta", retmode="text")
        assert ">NM_000001" in text

    @pytest.mark.asyncio
    @respx.mock
    async def test_elink(self, client: EntrezClient) -> None:
        respx.get(f"{BASE_URL}/elink.fcgi").mock(
            return_value=_links_json(),
        )

        link_sets = await client.elink("pubmed", db="pmc", ids=["12345"])
        assert len(link_sets) == 1
        link_set = link_sets[0]
        assert link_set.db_from == "pubmed"
        assert link_set.id == "12345"
        assert len(link_set.links) == 1
        assert link_set.links[0].db_to == "pmc"
        assert link_set.links[0].ids == ["654321"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_elink_no_ids(self, client: EntrezClient) -> None:
        result = await client.elink("pubmed", ids=None)
        assert result == []


# ── 4.17.2: Nucleotide ────────────────────────────────────────────────────


class TestNucleotide:
    @pytest.mark.asyncio
    @respx.mock
    async def test_search(self, client: EntrezClient) -> None:
        route = respx.get(f"{BASE_URL}/esearch.fcgi").mock(
            return_value=_search_json(["NM_000001", "NM_000002"], count=2),
        )

        result = await client.search_nucleotide("BRCA1", retmax=2)
        assert len(result.ids) == 2
        assert "db=nucleotide" in route.calls[0].request.url.query.decode()

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch(self, client: EntrezClient) -> None:
        respx.get(f"{BASE_URL}/efetch.fcgi").mock(
            return_value=Response(200, text=GENBANK_XML),
        )

        record = await client.fetch_nucleotide("NM_000001")
        assert isinstance(record, NucleotideRecord)
        assert record.accession == "NM_000001"
        assert record.accession_version == "NM_000001.1"
        assert record.length == 5000
        assert record.definition == "Homo sapiens hypothetical gene"
        assert record.molecule_type == "mRNA"
        assert record.topology == "linear"
        assert record.strandedness == "single"
        assert record.organism == "Homo sapiens"
        assert record.gene_name == "BRCA1"
        assert record.sequence == "atgcgatcgatcgtagctagctagctagctagctagcgtagc"
        assert record.extra["taxonomy"] == "Eukaryota; Metazoa; Chordata"
        assert record.extra["comment"] == "Test record"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_sequence(self, client: EntrezClient) -> None:
        route = respx.get(f"{BASE_URL}/efetch.fcgi").mock(
            return_value=Response(200, text=FASTA_TEXT),
        )

        fasta = await client.fetch_nucleotide_sequence("NM_000001")
        assert fasta == FASTA_TEXT
        query = route.calls[0].request.url.query.decode()
        assert "rettype=fasta" in query
        assert "retmode=text" in query

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_missing_gbseq(self, client: EntrezClient) -> None:
        respx.get(f"{BASE_URL}/efetch.fcgi").mock(
            return_value=Response(200, text="<?xml version=\"1.0\"?><GBSet/>"),
        )

        with pytest.raises(ReferenceError, match="No GBSeq element"):
            await client.fetch_nucleotide("INVALID")


# ── 4.17.3: Genome assembly ────────────────────────────────────────────────


class TestAssembly:
    @pytest.mark.asyncio
    @respx.mock
    async def test_search(self, client: EntrezClient) -> None:
        route = respx.get(f"{BASE_URL}/esearch.fcgi").mock(
            return_value=_search_json(["GCF_000001405.40"], count=1),
        )

        result = await client.search_assembly("GRCh38", retmax=1)
        assert len(result.ids) == 1
        assert "db=assembly" in route.calls[0].request.url.query.decode()

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch(self, client: EntrezClient) -> None:
        respx.get(f"{BASE_URL}/efetch.fcgi").mock(
            return_value=Response(200, text=ASSEMBLY_XML),
        )

        record = await client.fetch_assembly("GCF_000001405.40")
        assert isinstance(record, AssemblyRecord)
        assert record.assembly_accession == "GCF_000001405.40"
        assert record.assembly_name == "GRCh38.p14"
        assert record.organism == "Homo sapiens"
        assert record.taxon_id == 9606
        assert record.assembly_level == "Chromosome"
        assert record.assembly_type == "haploid-with-alt-loci"
        assert record.genome_representation == "full"
        assert record.release_date == "2022-03-16"
        assert record.submitter == "Genome Reference Consortium"
        assert record.total_sequence_length == 3100000000

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_not_found(self, client: EntrezClient) -> None:
        respx.get(f"{BASE_URL}/efetch.fcgi").mock(
            return_value=Response(200, text="<?xml version=\"1.0\"?><AssemblySet/>"),
        )

        with pytest.raises(ReferenceError, match="No assembly found"):
            await client.fetch_assembly("INVALID_ACCESSION")


# ── 4.17.4: Taxonomy ────────────────────────────────────────────────────────


class TestTaxonomy:
    @pytest.mark.asyncio
    @respx.mock
    async def test_search(self, client: EntrezClient) -> None:
        route = respx.get(f"{BASE_URL}/esearch.fcgi").mock(
            return_value=_search_json(["9606", "9598"], count=2),
        )

        result = await client.search_taxonomy("Homo sapiens", retmax=2)
        assert len(result.ids) == 2
        assert "db=taxonomy" in route.calls[0].request.url.query.decode()

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch(self, client: EntrezClient) -> None:
        respx.get(f"{BASE_URL}/efetch.fcgi").mock(
            return_value=Response(200, text=TAXONOMY_XML),
        )

        record = await client.fetch_taxonomy(9606)
        assert isinstance(record, TaxonomyRecord)
        assert record.taxon_id == 9606
        assert record.scientific_name == "Homo sapiens"
        assert record.common_name == "human"
        assert record.genbank_common_name == "human"
        assert "Primates" in record.lineage
        assert record.genetic_code == 1
        assert record.mito_genetic_code == 2
        assert record.rank == "species"
        assert record.division == "Primates"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_by_name(self, client: EntrezClient) -> None:
        respx.get(f"{BASE_URL}/esearch.fcgi").mock(
            return_value=_search_json(["9606"], count=1),
        )
        respx.get(f"{BASE_URL}/efetch.fcgi").mock(
            return_value=Response(200, text=TAXONOMY_XML),
        )

        record = await client.fetch_taxonomy_by_name("Homo sapiens")
        assert record is not None
        assert record.taxon_id == 9606
        assert record.scientific_name == "Homo sapiens"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_by_name_not_found(self, client: EntrezClient) -> None:
        respx.get(f"{BASE_URL}/esearch.fcgi").mock(
            return_value=_search_json([]),
        )

        record = await client.fetch_taxonomy_by_name("Unknownus species")
        assert record is None


# ── 4.17.5: Literature cross-reference ──────────────────────────────────────


class TestLiteratureCrossReference:
    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_linked_records(self, client: EntrezClient) -> None:
        respx.get(f"{BASE_URL}/elink.fcgi").mock(
            return_value=_links_json(),
        )

        link_set = await client.fetch_linked_records("12345", db_to="pmc")
        assert link_set.db_from == "pubmed"
        assert link_set.id == "12345"
        assert len(link_set.links) == 1
        assert link_set.links[0].db_to == "pmc"
        assert link_set.links[0].ids == ["654321"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_linked_records_no_db(self, client: EntrezClient) -> None:
        respx.get(f"{BASE_URL}/elink.fcgi").mock(
            return_value=_links_json(),
        )

        link_set = await client.fetch_linked_records("12345")
        assert link_set.db_from == "pubmed"
        assert link_set.id == "12345"


# ── Rate limiting ─────────────────────────────────────────────────────────


class TestRateLimiting:
    @pytest.mark.asyncio
    @respx.mock
    async def test_api_key(self, client_with_key: EntrezClient) -> None:
        respx.get(f"{BASE_URL}/esearch.fcgi").mock(
            return_value=_search_json(["12345"]),
        )

        result = await client_with_key.esearch("pubmed", "cancer")
        assert len(result.ids) == 1


# ── Error handling ────────────────────────────────────────────────────────


class TestErrorHandling:
    @pytest.mark.asyncio
    @respx.mock
    async def test_http_error(self, client: EntrezClient) -> None:
        respx.get(f"{BASE_URL}/esearch.fcgi").mock(
            return_value=Response(500),
        )

        with pytest.raises(ReferenceError, match="Entrez API error: 500"):
            await client.esearch("pubmed", "cancer")

    @pytest.mark.asyncio
    @respx.mock
    async def test_network_error(self, client: EntrezClient) -> None:
        import httpx
        respx.get(f"{BASE_URL}/esearch.fcgi").mock(
            side_effect=httpx.ConnectError("connection failed"),
        )

        with pytest.raises(ReferenceError, match="Entrez request failed"):
            await client.esearch("pubmed", "cancer")


# ── Default params ──────────────────────────────────────────────────────────


class TestDefaultParams:
    @pytest.mark.asyncio
    @respx.mock
    async def test_default_params(self) -> None:
        client = EntrezClient(email="test@example.com")
        route = respx.get(f"{BASE_URL}/esearch.fcgi").mock(
            return_value=_search_json(["12345"]),
        )

        await client.esearch("pubmed", "cancer")
        query = route.calls[0].request.url.query.decode()
        assert "tool=openscire" in query
        assert "email=test%40example.com" in query
        assert "api_key" not in query
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_default_params_with_key(self) -> None:
        client = EntrezClient(email="test@example.com", api_key="test-key-123")
        route = respx.get(f"{BASE_URL}/esearch.fcgi").mock(
            return_value=_search_json(["12345"]),
        )

        await client.esearch("pubmed", "cancer")
        query = route.calls[0].request.url.query.decode()
        assert "api_key=test-key-123" in query
        await client.close()

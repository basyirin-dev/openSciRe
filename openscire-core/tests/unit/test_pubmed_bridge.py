# SPDX-License-Identifier: Apache-2.0

import pytest
import respx
from httpx import Response
from openscire.references.bridges.pubmed import PubMedBridge

ESEARCH_XML = b"""<?xml version="1.0"?>
<eSearchResult>
  <Count>1</Count>
  <RetMax>1</RetMax>
  <RetStart>0</RetStart>
  <IdList>
    <Id>12345678</Id>
  </IdList>
  <WebEnv>NCID_test_webenv</WebEnv>
  <QueryKey>1</QueryKey>
</eSearchResult>"""

ESUMMARY_JSON = b"""{
  "header": {"type": "esummary", "version": "0.3"},
  "result": {
    "uids": ["12345678"],
    "12345678": {
      "uid": "12345678",
      "title": "Test Article Title",
      "source": "J Test Sci",
      "pubdate": "2024 Jan",
      "volume": "10",
      "issue": "2",
      "pages": "100-10",
      "authors": [{"name": "Smith J", "authtype": "author"}, {"name": "Doe J", "authtype": "author"}],
      "doi": "10.1234/test.2024.001",
      "attributes": ["Has Abstract"],
      "pmcrefcount": 0,
      "elocationid": "doi: 10.1234/test.2024.001"
    }
  }
}"""

EFETCH_XML = b"""<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345678</PMID>
      <Article>
        <Journal>
          <Title>J Test Sci</Title>
          <ISSN>1234-5678</ISSN>
          <JournalIssue>
            <Volume>10</Volume>
            <Issue>2</Issue>
            <PubDate><Year>2024</Year><Month>01</Month></PubDate>
          </JournalIssue>
        </Journal>
        <ArticleTitle>Test Article Title</ArticleTitle>
        <Abstract><AbstractText>This is a test abstract.</AbstractText></Abstract>
        <AuthorList>
          <Author><LastName>Smith</LastName><ForeName>John</ForeName></Author>
          <Author><LastName>Doe</LastName><ForeName>Jane</ForeName></Author>
        </AuthorList>
      </Article>
      <MeshHeadingList>
        <MeshHeading>
          <DescriptorName UI="D000001" MajorTopicYN="N">Machine Learning</DescriptorName>
        </MeshHeading>
      </MeshHeadingList>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="doi">10.1234/test.2024.001</ArticleId>
        <ArticleId IdType="pmc">PMC987654</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>"""


@pytest.fixture
def bridge() -> PubMedBridge:
    return PubMedBridge(email="test@example.com", tool="test_tool")


class TestPubMedBridge:
    def test_constructor_defaults(self) -> None:
        b = PubMedBridge()
        assert b._email == ""
        assert b._tool == "openscire"

    def test_constructor_custom(self) -> None:
        b = PubMedBridge(email="x@y.com", tool="mytool", api_key="key123")
        assert b._email == "x@y.com"
        assert b._tool == "mytool"
        assert b._api_key == "key123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_search(self, bridge: PubMedBridge) -> None:
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
            return_value=Response(200, content=ESEARCH_XML)
        )
        result = await bridge.search("machine learning")
        assert result.pmids == ["12345678"]
        assert result.total_count == 1
        assert result.webenv == "NCID_test_webenv"
        assert result.query_key == "1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_empty(self, bridge: PubMedBridge) -> None:
        empty = ESEARCH_XML.replace(b"<Count>1</Count>", b"<Count>0</Count>").replace(
            b"<Id>12345678</Id>", b""
        )
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
            return_value=Response(200, content=empty)
        )
        result = await bridge.search("nonexistent")
        assert result.pmids == []
        assert result.total_count == 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_summary(self, bridge: PubMedBridge) -> None:
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi").mock(
            return_value=Response(200, content=ESUMMARY_JSON)
        )
        items = await bridge.fetch_summary("12345678")
        assert len(items) == 1
        assert items[0].doi == "10.1234/test.2024.001"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_detail(self, bridge: PubMedBridge) -> None:
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi").mock(
            return_value=Response(200, content=EFETCH_XML)
        )
        items = await bridge.fetch_detail("12345678")
        assert len(items) == 1
        item = items[0]
        assert item.id == "12345678"
        assert item.doi == "10.1234/test.2024.001"
        assert item.journal == "J Test Sci"
        assert item.volume == "10"
        assert item.issue == "2"
        assert item.year == 2024

    @pytest.mark.asyncio
    @respx.mock
    async def test_resolve_pmid_to_doi(self, bridge: PubMedBridge) -> None:
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi").mock(
            return_value=Response(200, content=EFETCH_XML)
        )
        doi = await bridge.resolve_pmid_to_doi("12345678")
        assert doi == "10.1234/test.2024.001"

    @pytest.mark.asyncio
    @respx.mock
    async def test_resolve_doi_to_pmid(self, bridge: PubMedBridge) -> None:
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
            return_value=Response(200, content=ESEARCH_XML)
        )
        pmid = await bridge.resolve_doi_to_pmid("10.1234/test.2024.001")
        assert pmid == "12345678"

    @pytest.mark.asyncio
    async def test_close(self, bridge: PubMedBridge) -> None:
        await bridge.close()

    @pytest.mark.asyncio
    async def test_ncbi_rate_limiter(self) -> None:
        import asyncio

        from openscire.references.bridges.pubmed import NCBIRateLimiter

        # With API key: 10 req/s = 0.1s delay
        limiter = NCBIRateLimiter(api_key="test")
        assert limiter._delay == 0.1
        await limiter.wait()
        t1 = asyncio.get_event_loop().time()
        await limiter.wait()
        t2 = asyncio.get_event_loop().time()
        assert t2 - t1 >= 0.09

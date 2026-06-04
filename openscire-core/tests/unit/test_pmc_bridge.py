# SPDX-License-Identifier: Apache-2.0

import respx
import pytest
from httpx import Response

from openscire.references.bridges.pmc import PMCBridge

PMC_ESEARCH_XML = b"""<?xml version="1.0"?>
<eSearchResult>
  <Count>1</Count>
  <RetMax>1</RetMax>
  <RetStart>0</RetStart>
  <IdList>
    <Id>987654</Id>
  </IdList>
</eSearchResult>"""

ID_CONVERTER_JSON = b"""{
  "records": [
    {"pmcid": "PMC987654", "pmid": "12345678"}
  ]
}"""

SAMPLE_NXML = """<?xml version="1.0"?>
<article>
  <front>
    <journal-meta>
      <journal-id journal-id-type="nlm-ta">J Test Sci</journal-id>
      <journal-title-group>
        <journal-title>Journal of Test Science</journal-title>
      </journal-title-group>
    </journal-meta>
    <article-meta>
      <article-id pub-id-type="pmid">12345678</article-id>
      <article-id pub-id-type="pmc">PMC987654</article-id>
      <article-id pub-id-type="doi">10.1234/test.2024.001</article-id>
      <title-group>
        <article-title>Test Full Text Article</article-title>
      </title-group>
      <contrib-group>
        <contrib contrib-type="author">
          <name>
            <surname>Smith</surname>
            <given-names>John</given-names>
          </name>
        </contrib>
      </contrib-group>
      <pub-date>
        <year>2024</year>
      </pub-date>
      <volume>10</volume>
      <issue>2</issue>
      <fpage>100</fpage>
      <lpage>110</lpage>
      <abstract>
        <p>This is the abstract.</p>
      </abstract>
    </article-meta>
  </front>
  <body>
    <sec>
      <title>Introduction</title>
      <p>Introduction text here.</p>
    </sec>
    <sec>
      <title>Methods</title>
      <p>Methods text here.</p>
    </sec>
  </body>
  <back>
    <ref-list>
      <ref>
        <mixed-citation>1. Author A, Title, 2023</mixed-citation>
      </ref>
    </ref-list>
  </back>
</article>"""


@pytest.fixture
def bridge() -> PMCBridge:
    return PMCBridge(email="test@example.com", tool="test_tool")


class TestPMCBridge:
    def test_constructor(self) -> None:
        b = PMCBridge(email="x@y.com", tool="mytool")
        assert b._email == "x@y.com"
        assert b._tool == "mytool"

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_pmc(self, bridge: PMCBridge) -> None:
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
            return_value=Response(200, content=PMC_ESEARCH_XML)
        )
        pmcids = await bridge.search_pmc("machine learning")
        assert pmcids == ["PMC987654"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_pmc_empty(self, bridge: PMCBridge) -> None:
        empty = PMC_ESEARCH_XML.replace(b"<Count>1</Count>", b"<Count>0</Count>").replace(
            b"<Id>987654</Id>", b""
        )
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
            return_value=Response(200, content=empty)
        )
        pmcids = await bridge.search_pmc("nonexistent")
        assert pmcids == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_convert_pmid_to_pmcid(self, bridge: PMCBridge) -> None:
        respx.get("https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0").mock(
            return_value=Response(200, content=ID_CONVERTER_JSON)
        )
        pmcid = await bridge.convert_pmid_to_pmcid("12345678")
        assert pmcid == "PMC987654"

    @pytest.mark.asyncio
    @respx.mock
    async def test_convert_pmid_to_pmcid_not_found(self, bridge: PMCBridge) -> None:
        respx.get("https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0").mock(
            return_value=Response(200, content=b'{"records": []}')
        )
        pmcid = await bridge.convert_pmid_to_pmcid("99999999")
        assert pmcid is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_full_text_by_pmid_not_in_pmc(self, bridge: PMCBridge) -> None:
        respx.get("https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0").mock(
            return_value=Response(200, content=b'{"records": []}')
        )
        article = await bridge.fetch_full_text_by_pmid("99999999")
        assert article is None

    def test_parse_article_xml(self) -> None:
        article = PMCBridge._parse_article_xml(SAMPLE_NXML)
        assert article.pmid == "12345678"
        assert article.pmcid == "PMC987654"
        assert article.doi == "10.1234/test.2024.001"
        assert article.title == "Test Full Text Article"
        assert article.journal == "Journal of Test Science"
        assert article.year == 2024
        assert article.volume == "10"
        assert article.issue == "2"
        assert article.pages == "100-110"
        assert "abstract" in article.abstract.lower()
        assert len(article.authors) == 1
        assert article.authors[0].last == "Smith"
        assert article.authors[0].first == "John"

    def test_parse_sections(self) -> None:
        article = PMCBridge._parse_article_xml(SAMPLE_NXML)
        assert len(article.sections) >= 2
        headings = [s.heading for s in article.sections]
        assert "Introduction" in headings
        assert "Methods" in headings

    def test_parse_references(self) -> None:
        article = PMCBridge._parse_article_xml(SAMPLE_NXML)
        assert len(article.references) >= 1
        assert "Author A" in article.references[0]

    def test_parse_empty_xml(self) -> None:
        article = PMCBridge._parse_article_xml(b"<article></article>")
        assert article.pmid == ""

    def test_close(self) -> None:
        import asyncio

        b = PMCBridge()
        asyncio.run(b.close())

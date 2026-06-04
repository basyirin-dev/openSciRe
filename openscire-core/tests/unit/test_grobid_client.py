import pytest
import respx
from httpx import Response
from openscire.references.parsing.grobid_client import GrobidClient, GrobidConfig

TEI_XML = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader>
    <fileDesc>
      <titleStmt>
        <title>Test Paper Title</title>
      </titleStmt>
      <sourceDesc>
        <biblStruct>
          <analytic>
            <author>
              <forename>Alice</forename>
              <surname>Smith</surname>
            </author>
            <author>
              <forename>Bob</forename>
              <surname>Jones</surname>
            </author>
          </analytic>
          <monogr>
            <title>J Test Studies</title>
          </monogr>
        </biblStruct>
      </sourceDesc>
    </fileDesc>
    <profileDesc>
      <abstract>
        <p>This is the abstract of the test paper.</p>
      </abstract>
    </profileDesc>
  </teiHeader>
  <text>
    <body>
      <div>
        <head>Introduction</head>
        <p>This is the introduction section.</p>
      </div>
      <div>
        <head>Methods</head>
        <p>We used a test method.</p>
      </div>
    </body>
    <back>
      <div type="references">
        <listBibl>
          <biblStruct>
            <analytic>
              <title>Some Reference</title>
            </analytic>
            <monogr>
              <title>Journal of X</title>
              <imprint>
                <date type="published">2020</date>
              </imprint>
            </monogr>
          </biblStruct>
        </listBibl>
      </div>
    </back>
  </text>
</TEI>
"""


class TestGrobidClient:
    @pytest.mark.asyncio
    @respx.mock
    async def test_process_pdf(self):
        config = GrobidConfig(timeout=10)
        client = GrobidClient(config)

        respx.get("http://localhost:8070/api/isalive").mock(return_value=Response(200))
        respx.post("http://localhost:8070/api/processFulltextDocument").mock(
            return_value=Response(200, text=TEI_XML),
        )

        article = await client.process_fulltext(b"mock pdf bytes")
        assert article is not None
        assert article.title == "Test Paper Title"
        assert len(article.authors) == 2
        assert article.authors[0].first == "Alice"
        assert article.authors[0].last == "Smith"
        assert article.journal == "J Test Studies"
        assert "abstract" in article.abstract.lower()
        assert len(article.sections) == 2
        assert len(article.references) == 1
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_grobid_unavailable(self):
        config = GrobidConfig(timeout=5)
        client = GrobidClient(config)

        respx.get("http://localhost:8070/api/isalive").mock(
            return_value=Response(503),
        )

        result = await client.process_fulltext(b"mock pdf bytes")
        assert result is None
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_grobid_connection_error(self):
        config = GrobidConfig(timeout=5)
        client = GrobidClient(config)

        respx.get("http://localhost:8070/api/isalive").mock(
            return_value=Response(200),
        )
        respx.post("http://localhost:8070/api/processFulltextDocument").mock(
            return_value=Response(500),
        )

        with pytest.raises(Exception, match="GROBID API error"):
            await client.process_fulltext(b"mock pdf bytes")
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_check_availability_cached(self):
        config = GrobidConfig(timeout=5)
        client = GrobidClient(config)

        respx.get("http://localhost:8070/api/isalive").mock(return_value=Response(200))
        assert await client.check_availability() is True
        assert client._available is True
        await client.close()

# SPDX-License-Identifier: Apache-2.0

import pytest
import respx
from httpx import Request, Response
from openscire.references.bridges.arxiv import (
    ARXIV_CATEGORIES,
    ArXivClient,
    arxiv_category_name,
    is_valid_arxiv_category,
)

ATOM_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <opensearch:totalResults xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">1</opensearch:totalResults>
  <entry>
    <id>http://arxiv.org/abs/2401.12345</id>
    <title>  A Test Paper on Machine Learning  </title>
    <author>
      <name>John Smith</name>
    </author>
    <author>
      <name>Jane Doe</name>
    </author>
    <summary>This is a test abstract describing novel machine learning methods.</summary>
    <published>2024-01-15T00:00:00Z</published>
    <arxiv:primary_category term="cs.LG"/>
    <category term="cs.LG"/>
    <category term="stat.ML"/>
    <arxiv:doi>10.1234/arxiv.2024.001</arxiv:doi>
    <arxiv:comment>12 pages, 3 figures</arxiv:comment>
    <arxiv:journal_ref>J. Mach. Learn. 10 (2024) 100</arxiv:journal_ref>
  </entry>
</feed>"""

ATOM_EMPTY = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <opensearch:totalResults xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">0</opensearch:totalResults>
</feed>"""

ATOM_MULTI = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <opensearch:totalResults xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">2</opensearch:totalResults>
  <entry>
    <id>http://arxiv.org/abs/2401.11111</id>
    <title>First Paper</title>
    <author><name>Alice A</name></author>
    <summary>Abstract A.</summary>
    <published>2024-01-01T00:00:00Z</published>
    <category term="cs.CL"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2401.22222</id>
    <title>Second Paper</title>
    <author><name>Bob B</name></author>
    <summary>Abstract B.</summary>
    <published>2024-02-01T00:00:00Z</published>
    <arxiv:doi>10.1234/arxiv.2024.002</arxiv:doi>
    <category term="cs.LG"/>
  </entry>
</feed>"""

SAMPLE_TEX = b"\\documentclass{article}\n\\begin{document}\nHello\n\\end{document}\n"
GZIPPED_TEX = __import__("gzip").compress(SAMPLE_TEX)


@pytest.fixture
def client() -> ArXivClient:
    return ArXivClient(email="test@example.com", tool="test_tool")


class TestArXivClient:
    def test_constructor(self) -> None:
        c = ArXivClient(email="x@y.com", tool="mytool")
        assert c._email == "x@y.com"
        assert c._tool == "mytool"

    def test_constructor_defaults(self) -> None:
        c = ArXivClient()
        assert c._email == ""
        assert c._tool == "openscire"

    @pytest.mark.asyncio
    @respx.mock
    async def test_search(self, client: ArXivClient) -> None:
        respx.get("https://export.arxiv.org/api/query").mock(
            return_value=Response(200, content=ATOM_FEED)
        )
        result = await client.search("machine learning")
        assert result.arxiv_ids == ["2401.12345"]
        assert result.total_count == 1
        assert result.start == 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_returns_items(self, client: ArXivClient) -> None:
        respx.get("https://export.arxiv.org/api/query").mock(
            return_value=Response(200, content=ATOM_FEED)
        )
        items = await client.fetch_by_id("2401.12345")
        assert len(items) == 1
        item = items[0]
        assert item.id == "2401.12345"
        assert "Test Paper" in item.title
        assert item.doi == "10.1234/arxiv.2024.001"
        assert len(item.authors) == 2
        assert item.authors[0].full == "John Smith"
        assert item.authors[1].full == "Jane Doe"
        assert "machine learning" in item.abstract.lower()
        assert item.year == 2024
        assert item.url == "https://arxiv.org/abs/2401.12345"
        assert item.source.value == "arxiv"
        assert item.item_type == "article"
        assert "cs.LG" in item.keywords
        assert item.extra.get("comment") == "12 pages, 3 figures"
        assert item.extra.get("journal_ref") == "J. Mach. Learn. 10 (2024) 100"
        assert item.extra.get("primary_category") == "cs.LG"

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_empty(self, client: ArXivClient) -> None:
        respx.get("https://export.arxiv.org/api/query").mock(
            return_value=Response(200, content=ATOM_EMPTY)
        )
        result = await client.search("nonexistent")
        assert result.arxiv_ids == []
        assert result.total_count == 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_by_id(self, client: ArXivClient) -> None:
        respx.get("https://export.arxiv.org/api/query").mock(
            return_value=Response(200, content=ATOM_FEED)
        )
        items = await client.fetch_by_id("2401.12345")
        assert len(items) == 1
        assert items[0].id == "2401.12345"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_by_id_multiple(self, client: ArXivClient) -> None:
        respx.get("https://export.arxiv.org/api/query").mock(
            return_value=Response(200, content=ATOM_MULTI)
        )
        items = await client.fetch_by_id(["2401.11111", "2401.22222"])
        assert len(items) == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_by_category(self, client: ArXivClient) -> None:
        def check_params(request: Request) -> Response:
            assert "cat:cs.LG" in request.url.params.get("search_query", "")
            return Response(200, content=ATOM_EMPTY)

        respx.get("https://export.arxiv.org/api/query").mock(side_effect=check_params)
        await client.search_by_category("cs.LG")

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_by_author(self, client: ArXivClient) -> None:
        def check_params(request: Request) -> Response:
            assert 'au:"John Smith"' in request.url.params.get("search_query", "")
            return Response(200, content=ATOM_EMPTY)

        respx.get("https://export.arxiv.org/api/query").mock(side_effect=check_params)
        await client.search_by_author("John Smith")

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_by_date_range(self, client: ArXivClient) -> None:
        def check_params(request: Request) -> Response:
            sq = request.url.params.get("search_query", "")
            assert "submittedDate:[" in sq
            assert "2024-01-01" in sq
            assert "2024-12-31" in sq
            return Response(200, content=ATOM_EMPTY)

        respx.get("https://export.arxiv.org/api/query").mock(side_effect=check_params)
        await client.search_by_date_range("2024-01-01", "2024-12-31")

    @pytest.mark.asyncio
    @respx.mock
    async def test_resolve_arxiv_to_doi(self, client: ArXivClient) -> None:
        respx.get("https://export.arxiv.org/api/query").mock(
            return_value=Response(200, content=ATOM_FEED)
        )
        doi = await client.resolve_arxiv_to_doi("2401.12345")
        assert doi == "10.1234/arxiv.2024.001"

    @pytest.mark.asyncio
    @respx.mock
    async def test_resolve_arxiv_to_doi_not_found(self, client: ArXivClient) -> None:
        respx.get("https://export.arxiv.org/api/query").mock(
            return_value=Response(200, content=ATOM_EMPTY)
        )
        doi = await client.resolve_arxiv_to_doi("0000.00000")
        assert doi is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_resolve_doi_to_arxiv(self, client: ArXivClient) -> None:
        respx.get("https://export.arxiv.org/api/query").mock(
            return_value=Response(200, content=ATOM_FEED)
        )
        arxiv_id = await client.resolve_doi_to_arxiv("10.1234/arxiv.2024.001")
        assert arxiv_id == "2401.12345"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_source(self, client: ArXivClient) -> None:
        respx.get("https://arxiv.org/e-print/2401.12345").mock(
            return_value=Response(200, content=SAMPLE_TEX)
        )
        data = await client.fetch_source("2401.12345")
        assert data == SAMPLE_TEX

    def test_extract_tex_files_plain(self) -> None:
        files = ArXivClient.extract_tex_files(SAMPLE_TEX)
        assert len(files) == 1
        assert files[0][0] == "main.tex"
        assert "documentclass" in files[0][1]

    def test_extract_tex_files_gzip(self) -> None:
        files = ArXivClient.extract_tex_files(GZIPPED_TEX)
        assert len(files) == 1
        assert "documentclass" in files[0][1]

    def test_extract_tex_files_invalid(self) -> None:
        files = ArXivClient.extract_tex_files(b"")
        assert files == [("main.tex", "")]

    @pytest.mark.asyncio
    async def test_close(self, client: ArXivClient) -> None:
        await client.close()

    def test_is_valid_category(self) -> None:
        assert is_valid_arxiv_category("cs.LG")
        assert is_valid_arxiv_category("stat.ML")
        assert is_valid_arxiv_category("q-bio.GN")
        # Unknown format but matches regex pattern
        assert is_valid_arxiv_category("custom.Cat")
        # Invalid
        assert not is_valid_arxiv_category("")
        assert not is_valid_arxiv_category("invalid category!")

    def test_arxiv_category_name(self) -> None:
        assert arxiv_category_name("cs.LG") == "Machine Learning"
        assert arxiv_category_name("stat.ML") == "Machine Learning (Statistics)"
        assert arxiv_category_name("unknown.XXX") == "unknown.XXX"

    def test_category_dict_coverage(self) -> None:
        """Ensure all defined categories are valid per the validation function."""
        for cat in ARXIV_CATEGORIES:
            assert is_valid_arxiv_category(cat), f"{cat} should be valid"

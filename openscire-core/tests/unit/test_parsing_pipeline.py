import pytest
from openscire.references.models import FullTextArticle
from openscire.references.parsing.models import ExtractionResult
from openscire.references.parsing.pipeline import PDFParsingPipeline


class TestPDFParsingPipeline:
    @pytest.mark.asyncio
    async def test_parse_pdfplumber_fallback(self, mocker):
        mock_extracted = {
            "pages": [],
            "metadata": {},
            "raw_text": "Title Page\n\nAbstract\nThis is the abstract.\n\nIntroduction\nContent.\n\nReferences\n[1] Ref one.\n[2] Ref two.\n",
            "elapsed": 0.1,
        }
        mocker.patch(
            "openscire.references.parsing.pdf_extractor.PDFExtractor.extract",
            return_value=mock_extracted,
        )

        pipeline = PDFParsingPipeline()
        result = await pipeline.parse(b"mock pdf")
        assert isinstance(result, ExtractionResult)
        assert result.method == "pdfplumber"
        assert result.full_text.abstract == "This is the abstract."
        assert len(result.parsed_references) >= 2

    @pytest.mark.asyncio
    async def test_parse_grobid_primary(self, mocker):
        mock_article = FullTextArticle(
            title="GROBID Title",
            references=["[1] Ref one.", "[2] Ref two."],
        )

        mocker.patch(
            "openscire.references.parsing.grobid_client.GrobidClient.check_availability",
            return_value=True,
        )
        mocker.patch(
            "openscire.references.parsing.grobid_client.GrobidClient.process_fulltext",
            return_value=mock_article,
        )

        pipeline = PDFParsingPipeline(grobid_config=mocker.MagicMock())
        result = await pipeline.parse(b"mock pdf")
        assert result.method == "grobid"
        assert result.full_text.title == "GROBID Title"

    @pytest.mark.asyncio
    async def test_extraction_error(self, mocker):
        mocker.patch(
            "openscire.references.parsing.pdf_extractor.PDFExtractor.extract",
            side_effect=Exception("PDF corrupted"),
        )

        pipeline = PDFParsingPipeline()
        result = await pipeline.parse(b"bad pdf")
        assert result.method == "error"
        assert any("PDF extraction failed" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_parse_file(self, mocker):
        mock_data = {
            "pages": [],
            "metadata": {},
            "raw_text": "Title\n\nAbstract content.\n\nIntroduction\nBody.\n",
            "elapsed": 0.1,
        }
        mocker.patch(
            "openscire.references.parsing.pdf_extractor.PDFExtractor.extract",
            return_value=mock_data,
        )
        mocker.patch("builtins.open", mocker.mock_open(read_data=b"mock pdf"))

        pipeline = PDFParsingPipeline()
        result = await pipeline.parse_file("/fake/path.pdf")
        assert result.method == "pdfplumber"
        assert result.source_path == "/fake/path.pdf"

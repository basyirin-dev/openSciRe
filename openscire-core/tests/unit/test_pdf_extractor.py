import pytest
from openscire.exceptions import ReferenceError
from openscire.references.parsing.pdf_extractor import PDFExtractor


@pytest.fixture
def mock_pdfplumber(mocker):
    pdf_module = mocker.MagicMock()
    page1 = mocker.MagicMock()
    page1.extract_text.return_value = "Page 1 text"
    page1.extract_tables.return_value = [["a", "b"]]
    page1.width = 612
    page1.height = 792

    page2 = mocker.MagicMock()
    page2.extract_text.return_value = "Page 2 text"
    page2.extract_tables.return_value = None
    page2.width = 612
    page2.height = 792

    pdf_doc = mocker.MagicMock()
    pdf_doc.pages = [page1, page2]
    pdf_doc.metadata = {"title": "Test Paper"}

    pdf_module.open.return_value = pdf_doc
    mocker.patch(
        "openscire.references.parsing.pdf_extractor.PDFExtractor._get_pdfplumber",
        return_value=pdf_module,
    )
    return pdf_module


class TestPDFExtractor:
    def test_extract_text(self, mock_pdfplumber):
        extractor = PDFExtractor()
        pdf_bytes = b"%PDF-1.4 mock data"
        result = extractor.extract(pdf_bytes)

        assert len(result["pages"]) == 2
        assert result["pages"][0].text == "Page 1 text"
        assert result["pages"][1].text == "Page 2 text"
        assert "Page 1 text\nPage 2 text" in result["raw_text"]
        assert result["metadata"]["title"] == "Test Paper"

    def test_encrypted_pdf(self, mock_pdfplumber):
        mock_pdfplumber.open.return_value.metadata = {"encrypted": True}
        extractor = PDFExtractor()
        with pytest.raises(ReferenceError, match="Encrypted PDF"):
            extractor.extract(b"encrypted")

    def test_error_on_corrupted_pdf(self, mock_pdfplumber):
        mock_pdfplumber.open.side_effect = Exception("Corrupted PDF")
        extractor = PDFExtractor()
        with pytest.raises(ReferenceError, match="Failed to open PDF"):
            extractor.extract(b"corrupted")

    def test_extract_from_path(self, mocker, mock_pdfplumber):
        mocker.patch(
            "builtins.open",
            mocker.mock_open(read_data=b"%PDF-1.4 mock data"),
        )
        extractor = PDFExtractor()
        result = extractor.extract_from_path("/fake/paper.pdf")
        assert len(result["pages"]) == 2

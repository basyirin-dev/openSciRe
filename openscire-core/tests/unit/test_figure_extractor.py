from openscire.references.parsing.figure_extractor import FigureExtractor


class TestFigureExtractor:
    def test_extract_captions(self):
        text = """Some text before.
Figure 1: This is the first figure caption.
More text between.
Figure 2: Second figure with details.
Table 1: Results summary table.
"""
        extractor = FigureExtractor()
        captions = extractor.extract_captions(text)
        assert len(captions) >= 2
        labels = [c["label"] for c in captions]
        assert "Figure 1" in labels
        assert "Figure 2" in labels

    def test_extract_tables(self):
        text = """Table 1: Experimental conditions.
Some data here.
Table 2: Statistical results.
"""
        extractor = FigureExtractor()
        captions = extractor.extract_captions(text)
        table_labels = [c["label"] for c in captions if "Table" in c["label"]]
        assert len(table_labels) >= 2

    def test_no_figures(self):
        text = """Just text without any figure or table captions at all."""
        extractor = FigureExtractor()
        captions = extractor.extract_captions(text)
        assert captions == []

    def test_extract_with_line_based_fallback(self):
        text = """Some text.
Fig. 1: A figure caption in line format.
Fig. 2: Another figure.
"""
        extractor = FigureExtractor()
        captions = extractor.extract_captions(text)
        labels = [c["label"] for c in captions]
        assert "Figure 1" in labels or "Fig. 1" in labels

    def test_extract_returns_article_figures(self, mocker):
        extractor = FigureExtractor()
        text = """Figure 1: A sample figure caption.

Some text here.
Figure 2: Another figure.

Table 1: A table.
"""
        mocker.patch.object(extractor, "_get_pymupdf", return_value=mocker.MagicMock())

        figures = extractor.extract(b"pdf bytes", text)
        assert len(figures) >= 2
        labels = [f.label for f in figures]
        assert "Figure 1" in labels
        assert "Figure 2" in labels

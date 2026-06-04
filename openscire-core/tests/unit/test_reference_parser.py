from openscire.references.parsing.reference_parser import ReferenceParser


class TestReferenceParser:
    def test_extract_numbered_refs(self):
        text = """[1] Smith A, Jones B. A study on X. J Science. 2020;10:100-110.
[2] Lee C, et al. Another study. J Results. 2021;11:200-210.
[3] Wang D. Third reference. J Methods. 2022;12:300-310.
"""
        parser = ReferenceParser()
        refs = parser.extract_references(text)
        assert len(refs) == 3
        assert refs[0].index == 1
        assert refs[1].index == 2
        assert refs[2].index == 3
        assert "Smith" in refs[0].raw_text

    def test_extract_doi_and_pmid(self):
        text = """[1] Smith A, et al. Important paper. Nature. 2020;10:100.
doi: 10.1038/s41586-020-2001-0 PMID: 32165498

[2] Jones B, et al. arXiv paper. arXiv:2105.12345
"""
        parser = ReferenceParser()
        refs = parser.extract_references(text)
        assert len(refs) == 2
        assert refs[0].doi == "10.1038/s41586-020-2001-0"
        assert refs[0].pmid == "32165498"
        assert refs[1].arxiv_id == "2105.12345"

    def test_no_references(self):
        text = "Just some text without any references at all."
        parser = ReferenceParser()
        refs = parser.extract_references(text)
        assert refs == []

    def test_multi_format_refs(self):
        text = """1. Miller D, et al. (2019) A paper. J Sci. 10:100.
[2] Taylor E, et al. (2020) Another paper. J Res. 11:200.
(3) Garcia F, et al. (2021) Third paper. J Meth. 12:300.
"""
        parser = ReferenceParser()
        refs = parser.extract_references(text)
        assert len(refs) == 3

    def test_enrich_with_doi(self):
        text = """[1] Smith A, et al. (2020) A study on X. J Science. 10.1234/test.doi
"""
        parser = ReferenceParser()
        refs = parser.extract_references(text)
        assert len(refs) == 1
        assert refs[0].doi == "10.1234/test.doi"
        assert refs[0].confidence > 0.5

# SPDX-License-Identifier: Apache-2.0

from openscire.references.importers.medline_importer import MedlineImporter

SAMPLE_MEDLINE = """PMID- 12345678
TI  - A test article about machine learning in bioinformatics
AB  - This is a test abstract describing a novel method for sequence alignment.
AU  - Smith J
AU  - Doe J
DP  - 2024 Jan 15
VI  - 10
IP  - 2
PG  - 100-110
AID - 10.1234/test.2024.001 [doi]
MH  - Machine Learning
MH  - Computational Biology
MH  - Algorithms/statistics & numerical data
PT  - Journal Article
PT  - Research Support, Non-U.S. Gov't

"""

MULTI_RECORD = """PMID- 1111111
TI  - First article
DP  - 2023
VI  - 1
IP  - 1
PG  - 1-10
AID - 10.1/test.2023 [doi]

PMID- 2222222
TI  - Second article
DP  - 2024
VI  - 2
IP  - 1
PG  - 20-30
AID - 10.2/test.2024 [doi]

"""


class TestMedlineImporter:
    def test_simple_parse(self) -> None:
        importer = MedlineImporter()
        items = importer.parse(SAMPLE_MEDLINE)
        assert len(items) == 1
        item = items[0]
        assert item.id == "12345678"
        assert item.source.value == "pubmed"
        assert "machine learning" in item.title.lower()
        assert "sequence alignment" in item.abstract.lower()
        assert len(item.authors) == 2
        assert item.authors[0].last == "Smith"
        assert item.authors[0].first == "J"
        assert item.year == 2024
        assert item.volume == "10"
        assert item.issue == "2"
        assert item.pages == "100-110"
        assert item.doi == "10.1234/test.2024.001"
        assert "Machine Learning" in item.keywords
        assert "Computational Biology" in item.keywords

    def test_mesh_extraction(self) -> None:
        importer = MedlineImporter()
        items = importer.parse(SAMPLE_MEDLINE)
        mesh = items[0].extra.get("mesh_terms", [])
        assert len(mesh) == 3
        # The importer stores raw MH lines in extra["mesh_terms"] as strings,
        # and parses keywords (descriptor only) from them
        assert mesh[0] == "Machine Learning"
        assert mesh[1] == "Computational Biology"
        # Third term has qualifier - whole string stored
        assert "Algorithms" in mesh[2]
        # keywords (descriptor-only) extracted from mesh terms
        kw = items[0].keywords
        assert "Machine Learning" in kw
        assert "Computational Biology" in kw
        assert "Algorithms" in kw

    def test_multiple_records(self) -> None:
        importer = MedlineImporter()
        items = importer.parse(MULTI_RECORD)
        assert len(items) == 2
        assert items[0].id == "1111111"
        assert items[1].id == "2222222"

    def test_empty_input(self) -> None:
        importer = MedlineImporter()
        items = importer.parse("")
        assert items == []

    def test_field_continuation(self) -> None:
        text = """PMID- 999999
TI  - A very long title that spans
      multiple lines in the MEDLINE
      format for testing
DP  - 2024
"""
        importer = MedlineImporter()
        items = importer.parse(text)
        assert len(items) == 1
        assert "multiple lines" in items[0].title
        assert "format for testing" in items[0].title

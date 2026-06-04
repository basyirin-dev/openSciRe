from openscire.references.parsing.section_parser import SectionParser


class TestSectionParser:
    def test_standard_imrad(self):
        text = """A Novel Method for X

Alice Smith, Bob Jones

Abstract
This is the abstract of the paper.

Introduction
This is the introduction section.

Methods
We used a novel approach.

Results
We found significant results.

Discussion
These results confirm our hypothesis.

References
[1] Smith A, et al. (2020) Some paper.
[2] Jones B, et al. (2021) Another paper.
"""
        parser = SectionParser()
        article = parser.parse(text)

        assert article.title == "A Novel Method for X"
        assert "This is the abstract" in article.abstract
        assert len(article.sections) >= 4

        headings = [s.heading for s in article.sections]
        assert "Introduction" in headings
        assert "Methods" in headings
        assert "Results" in headings
        assert "Discussion" in headings

        assert len(article.references) == 2

    def test_missing_abstract(self):
        text = """Title Only Paper

Introduction
Content without abstract.
"""
        parser = SectionParser()
        article = parser.parse(text)
        assert article.title == "Title Only Paper"
        assert article.abstract == ""

    def test_no_sections(self):
        text = """Just a blob of text with no clear section headings.
Paragraph one about something.
Paragraph two about something else.
"""
        parser = SectionParser()
        article = parser.parse(text)
        assert len(article.sections) == 1
        assert article.sections[0].heading == ""
        assert "blob of text" in article.sections[0].body

    def test_single_column(self):
        text = """Single Column Title

Methods
The method section.

Results
The results.
"""
        parser = SectionParser()
        article = parser.parse(text)
        assert len([s for s in article.sections if s.heading]) >= 2

    def test_non_english(self):
        text = """Título del Artículo

Resumen
Este es el resumen.

Introducción
Este es la introducción.

Métodos
Los métodos utilizados.

Resultados
Los resultados obtenidos.
"""
        parser = SectionParser()
        article = parser.parse(text)
        assert article.abstract == ""
        assert len(article.sections) == 1

# SPDX-License-Identifier: Apache-2.0

from openscire.references.mesh import (
    MeshIndex,
    extract_mesh_from_medline,
    extract_mesh_from_xml,
)
from openscire.references.models import MeshTerm


class TestExtractMeshFromMedline:
    def test_single_term(self) -> None:
        line = "MH  - Machine Learning"
        terms = extract_mesh_from_medline(line)
        assert len(terms) == 1
        assert terms[0].descriptor == "Machine Learning"
        assert terms[0].qualifier == ""

    def test_term_with_qualifier(self) -> None:
        line = "MH  - Algorithms/statistics & numerical data"
        terms = extract_mesh_from_medline(line)
        assert len(terms) == 1
        assert terms[0].descriptor == "Algorithms"
        assert terms[0].qualifier == "statistics & numerical data"

    def test_term_with_focus(self) -> None:
        line = "MH  - *Neoplasms"
        terms = extract_mesh_from_medline(line)
        assert len(terms) == 1
        assert terms[0].descriptor == "Neoplasms"

    def test_term_with_ui(self) -> None:
        line = "MH  - Diabetes Mellitus, Type 2/Drug Therapy"
        terms = extract_mesh_from_medline(line)
        assert len(terms) == 1
        assert terms[0].descriptor == "Diabetes Mellitus, Type 2"
        assert terms[0].qualifier == "Drug Therapy"

    def test_empty_line(self) -> None:
        assert extract_mesh_from_medline("") == []

    def test_non_mesh_line(self) -> None:
        assert extract_mesh_from_medline("AU  - Smith J") == []


class TestExtractMeshFromXml:
    def test_single_descriptor(self) -> None:
        xml = """<MeshHeadingList>
            <MeshHeading>
                <DescriptorName UI="D000001" MajorTopicYN="N">Machine Learning</DescriptorName>
            </MeshHeading>
        </MeshHeadingList>"""
        terms = extract_mesh_from_xml(xml)
        assert len(terms) == 1
        assert terms[0].descriptor == "Machine Learning"
        assert terms[0].ui == "D000001"

    def test_descriptor_with_qualifier(self) -> None:
        xml = """<MeshHeadingList>
            <MeshHeading>
                <DescriptorName UI="D000123">Algorithms</DescriptorName>
                <QualifierName UI="Q000003">statistics and numerical data</QualifierName>
            </MeshHeading>
        </MeshHeadingList>"""
        terms = extract_mesh_from_xml(xml)
        assert len(terms) == 1
        assert terms[0].descriptor == "Algorithms"
        assert terms[0].qualifier == "statistics and numerical data"
        assert terms[0].ui == "Q000003"

    def test_multiple_headings(self) -> None:
        xml = """<MeshHeadingList>
            <MeshHeading>
                <DescriptorName UI="D001">Term A</DescriptorName>
            </MeshHeading>
            <MeshHeading>
                <DescriptorName UI="D002">Term B</DescriptorName>
                <QualifierName UI="Q001">therapy</QualifierName>
            </MeshHeading>
        </MeshHeadingList>"""
        terms = extract_mesh_from_xml(xml)
        assert len(terms) == 2
        assert terms[0].descriptor == "Term A"
        assert terms[1].descriptor == "Term B"
        assert terms[1].qualifier == "therapy"

    def test_empty_element(self) -> None:
        assert extract_mesh_from_xml("<MeshHeadingList/>") == []


class TestMeshIndex:
    def test_add_and_search(self) -> None:
        index = MeshIndex()
        index.add(
            "123",
            [
                MeshTerm(descriptor="Neoplasms"),
                MeshTerm(descriptor="Algorithms", qualifier="statistics"),
                MeshTerm(descriptor="Machine Learning", ui="D000001"),
            ],
        )
        results = index.search_by_descriptor("neoplasms")
        assert "123" in results
        results = index.search_by_descriptor("Algorithms")
        assert "123" in results
        results = index.search_by_ui("D000001")
        assert "123" in results

    def test_search_missing(self) -> None:
        index = MeshIndex()
        assert index.search_by_descriptor("NonexistentTerm") == []

    def test_article_count(self) -> None:
        index = MeshIndex()
        assert index.article_count == 0
        index.add("123", [MeshTerm(descriptor="Cancer")])
        assert index.article_count == 1

    def test_get_for_article(self) -> None:
        index = MeshIndex()
        index.add("123", [MeshTerm(descriptor="Cancer")])
        terms = index.get_for_article("123")
        assert terms is not None
        assert terms[0].descriptor == "Cancer"
        assert index.get_for_article("999") is None

    def test_unique_descriptors(self) -> None:
        index = MeshIndex()
        index.add("1", [MeshTerm(descriptor="Cancer")])
        index.add("2", [MeshTerm(descriptor="Cancer")])
        index.add("3", [MeshTerm(descriptor="Diabetes")])
        descs = index.unique_descriptors
        assert len(descs) == 2
        assert "cancer" in descs
        assert "diabetes" in descs

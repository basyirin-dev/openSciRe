# SPDX-License-Identifier: Apache-2.0

"""Integration test: Semantic Scholar -> OpenAlex cross-ref -> citation graph -> export.

Tests cross-referencing between Semantic Scholar citations and OpenAlex
works, building a citation graph, scoring influence, and exporting.
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response
from openscire.references.bridges.openalex import OpenAlexClient
from openscire.references.bridges.semantic_scholar import SemanticScholarClient
from openscire.references.graph import (
    CitationGraphAnalyzer,
    CitationGraphBuilder,
    GraphExporter,
    InfluenceScorer,
)

pytestmark = [
    pytest.mark.integration,
]

CITING_PAPER_S2 = {
    "paperId": "citing001",
    "title": "Citing Paper",
    "authors": [{"authorId": "ca1", "name": "Citing Author"}],
    "year": 2024,
    "externalIds": {"DOI": "10.1234/citing.2024"},
}

CITED_PAPER_S2 = {
    "paperId": "cited001",
    "title": "Cited Paper",
    "authors": [{"authorId": "ra1", "name": "Cited Author"}],
    "year": 2020,
    "externalIds": {"DOI": "10.1234/cited.2020"},
}

CITATIONS_RESPONSE = {
    "data": [
        {
            "citingPaper": CITING_PAPER_S2,
            "contexts": ["As shown in [1]."],
            "isInfluential": True,
        },
    ],
    "next": None,
}

REFERENCES_RESPONSE = {
    "data": [
        {
            "citedPaper": CITED_PAPER_S2,
            "contexts": ["Builds on [2]."],
            "isInfluential": False,
        },
    ],
    "next": None,
}

OPENALEX_WORK = {
    "id": "https://openalex.org/W2741809807",
    "doi": "https://doi.org/10.1234/cited.2020",
    "display_name": "Cited Paper",
    "publication_year": 2020,
    "cited_by_count": 142,
    "is_retracted": False,
    "referenced_works": ["https://openalex.org/W000000001"],
    "related_works": ["https://openalex.org/W000000002"],
    "open_access": {"is_oa": True, "oa_status": "gold", "oa_url": ""},
    "authorships": [],
    "ids": {},
    "primary_location": None,
    "topics": [],
    "concepts": [],
    "keywords": [],
    "biblio": {},
    "type": "article",
    "language": "en",
    "counts_by_year": [],
    "fwci": None,
}

OPENALEX_WORK_CITING = {
    "id": "https://openalex.org/W2741809808",
    "doi": "https://doi.org/10.1234/citing.2024",
    "display_name": "Citing Paper",
    "publication_year": 2024,
    "cited_by_count": 5,
    "is_retracted": False,
    "referenced_works": ["https://openalex.org/W2741809807"],
    "open_access": {"is_oa": False, "oa_status": "", "oa_url": ""},
    "authorships": [],
    "ids": {},
    "primary_location": None,
    "topics": [],
    "concepts": [],
    "keywords": [],
    "biblio": {},
    "type": "article",
    "language": "en",
    "counts_by_year": [],
    "fwci": None,
}


class TestBridgeCrossrefCycle:
    """Semantic Scholar -> OpenAlex -> graph -> influence -> export."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_crossref_cycle(self) -> None:
        s2 = SemanticScholarClient()
        oa = OpenAlexClient()

        respx.get(
            "https://api.semanticscholar.org/graph/v1/paper/detail001/citations",
        ).mock(return_value=Response(200, json=CITATIONS_RESPONSE))

        respx.get(
            "https://api.semanticscholar.org/graph/v1/paper/detail001/references",
        ).mock(return_value=Response(200, json=REFERENCES_RESPONSE))

        respx.get(
            "https://api.openalex.org/works/doi/10.1234/cited.2020",
        ).mock(return_value=Response(200, json=OPENALEX_WORK))

        citations = await s2.get_citations("detail001")
        assert len(citations) == 1
        citing_doi = citations[0].citing_paper.doi
        assert citing_doi == "10.1234/citing.2024"

        references = await s2.get_references("detail001")
        assert len(references) == 1
        cited_doi = references[0].cited_paper.doi
        assert cited_doi == "10.1234/cited.2020"

        oa_result = await oa.fetch_work(f"doi/{cited_doi}")
        assert oa_result.extra.get("cited_by_count") == 142
        assert not oa_result.extra.get("is_retracted", False)

        citing_item = citations[0].citing_paper
        cited_item = references[0].cited_paper
        ref_lookup = {citing_item.id: citing_item, cited_item.id: cited_item}

        # Create a combined citation entry with both sides populated
        from openscire.references.models import CitationGraphEntry
        combined_entry = CitationGraphEntry(
            citing_paper=citing_item,
            cited_paper=cited_item,
            contexts=["Builds on prior work."],
            is_influential=True,
        )
        graph = CitationGraphBuilder.build_from_entries([combined_entry], ref_lookup)
        assert len(graph.nodes) >= 2
        assert graph.has_edge(citing_item.id, cited_item.id)

        scorer = InfluenceScorer()
        report = scorer.score(graph)
        assert len(report.results) > 0
        assert all(0.0 <= r.score <= 1.0 for r in report.results)

        exporter = GraphExporter()
        d3 = exporter.to_d3_json(graph)
        assert len(d3.data["nodes"]) >= 2
        assert len(d3.data["edges"]) >= 1

        cy = exporter.to_cytoscape_json(graph)
        assert len(cy.data["elements"]["nodes"]) >= 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_analyzer_orchestration(self) -> None:
        oa = OpenAlexClient()

        respx.get(
            "https://api.openalex.org/works/doi/10.1234/cited.2020",
        ).mock(return_value=Response(200, json=OPENALEX_WORK))
        respx.get(
            "https://api.openalex.org/works/doi/10.1234/citing.2024",
        ).mock(return_value=Response(200, json=OPENALEX_WORK_CITING))

        cited = await oa.fetch_work("doi/10.1234/cited.2020")
        citing = await oa.fetch_work("doi/10.1234/citing.2024")

        graph = CitationGraphBuilder.build([cited, citing])
        assert len(graph.nodes) >= 2

        analyzer = CitationGraphAnalyzer()
        report = analyzer.analyze([cited, citing])
        assert report.node_count >= 2

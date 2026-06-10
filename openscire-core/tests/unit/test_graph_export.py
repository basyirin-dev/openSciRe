# SPDX-License-Identifier: Apache-2.0

"""Tests for GraphExporter."""

import networkx as nx
import pytest
from openscire.references.graph.export import GraphExporter


class TestD3Export:
    def test_empty_graph(self) -> None:
        g = nx.DiGraph()
        export = GraphExporter.to_d3_json(g)
        assert export.format == "d3"
        assert "nodes" in export.data
        assert "edges" in export.data
        assert export.data["nodes"] == []
        assert export.data["edges"] == []

    def test_single_node(self) -> None:
        g = nx.DiGraph()
        g.add_node("W001", ref=None)
        export = GraphExporter.to_d3_json(g)
        assert len(export.data["nodes"]) == 1
        assert export.data["nodes"][0]["id"] == "W001"

    def test_edge_included(self) -> None:
        g = nx.DiGraph()
        g.add_node("W001", ref=None)
        g.add_node("W002", ref=None)
        g.add_edge("W001", "W002", is_influential=True)
        export = GraphExporter.to_d3_json(g)
        assert len(export.data["edges"]) == 1
        assert export.data["edges"][0]["source"] == "W001"
        assert export.data["edges"][0]["target"] == "W002"

    def test_node_attributes_preserved(self) -> None:
        g = nx.DiGraph()
        g.add_node("W001", ref="test_ref")
        export = GraphExporter.to_d3_json(g)
        assert export.data["nodes"][0]["ref"] == "test_ref"


class TestCytoscapeExport:
    def test_empty_graph(self) -> None:
        g = nx.DiGraph()
        export = GraphExporter.to_cytoscape_json(g)
        assert export.format == "cytoscape"
        assert "elements" in export.data
        assert "nodes" in export.data["elements"]
        assert "edges" in export.data["elements"]

    def test_single_node(self) -> None:
        g = nx.DiGraph()
        g.add_node("W001", ref=None)
        export = GraphExporter.to_cytoscape_json(g)
        nodes = export.data["elements"]["nodes"]
        assert len(nodes) == 1
        assert nodes[0]["data"]["id"] == "W001"

    def test_edge_format(self) -> None:
        g = nx.DiGraph()
        g.add_node("W001", ref=None)
        g.add_node("W002", ref=None)
        g.add_edge("W001", "W002")
        export = GraphExporter.to_cytoscape_json(g)
        edges = export.data["elements"]["edges"]
        assert len(edges) == 1
        assert edges[0]["data"]["source"] == "W001"
        assert edges[0]["data"]["target"] == "W002"


class TestExportMethod:
    def test_export_d3(self) -> None:
        g = nx.DiGraph()
        g.add_node("W001")
        export = GraphExporter.export(g, "d3")
        assert export.format == "d3"

    def test_export_cytoscape(self) -> None:
        g = nx.DiGraph()
        g.add_node("W001")
        export = GraphExporter.export(g, "cytoscape")
        assert export.format == "cytoscape"

    def test_export_invalid_format(self) -> None:
        g = nx.DiGraph()
        with pytest.raises(ValueError, match="Unsupported export format"):
            GraphExporter.export(g, "gephi")

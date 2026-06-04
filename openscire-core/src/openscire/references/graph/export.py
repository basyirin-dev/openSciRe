# SPDX-License-Identifier: Apache-2.0

"""GraphExporter — serialize citation graphs for visualization (D3.js, Cytoscape)."""

import networkx as nx

from openscire.references.graph.models import GraphExport


class GraphExporter:
    @staticmethod
    def to_d3_json(graph: nx.DiGraph) -> GraphExport:
        data = nx.node_link_data(graph, edges="edges")
        return GraphExport(format="d3", data=data)

    @staticmethod
    def to_cytoscape_json(graph: nx.DiGraph) -> GraphExport:
        data = nx.cytoscape_data(graph)
        return GraphExport(format="cytoscape", data=data)

    @staticmethod
    def export(
        graph: nx.DiGraph,
        fmt: str = "d3",
    ) -> GraphExport:
        if fmt == "d3":
            return GraphExporter.to_d3_json(graph)
        if fmt == "cytoscape":
            return GraphExporter.to_cytoscape_json(graph)
        msg = f"Unsupported export format: {fmt}. Use 'd3' or 'cytoscape'."
        raise ValueError(msg)

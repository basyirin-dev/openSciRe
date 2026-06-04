# SPDX-License-Identifier: Apache-2.0

"""ClusterEngine — co-citation and bibliographic coupling clustering."""

from typing import Any

import networkx as nx
from networkx.algorithms import community

from openscire.references.graph.models import CitationCluster, ClusterReport


class ClusterEngine:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    def co_citation_clustering(
        self,
        graph: nx.DiGraph,
        min_co_citation: int = 2,
    ) -> ClusterReport:
        sim = _co_citation_similarity(graph, min_co_citation)
        return _cluster_similarity_graph(sim, graph, "co_citation")

    def bibliographic_coupling(
        self,
        graph: nx.DiGraph,
        min_coupling: int = 2,
    ) -> ClusterReport:
        sim = _bibliographic_coupling_similarity(graph, min_coupling)
        return _cluster_similarity_graph(sim, graph, "bibliographic_coupling")

    def co_citation_similarity(self, graph: nx.DiGraph, min_co_citation: int = 2) -> nx.Graph:
        return _co_citation_similarity(graph, min_co_citation)

    def bibliographic_similarity(self, graph: nx.DiGraph, min_coupling: int = 2) -> nx.Graph:
        return _bibliographic_coupling_similarity(graph, min_coupling)


def _co_citation_similarity(graph: nx.DiGraph, min_co_citation: int = 2) -> nx.Graph:
    cited_to_citers: dict[Any, set] = {}
    for u, v in graph.edges():
        if v not in cited_to_citers:
            cited_to_citers[v] = set()
        cited_to_citers[v].add(u)
    sim = nx.Graph()
    cited_papers = list(cited_to_citers.keys())
    for i in range(len(cited_papers)):
        for j in range(i + 1, len(cited_papers)):
            a = cited_papers[i]
            b = cited_papers[j]
            common = cited_to_citers[a] & cited_to_citers[b]
            if len(common) >= min_co_citation:
                sim.add_edge(a, b, weight=len(common))
    return sim


def _bibliographic_coupling_similarity(graph: nx.DiGraph, min_coupling: int = 2) -> nx.Graph:
    paper_to_refs: dict[Any, set] = {}
    for u, v in graph.edges():
        if u not in paper_to_refs:
            paper_to_refs[u] = set()
        paper_to_refs[u].add(v)
    sim = nx.Graph()
    papers = list(paper_to_refs.keys())
    for i in range(len(papers)):
        for j in range(i + 1, len(papers)):
            a = papers[i]
            b = papers[j]
            common = paper_to_refs[a] & paper_to_refs[b]
            if len(common) >= min_coupling:
                sim.add_edge(a, b, weight=len(common))
    return sim


def _cluster_similarity_graph(
    sim: nx.Graph,
    original: nx.DiGraph,
    method: str,
) -> ClusterReport:
    if sim.number_of_nodes() == 0:
        return ClusterReport(method=method)
    communities = []
    try:
        communities = list(community.greedy_modularity_communities(sim, weight="weight"))
    except (nx.NetworkXError, ZeroDivisionError):
        communities = []
    if not communities:
        communities = [set(sim.nodes())]
    clusters = []
    for cid, comm in enumerate(communities):
        sub = sim.subgraph(comm)
        cohesion = _compute_cohesion(sub)
        years = _collect_years(original, comm)
        avg_year = sum(years) / len(years) if years else None
        clusters.append(
            CitationCluster(
                cluster_id=cid,
                paper_ids=sorted(comm),
                size=len(comm),
                cohesion=round(cohesion, 4),
                avg_year=avg_year,
            )
        )
    modularity = community.modularity(sim, communities, weight="weight") if communities else 0.0
    return ClusterReport(clusters=clusters, method=method, modularity=round(modularity, 4))


def _compute_cohesion(subgraph: nx.Graph) -> float:
    n = subgraph.number_of_nodes()
    if n < 2:
        return 1.0
    total_possible = n * (n - 1) / 2
    if total_possible == 0:
        return 1.0
    return subgraph.number_of_edges() / total_possible


def _collect_years(graph: nx.Graph, nodes: set) -> list[int]:
    years = []
    for node in nodes:
        ref = graph.nodes.get(node, {}).get("ref") if hasattr(graph, "nodes") else None
        if ref is None:
            continue
        if hasattr(ref, "year") and ref.year is not None:
            years.append(ref.year)
    return years

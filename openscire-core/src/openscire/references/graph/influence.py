# SPDX-License-Identifier: Apache-2.0

"""InfluenceScorer — PageRank-based citation influence scoring.

Pure Python PageRank implementation to avoid scipy dependency.
Uses the standard power iteration method with personalization vector
handling for dangling nodes.
"""

from typing import Any

import networkx as nx

from openscire.references.graph.models import InfluenceReport, InfluenceResult


class InfluenceScorer:
    @staticmethod
    def score(
        graph: nx.DiGraph,
        alpha: float = 0.85,
        max_iter: int = 100,
        tol: float = 1e-6,
    ) -> InfluenceReport:
        pr = _pagerank(graph, alpha=alpha, max_iter=max_iter, tol=tol)
        sorted_results = sorted(pr.items(), key=lambda x: x[1], reverse=True)
        results = [
            InfluenceResult(paper_id=pid, score=s, rank=i + 1)
            for i, (pid, s) in enumerate(sorted_results)
        ]
        return InfluenceReport(
            results=results,
            convergence=tol,
            iterations=max_iter,
            damping_factor=alpha,
        )

    @staticmethod
    def score_ego(
        graph: nx.DiGraph,
        node_id: str,
        depth: int = 2,
        alpha: float = 0.85,
    ) -> InfluenceReport:
        if node_id not in graph:
            return InfluenceReport(damping_factor=alpha)
        neighbors = set(nx.ego_graph(graph, node_id, radius=depth, undirected=True))
        subgraph = graph.subgraph(neighbors).copy()
        return InfluenceScorer.score(subgraph, alpha=alpha)


def _pagerank(
    graph: nx.DiGraph,
    alpha: float = 0.85,
    max_iter: int = 100,
    tol: float = 1e-6,
) -> dict[Any, float]:
    n_nodes = graph.number_of_nodes()
    if n_nodes == 0:
        return {}

    nodes = list(graph.nodes())
    dangling = [n for n in nodes if graph.out_degree(n) == 0]
    pr: dict[Any, float] = dict.fromkeys(nodes, 1.0 / n_nodes)

    for _ in range(max_iter):
        prev = pr.copy()
        leak = sum(prev[n] for n in dangling) * alpha / n_nodes if dangling else 0.0
        uniform = (1.0 - alpha) / n_nodes

        for node in nodes:
            rank = leak + uniform
            for pred in graph.predecessors(node):
                rank += alpha * prev[pred] / graph.out_degree(pred)
            pr[node] = rank

        diff = sum(abs(pr[n] - prev[n]) for n in nodes)
        if diff < tol:
            break

    return pr

# SPDX-License-Identifier: Apache-2.0

"""CitationGraphBuilder — constructs citation graphs from ReferenceItems."""

import re

import networkx as nx

from openscire.references.models import CitationGraphEntry, ReferenceItem

_ID_FROM_URL = re.compile(r"/([A-Za-z0-9]+)/?$")


def _extract_id_from_url(url: str) -> str | None:
    m = _ID_FROM_URL.search(url)
    return m.group(1) if m else None


class CitationGraphBuilder:
    @staticmethod
    def build(refs: list[ReferenceItem]) -> nx.DiGraph:
        g = nx.DiGraph()
        for ref in refs:
            _add_node(g, ref)
        for ref in refs:
            _add_openalex_edges(g, ref)
        return g

    @staticmethod
    def build_from_entries(
        entries: list[CitationGraphEntry],
        ref_lookup: dict[str, ReferenceItem],
    ) -> nx.DiGraph:
        g = nx.DiGraph()
        for entry in entries:
            if entry.citing_paper:
                citing_id = entry.citing_paper.id
                _add_node(g, entry.citing_paper)
                if citing_id in ref_lookup:
                    _add_node(g, ref_lookup[citing_id])
            if entry.cited_paper:
                cited_id = entry.cited_paper.id
                _add_node(g, entry.cited_paper)
                if cited_id in ref_lookup:
                    _add_node(g, ref_lookup[cited_id])
            if entry.citing_paper and entry.cited_paper:
                g.add_edge(
                    entry.citing_paper.id,
                    entry.cited_paper.id,
                    contexts=entry.contexts,
                    is_influential=entry.is_influential,
                )
        return g


def _add_node(g: nx.DiGraph, ref: ReferenceItem) -> None:
    g.add_node(ref.id, ref=ref)


def _add_openalex_edges(g: nx.DiGraph, ref: ReferenceItem) -> None:
    ref_id = ref.id
    for url in ref.extra.get("referenced_works", []):
        target = _extract_id_from_url(url)
        if target and target in g.nodes:
            g.add_edge(ref_id, target, source="openalex_referenced")
    for url in ref.extra.get("related_works", []):
        target = _extract_id_from_url(url)
        if target and target in g.nodes:
            g.add_edge(ref_id, target, source="openalex_related")

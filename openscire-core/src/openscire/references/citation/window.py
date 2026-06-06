from __future__ import annotations

import math
import re
from typing import Any

from openscire.references.chunking.models import DocumentChunk
from openscire.references.citation.models import (
    CitationContext,
    CitationContextReport,
    CitationDensity,
    CitationNeighborhood,
    ContradictionSignal,
    TemporalWeight,
)
from openscire.references.models import ReferenceItem

_CITATION_PATTERN = re.compile(
    r"\[[\d,\s\-–—]+\]"
    r"|\([A-Za-z\u00C0-\u024F]+(?:\s+et\s+al\.?)?"
    r"(?:,\s*[A-Za-z\u00C0-\u024F]+)?(?:&\s*[A-Za-z\u00C0-\u024F]+)?,\s*[\d]{4}[a-z]?\)"
)

_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z"\'({[]|\d+\s)')


class CitationContextWindow:
    def __init__(
        self,
        ref_lookup: dict[str, ReferenceItem],
        graph_builder: Any = None,  # noqa: ANN401
        influence_scorer: Any = None,  # noqa: ANN401
        retraction_monitor: Any = None,  # noqa: ANN401
        current_year: int = 2026,
        decay_rate: float = 0.1,
    ) -> None:
        self._ref_lookup = ref_lookup
        self._graph_builder = graph_builder
        self._influence_scorer = influence_scorer
        self._retraction_monitor = retraction_monitor
        self._current_year = current_year
        self._decay_rate = decay_rate

    def build(
        self,
        chunks: list[DocumentChunk],
        query: str = "",
    ) -> CitationContextReport:
        if not chunks:
            return CitationContextReport(query=query)

        citations = self._extract_citations(chunks)
        chunk_ids = [c.id for c in chunks]

        neighborhood = self._build_neighborhood(citations)
        density_scores = self._compute_density(citations)
        contradictions = self._detect_contradictions(citations)
        temporal_weights = self._compute_temporal_weights(citations)

        return CitationContextReport(
            query=query,
            source_chunk_ids=chunk_ids,
            citations=list(citations.values()),
            neighborhood=neighborhood,
            density_scores=density_scores,
            contradictions=contradictions,
            temporal_weights=temporal_weights,
        )

    def _extract_citations(self, chunks: list[DocumentChunk]) -> dict[str, CitationContext]:
        result: dict[str, CitationContext] = {}
        seen_texts: set[str] = set()
        for chunk in chunks:
            for citation_text in chunk.metadata.citation_list:
                if citation_text in seen_texts:
                    continue
                seen_texts.add(citation_text)
                ctx = CitationContext(
                    citation_text=citation_text,
                    chunk_id=chunk.id,
                    section=chunk.metadata.section,
                    sentence=self._extract_sentence(chunk.text, citation_text),
                )
                if citation_text in self._ref_lookup:
                    ref = self._ref_lookup[citation_text]
                    ctx.reference_id = ref.id
                    ctx.title = ref.title
                    ctx.year = ref.year
                    if ref.authors:
                        ctx.authors = (
                            ref.authors[0].full
                            if ref.authors[0].full
                            else f"{ref.authors[0].last}, {ref.authors[0].first}"
                        )
                    ctx.is_retracted = bool(ref.retraction_status)
                result[citation_text] = ctx
        return result

    def _extract_sentence(self, text: str, citation_text: str) -> str:
        sentences = _SENTENCE_SPLIT.split(text)
        for sentence in sentences:
            if citation_text in sentence:
                return sentence.strip()
        return ""

    def _get_resolved_refs(
        self,
        resolved: dict[str, CitationContext],
    ) -> list[ReferenceItem]:
        refs: list[ReferenceItem] = []
        for citation_text, ctx in resolved.items():
            if ctx.reference_id and citation_text in self._ref_lookup:
                refs.append(self._ref_lookup[citation_text])
        return refs

    def _build_neighborhood(
        self,
        resolved: dict[str, CitationContext],
    ) -> list[CitationNeighborhood]:
        if self._graph_builder is None:
            return []

        refs = self._get_resolved_refs(resolved)
        if not refs:
            return []

        try:
            graph = self._graph_builder.build(refs)
        except Exception:
            return []

        seed_ids = {r.id for r in refs}
        neighborhood: list[CitationNeighborhood] = []

        for seed_id in seed_ids:
            if seed_id not in graph:
                continue
            for pred in graph.predecessors(seed_id):
                node_data = graph.nodes.get(pred, {})
                ref_obj: ReferenceItem | None = node_data.get("ref")
                neighborhood.append(
                    CitationNeighborhood(
                        paper_id=str(pred),
                        title=ref_obj.title if ref_obj else "",
                        relationship="cites",
                        distance=1,
                        year=ref_obj.year if ref_obj else None,
                    )
                )
            for succ in graph.successors(seed_id):
                node_data = graph.nodes.get(succ, {})
                ref_obj = node_data.get("ref")
                neighborhood.append(
                    CitationNeighborhood(
                        paper_id=str(succ),
                        title=ref_obj.title if ref_obj else "",
                        relationship="cited_by",
                        distance=1,
                        year=ref_obj.year if ref_obj else None,
                    )
                )

        return neighborhood

    def _compute_density(
        self,
        resolved: dict[str, CitationContext],
    ) -> list[CitationDensity]:
        refs = self._get_resolved_refs(resolved)
        if not refs:
            return []

        pagerank_scores: dict[str, float] = {}
        if self._graph_builder is not None and self._influence_scorer is not None:
            try:
                graph = self._graph_builder.build(refs)
                if graph.number_of_nodes() > 0:
                    report = self._influence_scorer.score(graph)
                    pagerank_scores = {r.paper_id: r.score for r in report.results}
            except Exception:
                pass

        citation_counts = [ref.extra.get("citation_count", 0) for ref in refs]
        if citation_counts:
            mean = sum(citation_counts) / len(citation_counts)
            std = (
                math.sqrt(sum((c - mean) ** 2 for c in citation_counts) / len(citation_counts))
                if len(citation_counts) > 1
                else 0.0
            )
        else:
            mean = 0.0
            std = 0.0

        density_scores: list[CitationDensity] = []
        for ref in refs:
            cc = ref.extra.get("citation_count", 0)
            z = (cc - mean) / std if std > 0 else 0.0
            if z > 1.5:
                label = "high"
            elif z < -0.5:
                label = "low"
            else:
                label = "medium"
            density_scores.append(
                CitationDensity(
                    reference_id=ref.id,
                    citation_count=cc,
                    normalized_citation_count=round(z, 4),
                    pagerank_score=pagerank_scores.get(ref.id, 0.0),
                    density_label=label,
                )
            )

        return density_scores

    def _detect_contradictions(
        self,
        resolved: dict[str, CitationContext],
    ) -> list[ContradictionSignal]:
        if self._retraction_monitor is None:
            return []

        signals: list[ContradictionSignal] = []
        for citation_text, ctx in resolved.items():
            if not ctx.reference_id:
                continue
            ref = self._ref_lookup.get(citation_text)
            if ref is None:
                continue
            doi = ref.doi
            if not doi:
                continue
            try:
                import asyncio

                status, _records = asyncio.run(self._retraction_monitor.check_paper(doi))
                if str(status) == "retracted":
                    signals.append(
                        ContradictionSignal(
                            reference_id=ref.id,
                            signal_type="retracted",
                            confidence=1.0,
                            description=f"Paper '{ref.title}' has been retracted",
                        )
                    )
                elif str(status) == "corrected":
                    signals.append(
                        ContradictionSignal(
                            reference_id=ref.id,
                            signal_type="corrected",
                            confidence=0.7,
                            description=f"Paper '{ref.title}' has been corrected",
                        )
                    )
                elif str(status) == "expression_of_concern":
                    signals.append(
                        ContradictionSignal(
                            reference_id=ref.id,
                            signal_type="expression_of_concern",
                            confidence=0.8,
                            description=(
                                f"An expression of concern has been raised for '{ref.title}'"
                            ),
                        )
                    )
            except Exception:
                continue

        return signals

    def _compute_temporal_weights(
        self,
        resolved: dict[str, CitationContext],
    ) -> list[TemporalWeight]:
        weights: list[TemporalWeight] = []
        for citation_text, ctx in resolved.items():
            if not ctx.reference_id:
                continue
            ref = self._ref_lookup.get(citation_text)
            year = ref.year if ref else ctx.year
            if year is None:
                weight = 0.0
            else:
                age = self._current_year - year
                weight = math.exp(-self._decay_rate * max(age, 0))
            weights.append(
                TemporalWeight(
                    reference_id=ctx.reference_id,
                    year=year,
                    weight=weight,
                    decay_rate=self._decay_rate,
                )
            )
        return weights

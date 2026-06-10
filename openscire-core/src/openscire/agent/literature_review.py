# SPDX-License-Identifier: Apache-2.0

"""Literature Review Agent — structured evidence gathering via multi-source search."""

from __future__ import annotations

import logging
from typing import Any

from openscire.agent.bus import AgentBus
from openscire.agent.models import (
    AgentMessage,
    MessageType,
    QueryPayload,
    ResponsePayload,
    ResultPayload,
    TaskPayload,
)

logger = logging.getLogger(__name__)


class LiteratureReviewAgent:
    """Structured evidence-gathering agent.

    Decomposes a research question into sub-queries, dispatches to multiple
    literature sources, deduplicates, synthesizes findings, identifies gaps
    and contradictions, and assesses evidence quality.

    LLM-optional: when no ModelProvider is available, uses heuristic
    decomposition and keyword-based contradiction detection.
    """

    def __init__(
        self,
        agent_id: str = "literature_review",
        bus: AgentBus | None = None,
        provenance_tracker: Any = None,  # noqa: ANN401
        openalex_client: Any = None,  # noqa: ANN401
        pubmed_bridge: Any = None,  # noqa: ANN401
        dedup_engine: Any = None,  # noqa: ANN401
        gap_analyzer: Any = None,  # noqa: ANN401
        quality_scorer: Any = None,  # noqa: ANN401
        retraction_monitor: Any = None,  # noqa: ANN401
        config: dict[str, Any] | None = None,
    ) -> None:
        self._agent_id = agent_id
        self._bus = bus or AgentBus.get_bus("literature_review")
        self._provenance = provenance_tracker
        self._openalex = openalex_client
        self._pubmed = pubmed_bridge
        self._dedup = dedup_engine
        self._gap_analyzer = gap_analyzer
        self._quality_scorer = quality_scorer
        self._retraction_monitor = retraction_monitor
        self._config = config or {}

        self._sub = self._bus.subscribe(
            agent_id,
            {MessageType.task, MessageType.query},
            self.handle_message,
        )

    # ── Message handling ──────────────────────────────────────────────

    async def handle_message(self, message: AgentMessage) -> None:
        if message.message_type == MessageType.task:
            await self._handle_task(message)
        elif message.message_type == MessageType.query:
            await self._handle_query(message)

    async def _handle_task(self, message: AgentMessage) -> None:
        try:
            payload = TaskPayload.model_validate(message.payload)
            params = payload.parameters or {}
            question = payload.description or params.get("question", "")
            result = await self.execute_review(
                question=question,
                parameters=params,
            )
            self._bus.publish(
                AgentMessage(
                    sender=self._agent_id,
                    recipient=message.sender,
                    message_type=MessageType.result,
                    payload=ResultPayload(
                        task_description=payload.description,
                        output=result,
                        success=True,
                    ).model_dump(),
                    thread_id=message.thread_id,
                    provenance_parent_id=message.message_id,
                )
            )
        except Exception as exc:
            logger.exception("Literature review task failed")
            desc = ""
            try:
                desc = TaskPayload.model_validate(message.payload).description
            except Exception:  # noqa: BLE001
                desc = "unknown"
            self._bus.publish(
                AgentMessage(
                    sender=self._agent_id,
                    recipient=message.sender or "supervisor",
                    message_type=MessageType.result,
                    payload=ResultPayload(
                        task_description=desc,
                        output={},
                        success=False,
                        error=str(exc),
                    ).model_dump(),
                    thread_id=message.thread_id,
                    provenance_parent_id=message.message_id,
                )
            )

    async def _handle_query(self, message: AgentMessage) -> None:
        payload = QueryPayload.model_validate(message.payload)
        self._bus.publish(
            AgentMessage(
                sender=self._agent_id,
                recipient=message.sender,
                message_type=MessageType.response,
                payload=ResponsePayload(
                    content=(
                        f"LiteratureReviewAgent received query: {payload.question}. "
                        "Deep querying over prior results is not yet implemented."
                    ),
                    confidence=0.0,
                    citations=[],
                ).model_dump(),
                thread_id=message.thread_id,
            )
        )

    # ── Review pipeline ───────────────────────────────────────────────

    async def execute_review(
        self,
        question: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run the full literature review pipeline."""
        params = parameters or {}
        question = question.strip()
        if not question:
            return {"conclusion": "", "evidence": [], "confidence": 0.0}

        sub_queries = self._decompose_query(question)

        all_items: list[Any] = []
        openalex_items = await self._search_openalex(sub_queries, params)
        all_items.extend(openalex_items)
        pubmed_items = await self._search_pubmed(sub_queries, params)
        all_items.extend(pubmed_items)

        unique_items = self._deduplicate(all_items)

        quality_scores = self._assess_quality(unique_items)

        synthesis = self._synthesize(question, unique_items, quality_scores)

        gap_report = self._identify_gaps(question, unique_items)

        contradictions = self._detect_contradictions(unique_items)

        retraction_warnings = await self._check_retractions(unique_items)

        top_evidence = self._rank_evidence(unique_items, quality_scores, 10)

        return {
            "conclusion": synthesis.get("conclusion", ""),
            "evidence": top_evidence,
            "confidence": synthesis.get("confidence", 0.5),
            "sub_queries_used": sub_queries,
            "total_sources_found": len(all_items),
            "unique_sources": len(unique_items),
            "gaps": gap_report,
            "contradictions": contradictions,
            "retraction_warnings": retraction_warnings,
            "n_quality_scored": len(quality_scores),
        }

    # ── Pipeline steps (each overridable in tests) ────────────────────

    def _decompose_query(self, question: str) -> list[str]:
        """Break a research question into search sub-queries.

        LLM-optional heuristic: split on 'and', 'vs', 'versus' at the
        clause level, or return the full question as a single query.
        """
        import re

        question_lower = question.lower()
        delimiters = [r"\bvs\.?\b", r"\bversus\b", r"\band\b"]
        for delim in delimiters:
            parts = re.split(delim, question_lower)
            if len(parts) > 1:
                return [p.strip().strip("?.") for p in parts if p.strip()]
        return [question]

    async def _search_openalex(
        self,
        sub_queries: list[str],
        params: dict[str, Any],
    ) -> list[Any]:
        if self._openalex is None:
            return []
        results: list[Any] = []
        for q in sub_queries:
            try:
                search_result = await self._openalex.search_works(
                    query=q,
                    per_page=min(params.get("max_results", 50), 200),
                )
                for wid in search_result.work_ids:
                    if hasattr(self._openalex, "fetch_work"):
                        item = await self._openalex.fetch_work(wid)
                        if item is not None:
                            results.append(item)
            except Exception:  # noqa: BLE001
                logger.warning("OpenAlex search failed for query: %s", q)
        return results

    async def _search_pubmed(
        self,
        sub_queries: list[str],
        params: dict[str, Any],  # noqa: ARG002
    ) -> list[Any]:
        if self._pubmed is None:
            return []
        results: list[Any] = []
        for q in sub_queries:
            try:
                items = await self._pubmed.sync()
                results.extend(items)
            except Exception:  # noqa: BLE001
                logger.warning("PubMed search failed for query: %s", q)
        return results

    def _deduplicate(self, items: list[Any]) -> list[Any]:
        if self._dedup is None or not items:
            return items
        deduped = self._dedup.dedup(items)
        return [r.item for r in deduped if r.duplicate_of is None]

    def _assess_quality(self, items: list[Any]) -> list[Any]:
        if self._quality_scorer is None or not items:
            return []
        scores: list[Any] = []
        for item in items:
            try:
                score = self._quality_scorer.score(item)
                scores.append(score)
            except Exception:  # noqa: BLE001
                continue
        return scores

    def _synthesize(
        self,
        question: str,
        items: list[Any],
        scores: list[Any],
    ) -> dict[str, Any]:
        score_map: dict[str, float] = {}
        for s in scores:
            sid = getattr(s, "source_id", "")
            if sid:
                score_map[sid] = getattr(s, "overall_score", 0.0)

        n = len(items)
        if n == 0:
            return {"conclusion": "No literature found.", "confidence": 0.0}

        avg_score = sum(score_map.values()) / max(len(score_map), 1)
        confidence = min(0.5 + avg_score * 0.4, 0.95)
        titles = []
        for item in items:
            t = getattr(item, "title", "") or ""
            if t:
                titles.append(t)

        conclusion = (
            f"Reviewed {n} sources on '{question}'. "
            f"Average quality score: {avg_score:.2f}. "
            f"Key themes: {'; '.join(titles[:5])}."
        )
        return {"conclusion": conclusion, "confidence": round(confidence, 4)}

    def _identify_gaps(
        self,
        question: str,
        items: list[Any],
    ) -> dict[str, Any]:
        if self._gap_analyzer is None or not items:
            return {}
        try:
            report = self._gap_analyzer.analyze(topic=question, references=items)
            return report.model_dump() if hasattr(report, "model_dump") else {}
        except Exception:  # noqa: BLE001
            return {}

    def _detect_contradictions(self, items: list[Any]) -> list[dict[str, Any]]:
        contradictions: list[dict[str, Any]] = []
        abstracts = []
        for item in items:
            ab = getattr(item, "abstract", "") or ""
            ti = getattr(item, "title", "") or ""
            abstracts.append((getattr(item, "id", ""), ti, ab))

        for i in range(len(abstracts)):
            for j in range(i + 1, len(abstracts)):
                id_a, title_a, text_a = abstracts[i]
                id_b, title_b, text_b = abstracts[j]
                combined = f"{title_a} {text_a}"
                if self._is_text_contradictory(combined, title_b, text_b):
                    contradictions.append(
                        {
                            "source_a": id_a,
                            "source_b": id_b,
                            "topic": title_a or title_b or "",
                        }
                    )
        return contradictions

    @staticmethod
    def _is_text_contradictory(
        text_a: str,
        title_b: str,
        abstract_b: str,
    ) -> bool:
        negation_markers = ["not ", "no ", "does not", "cannot", "unlikely", "contradict"]
        b_combined = f"{title_b} {abstract_b}".lower()
        a_lower = text_a.lower()
        has_negation_b = any(m in b_combined for m in negation_markers)
        has_negation_a = any(m in a_lower for m in negation_markers)
        if has_negation_b == has_negation_a:
            return False

        noun_a = _extract_noun_phrase(a_lower)
        noun_b = _extract_noun_phrase(b_combined)
        return _words_overlap(noun_a, noun_b, min_overlap=1)

    async def _check_retractions(
        self,
        items: list[Any],
    ) -> list[dict[str, Any]]:
        if self._retraction_monitor is None or not items:
            return []
        warnings: list[dict[str, Any]] = []
        for item in items:
            doi = getattr(item, "doi", "") or ""
            if not doi:
                continue
            try:
                status, records = await self._retraction_monitor.check_paper(doi)
                if str(status) != "unchecked":
                    warnings.append({"doi": doi, "status": str(status), "n_records": len(records)})
            except Exception:  # noqa: BLE001
                continue
        return warnings

    def _rank_evidence(
        self,
        items: list[Any],
        scores: list[Any],
        top_n: int = 10,
    ) -> list[dict[str, Any]]:
        score_map: dict[str, float] = {}
        for s in scores:
            sid = getattr(s, "source_id", "")
            if sid:
                score_map[sid] = getattr(s, "overall_score", 0.0)

        scored_items: list[tuple[float, Any]] = []
        for item in items:
            sid = getattr(item, "id", "")
            sc = score_map.get(sid, 0.0)
            scored_items.append((sc, item))
        scored_items.sort(key=lambda x: x[0], reverse=True)

        result: list[dict[str, Any]] = []
        for sc, item in scored_items[:top_n]:
            sid = getattr(item, "id", "")
            title = getattr(item, "title", "") or ""
            doi = getattr(item, "doi", "") or ""
            result.append(
                {
                    "id": sid,
                    "title": title,
                    "doi": doi,
                    "quality_score": sc,
                }
            )
        return result


def _words_overlap(phrase_a: str, phrase_b: str, min_overlap: int = 1) -> bool:
    stop_words = {
        "the",
        "a",
        "an",
        "in",
        "of",
        "to",
        "for",
        "with",
        "on",
        "at",
        "by",
        "from",
        "and",
        "or",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "can",
    }
    words_a = {w for w in phrase_a.split() if w not in stop_words}
    words_b = {w for w in phrase_b.split() if w not in stop_words}
    return len(words_a & words_b) >= min_overlap


def _extract_noun_phrase(text: str) -> str:
    first_sentence = text.split(".")[0]
    words = first_sentence.split()
    return " ".join(words[:5]).lower()

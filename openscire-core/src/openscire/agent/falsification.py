# SPDX-License-Identifier: Apache-2.0

"""Falsification Agent — Popperian adversarial hypothesis testing.

Actively searches for evidence that contradicts a given hypothesis,
identifies confounds, generates counter-examples and alternative
explanations, and critiques methodology.

Design constraint: the FalsificationAgent must NOT receive the
HypothesisGenerator's confidence score (prevents anchoring bias).
"""

from __future__ import annotations

import logging
import re
from enum import StrEnum, auto
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


class ConfoundCategory(StrEnum):
    """Category of a potential experimental confound."""

    confounding = auto()
    mediating = auto()
    moderating = auto()
    selection = auto()
    measurement = auto()


class FalsificationAgent:
    """Adversarial agent that actively seeks to falsify hypotheses.

    Given a hypothesis, this agent:
    - Searches for contradicting evidence (Popperian falsification)
    - Generates counter-examples (boundary scenarios, edge cases)
    - Identifies potential confounds (uncontrolled variables)
    - Proposes alternative explanations (competing hypotheses)
    - Critiques methodology (evidence quality, testability, monocultures)

    LLM-optional: all pipeline steps use heuristics when no injected
    components are available.
    """

    def __init__(
        self,
        agent_id: str = "falsification",
        bus: AgentBus | None = None,
        provenance_tracker: Any = None,  # noqa: ANN401
        openalex_client: Any = None,  # noqa: ANN401
        pubmed_bridge: Any = None,  # noqa: ANN401
        adversarial_retriever: Any = None,  # noqa: ANN401
        assumption_miner: Any = None,  # noqa: ANN401
        quality_scorer: Any = None,  # noqa: ANN401
        negative_result_registry: Any = None,  # noqa: ANN401
        config: dict[str, Any] | None = None,
    ) -> None:
        self._agent_id = agent_id
        self._bus = bus or AgentBus.get_bus("falsification")
        self._provenance = provenance_tracker
        self._openalex = openalex_client
        self._pubmed = pubmed_bridge
        self._adversarial_retriever = adversarial_retriever
        self._assumption_miner = assumption_miner
        self._quality_scorer = quality_scorer
        self._neg_registry = negative_result_registry
        self._config = config or {}
        self._max_alternatives = self._config.get("max_alternatives", 5)
        self._max_counter_examples = self._config.get("max_counter_examples", 5)

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
            params = dict(payload.parameters or {})
            params.pop("confidence", None)

            hypothesis = params.get("hypothesis", "") or payload.description
            result = await self.execute_falsification(
                hypothesis=hypothesis,
                parameters=params,
            )

            if self._neg_registry is not None:
                try:
                    from openscire.negative_results.integration import (
                        submit_from_falsification,
                    )

                    submit_from_falsification(
                        store=self._neg_registry,
                        falsification_report=result,
                        agent_id=self._agent_id,
                    )
                except Exception:
                    logger.exception(
                        "Failed to auto-register negative result",
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
            logger.exception("Falsification task failed")
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
                        f"FalsificationAgent received query: {payload.question}. "
                        "Direct query answering is not yet implemented."
                    ),
                    confidence=0.0,
                    citations=[],
                ).model_dump(),
                thread_id=message.thread_id,
            )
        )

    # ── Falsification pipeline ────────────────────────────────────────

    async def execute_falsification(
        self,
        hypothesis: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run the full falsification pipeline.

        Returns a structured dict with all falsification findings.
        Raises ValueError if hypothesis is empty.
        """
        params = parameters or {}
        hypothesis = hypothesis.strip()
        if not hypothesis:
            raise ValueError("Cannot run falsification on empty hypothesis.")

        contradiction_evidence = await self._search_for_falsification(
            hypothesis,
            params,
        )
        counter_examples = self._generate_counter_examples(hypothesis, params)
        confounds = await self._identify_confounds(hypothesis, params)
        alternatives = self._generate_alternatives(hypothesis, params)
        critique = self._critique_methodology(hypothesis, contradiction_evidence, params)

        return self._build_report(
            hypothesis=hypothesis,
            contradiction_evidence=contradiction_evidence,
            counter_examples=counter_examples,
            confounds=confounds,
            alternatives=alternatives,
            critique=critique,
        )

    # ── Pipeline step 1: Popperian falsification search (6.4.1) ───────

    async def _search_for_falsification(
        self,
        hypothesis: str,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Search for evidence that contradicts the hypothesis.

        Uses injected bridges and adversarial retriever if available,
        otherwise returns empty list (graceful degradation).
        """
        claims = self._extract_claims(hypothesis)
        results: list[dict[str, Any]] = []

        if self._adversarial_retriever is not None:
            try:
                contradictory = await self._adversarial_retriever.find_contradictory_sources(
                    claims=claims,
                    max_per_claim=params.get("max_per_claim", 3),
                )
                for src in contradictory:
                    results.append(
                        {
                            "source_id": getattr(src, "source", {}).get("id", ""),
                            "title": getattr(src, "source", {}).get("title", ""),
                            "contradicts_claim": getattr(src, "claim", ""),
                            "evidence_type": getattr(src, "contradiction_type", ""),
                            "retrieved_via": "adversarial_retriever",
                        }
                    )
            except Exception:  # noqa: BLE001
                logger.warning("Adversarial retriever failed for hypothesis")

        seen_ids = {r["source_id"] for r in results if r["source_id"]}

        for claim in claims:
            negated = f"contrary to {claim}"
            bridge_results = await self._search_bridges(negated, params)
            for br in bridge_results:
                sid = br.get("source_id", "")
                if sid and sid not in seen_ids:
                    seen_ids.add(sid)
                    results.append(
                        {
                            "source_id": sid,
                            "title": br.get("title", ""),
                            "contradicts_claim": claim,
                            "evidence_type": "negation_search",
                            "retrieved_via": "bridge",
                        }
                    )

        return results

    def _extract_claims(self, hypothesis: str) -> list[str]:
        """Extract individual testable claims from a hypothesis string.

        Splits on causal connectors and conjunction markers.
        """
        causal_patterns = [
            r"(?:we hypothesize that|we propose that|our hypothesis is that)\s+(.+?)(?:\.|$)",
            (
                r"(.+?)\s+(?:causes|leads to|results in|increases|decreases|"
                r"correlates with|is associated with)\s+(.+?)(?:\.|$)"
            ),
        ]
        claims: list[str] = []
        for pattern in causal_patterns:
            matches = re.findall(pattern, hypothesis, re.IGNORECASE)
            for m in matches:
                if isinstance(m, tuple):
                    claims.extend(m)
                else:
                    claims.append(m)

        if not claims:
            claims.append(hypothesis)

        seen: set[str] = set()
        deduped: list[str] = []
        for c in claims:
            cleaned = c.strip().strip(".,;:!?")
            if cleaned and cleaned.lower() not in seen:
                seen.add(cleaned.lower())
                deduped.append(cleaned)

        return deduped[:10]

    async def _search_bridges(
        self,
        query: str,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Search OpenAlex and PubMed bridges for a given query."""
        results: list[dict[str, Any]] = []

        if self._openalex is not None:
            try:
                search_result = await self._openalex.search_works(
                    query=query,
                    per_page=min(params.get("max_results", 20), 100),
                )
                for wid in search_result.work_ids[:10]:
                    if hasattr(self._openalex, "fetch_work"):
                        item = await self._openalex.fetch_work(wid)
                        if item is not None:
                            results.append(
                                {
                                    "source_id": getattr(item, "id", ""),
                                    "title": getattr(item, "title", ""),
                                    "doi": getattr(item, "doi", ""),
                                    "abstract": getattr(item, "abstract", ""),
                                }
                            )
            except Exception:  # noqa: BLE001
                logger.warning("OpenAlex search failed for query: %s", query[:50])

        if self._pubmed is not None:
            try:
                items = await self._pubmed.sync()
                for item in (items or [])[:10]:
                    results.append(
                        {
                            "source_id": getattr(item, "id", ""),
                            "title": getattr(item, "title", ""),
                            "doi": getattr(item, "doi", ""),
                            "abstract": getattr(item, "abstract", ""),
                        }
                    )
            except Exception:  # noqa: BLE001
                logger.warning("PubMed search failed for query: %s", query[:50])

        return results

    # ── Pipeline step 2: Counter-example generation (6.4.2) ───────────

    def _generate_counter_examples(
        self,
        hypothesis: str,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Generate boundary-value scenarios where the hypothesis would fail.

        Extracts key variables from the hypothesis and constructs edge-case
        scenarios that would contradict the predicted relationship.
        """
        variables = self._extract_variables(hypothesis)
        counter_examples: list[dict[str, Any]] = []
        max_examples = params.get("max_counter_examples", self._max_counter_examples)

        templates = [
            ("value_boundary", "If {var} is zero, the predicted effect disappears"),
            ("value_boundary", "If {var} approaches infinity, the predicted effect reverses"),
            ("temporal", "If the effect of {var} has a significant time delay"),
            (
                "population",
                "If the observed relationship only holds for a specific "
                "subgroup, not the general population",
            ),
            ("measurement", "If the measurement of {var} is systematically biased"),
            (
                "interaction",
                "If {var} interacts with an uncontrolled variable in the opposite direction",
            ),
        ]

        if not variables:
            templates = templates[:3]
            for i in range(min(len(templates), max_examples)):
                scenario, desc = templates[i][0], templates[i][1]
                counter_examples.append(
                    {
                        "scenario": desc,
                        "variable_tested": "hypothesis",
                        "expected_outcome_if_valid": "observed effect does not generalize",
                        "template_used": scenario,
                    }
                )
        else:
            idx = 0
            for var in variables:
                for template_type, template in templates:
                    if idx >= max_examples:
                        break
                    scenario = template.format(var=var)
                    counter_examples.append(
                        {
                            "scenario": scenario,
                            "variable_tested": var,
                            "expected_outcome_if_valid": "falsifies the hypothesized relationship",
                            "template_used": template_type,
                        }
                    )
                    idx += 1
                if idx >= max_examples:
                    break

        return counter_examples[:max_examples]

    def _extract_variables(self, hypothesis: str) -> list[str]:
        """Extract candidate variables from a hypothesis using heuristics.

        Looks for nouns adjacent to causal verbs and comparison structures.
        """
        variables: list[str] = []

        matches = re.findall(
            r"(?:causes?|leads?\s+to|results?\s+in|increases?|decreases?|"
            r"correlates?\s+with|is\s+associated\s+with)\s+(\w+(?:\s+\w+)?)",
            hypothesis,
            re.IGNORECASE,
        )
        for m in matches:
            if m.lower() not in ("the", "a", "an", "this", "that", "these", "those"):
                variables.append(m.strip())

        matches = re.findall(
            r"(\w+(?:\s+\w+)?)\s+(?:causes?|leads?\s+to|results?\s+in|increases?|decreases?|"
            r"correlates?\s+with|is\s+associated\s+with)",
            hypothesis,
            re.IGNORECASE,
        )
        for m in matches:
            if m.lower() not in ("the", "a", "an", "this", "that", "these", "those"):
                variables.append(m.strip())

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
            "this",
            "that",
            "these",
            "those",
            "it",
            "its",
            "we",
            "our",
        }

        deduped: list[str] = []
        seen: set[str] = set()
        for v in variables:
            cleaned = v.strip().lower()
            words = cleaned.split()
            filtered = [w for w in words if w not in stop_words]
            key = " ".join(filtered) if filtered else cleaned
            if key and key not in seen:
                seen.add(key)
                deduped.append(v.strip())

        return deduped[:8]

    # ── Pipeline step 3: Confound identification (6.4.3) ──────────────

    async def _identify_confounds(
        self,
        hypothesis: str,
        _params: dict[str, Any],  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        """Identify potential experimental confounds.

        If AssumptionMiner is available, delegates to it.
        Otherwise uses heuristic regex to extract implicit assumptions
        and categorize them as confounds.
        """
        if self._assumption_miner is not None:
            try:
                assumptions = await self._assumption_miner.extract(hypothesis)
                confounds: list[dict[str, Any]] = []
                for a in assumptions:
                    text = getattr(a, "assumption_text", "") or str(a)
                    confounds.append(
                        {
                            "variable": text,
                            "category": ConfoundCategory.confounding,
                            "description": (
                                "Implicit assumption that may introduce confound. "
                                "Verify with controlled experiment."
                            ),
                            "impact_on_hypothesis": "Uncontrolled variable may bias results",
                        }
                    )
                return confounds
            except Exception:  # noqa: BLE001
                logger.warning("AssumptionMiner extraction failed")

        return self._heuristic_confounds(hypothesis)

    def _heuristic_confounds(self, hypothesis: str) -> list[dict[str, Any]]:
        """Extract confounds using regex patterns for causal language."""
        confounds: list[dict[str, Any]] = []

        # Patterns for universal claims (potential selection bias)
        universal_matches = re.findall(
            r"(?:all|every|always|never|none)\s+(\w+(?:\s+\w+)?)",
            hypothesis,
            re.IGNORECASE,
        )
        for m in universal_matches:
            confounds.append(
                {
                    "variable": m.strip(),
                    "category": ConfoundCategory.selection,
                    "description": (
                        f"Universal claim about '{m.strip()}' assumes "
                        "the sample represents the entire population"
                    ),
                    "impact_on_hypothesis": (
                        "Selection bias: results may not generalize beyond the observed sample"
                    ),
                }
            )

        # Patterns for causal connectors (identify assumed mechanisms)
        causal_matches = re.findall(
            r"(?:due to|because of|as a result of|caused by|driven by)\s+(\w+(?:\s+\w+)?)",
            hypothesis,
            re.IGNORECASE,
        )
        for m in causal_matches:
            confounds.append(
                {
                    "variable": m.strip(),
                    "category": ConfoundCategory.mediating,
                    "description": (
                        f"Assumed causal mechanism via '{m.strip()}' may not be the actual pathway"
                    ),
                    "impact_on_hypothesis": (
                        "Mediating variable may confound the direct cause-effect relationship"
                    ),
                }
            )

        # Patterns for certainty language (potential measurement bias)
        certainty_matches = re.findall(
            r"(?:significant|proven|established|demonstrated|confirmed)\s+(\w+(?:\s+\w+)?)",
            hypothesis,
            re.IGNORECASE,
        )
        for m in certainty_matches:
            confounds.append(
                {
                    "variable": m.strip(),
                    "category": ConfoundCategory.measurement,
                    "description": (
                        f"Unwarranted certainty about '{m.strip()}' "
                        "may indicate measurement or confirmation bias"
                    ),
                    "impact_on_hypothesis": (
                        "Measurement bias: assumptions about precision may not be justified"
                    ),
                }
            )

        return confounds[:8]

    # ── Pipeline step 4: Alternative explanations (6.4.4) ─────────────

    def _generate_alternatives(
        self,
        hypothesis: str,
        params: dict[str, Any],
    ) -> list[str]:
        """Generate alternative explanations for the same phenomenon.

        Template-based recombination of hypothesis variables:
        - Reverse causation: swap cause and effect
        - Common cause: a third variable causes both
        - Coincidence: no causal relationship
        - Different mechanism: same outcome, different pathway
        """
        variables = self._extract_variables(hypothesis)
        max_alt = params.get("max_alternatives", self._max_alternatives)
        alternatives: list[str] = []

        if len(variables) >= 2:
            alternatives.append(
                f"Reverse causation: {variables[1]} causes {variables[0]}, "
                "not the other way around."
            )
            alternatives.append(
                f"Common cause: an unobserved third variable Z causes both "
                f"{variables[0]} and {variables[1]}, creating a spurious correlation."
            )
            alternatives.append(
                f"Different mechanism: the relationship between {variables[0]} "
                f"and {variables[1]} exists but operates through an entirely "
                "different biochemical or physical pathway than proposed."
            )
        elif len(variables) == 1:
            alternatives.append(
                f"Reverse causation: the proposed direction is incorrect; "
                f"{variables[0]} may be an outcome rather than a cause."
            )
            alternatives.append(
                f"Common cause: {variables[0]} correlates with both the "
                "phenomenon and an unmeasured third variable."
            )
            alternatives.append(
                "Coincidence: the observed correlation is spurious and "
                "does not reflect a causal relationship."
            )
        else:
            alternatives = [
                "Reverse causation: the proposed causal direction is reversed.",
                "Common cause: an unobserved variable drives both factors.",
                "Coincidence: no causal relationship exists.",
            ]

        alternatives.append(
            "Different mechanism: the same outcome occurs via an "
            "alternative causal pathway not considered in the hypothesis."
        )

        seen: set[str] = set()
        deduped: list[str] = []
        for a in alternatives:
            key = a.lower().strip()
            if key not in seen:
                seen.add(key)
                deduped.append(a)

        return deduped[:max_alt]

    # ── Pipeline step 5: Methodology critique (6.4.5) ─────────────────

    def _critique_methodology(
        self,
        hypothesis: str,
        contradiction_evidence: list[dict[str, Any]],
        _params: dict[str, Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        """Critique the methodology of evidence supporting the hypothesis.

        Uses SourceQualityScorer if available, otherwise applies built-in
        methodology tier analysis.
        """
        methodology_distribution: dict[str, int] = {}
        monoculture_warning = ""
        recency_warning = ""
        testability_assessment = ""

        if self._quality_scorer is not None and contradiction_evidence:
            evidence_items = [e for e in contradiction_evidence if e.get("source_id")]
            for ev in evidence_items:
                try:
                    score = self._quality_scorer.score(ev)
                    ms = str(getattr(score, "methodology_score", 0.0))
                    methodology_distribution[ms] = methodology_distribution.get(ms, 0) + 1
                except Exception:  # noqa: BLE001
                    continue
        elif contradiction_evidence:
            methodology_distribution["not_scored"] = len(contradiction_evidence)

        if not contradiction_evidence:
            testability_assessment = (
                "No contradicting evidence found. The hypothesis may be "
                "unfalsifiable if it cannot generate testable predictions "
                "that could be contradicted by empirical observation."
            )
        else:
            total = len(contradiction_evidence)
            if total <= 2:
                testability_assessment = (
                    "Limited contradicting evidence suggests the hypothesis "
                    "may be difficult to falsify, or the literature base is thin."
                )
            else:
                testability_assessment = (
                    f"Found {total} contradicting or alternative sources. "
                    "The hypothesis generates testable predictions "
                    "amenable to falsification."
                )

            n_methods = len(methodology_distribution)
            if n_methods <= 1:
                monoculture_warning = (
                    "Methodological monoculture detected: all contradicting "
                    "evidence comes from the same methodology tier."
                )

        critique = self._critique_testability(hypothesis)

        return {
            "methodology_distribution": methodology_distribution,
            "monoculture_warning": monoculture_warning,
            "recency_warning": recency_warning,
            "testability_assessment": testability_assessment,
            "overall_critique": critique,
            "n_sources_reviewed": len(contradiction_evidence),
        }

    def _critique_testability(self, hypothesis: str) -> str:
        """Evaluate whether a hypothesis is testable/falsifiable.

        Checks for vague language, non-falsifiable qualifiers,
        and unfalsifiable claims.
        """
        lower = hypothesis.lower()
        issues: list[str] = []

        unfalsifiable_markers = [
            (r"(?:may|might|could)\s+(?:or\s+may\s+not|depending)", "contains untestable hedging"),
            (r"under certain conditions", "conditions are unspecified"),
            (r"(?:in some cases|to some extent|somewhat)", "vague qualifier"),
            (r"(?:everything|nothing|always|never)", "absolute claim is easily falsifiable"),
            (r"(?:invisible|undetectable|unmeasurable)", "posits undetectable entity"),
        ]

        for pattern, issue in unfalsifiable_markers:
            if re.search(pattern, lower):
                issues.append(issue)

        if not issues:
            return (
                "The hypothesis appears testable and falsifiable. "
                "It makes specific claims that can be empirically evaluated."
            )

        return (
            f"The hypothesis shows signs of limited testability: "
            f"{'; '.join(issues)}. These qualifiers should be made "
            "explicit or removed to improve falsifiability."
        )

    # ── Pipeline step 6: Report assembly (6.4.6) ──────────────────────

    def _build_report(
        self,
        hypothesis: str,
        contradiction_evidence: list[dict[str, Any]],
        counter_examples: list[dict[str, Any]],
        confounds: list[dict[str, Any]],
        alternatives: list[str],
        critique: dict[str, Any],
    ) -> dict[str, Any]:
        """Assemble all falsification findings into a structured report."""

        n_contradicting = len(contradiction_evidence)
        n_confounds = len(confounds)
        n_alternatives = len(alternatives)
        n_counter_examples = len(counter_examples)

        if n_contradicting == 0 and n_confounds == 0 and n_alternatives == 0:
            overall_assessment = "weak"
            remaining_uncertainty = (
                "No contradicting evidence, confounds, or alternative "
                "explanations found via heuristic analysis. This may "
                "indicate either a robust hypothesis or limited search depth."
            )
        elif n_contradicting >= 3 or n_confounds >= 2:
            overall_assessment = "strong"
            remaining_uncertainty = (
                "Multiple avenues of falsification found. The hypothesis "
                "should be revised or tested against these specific challenges."
            )
        else:
            overall_assessment = "moderate"
            remaining_uncertainty = (
                "Some potential issues identified. Further targeted "
                "experimentation is needed to resolve uncertainty."
            )

        suggestions: list[str] = []
        if n_contradicting > 0:
            suggestions.append("Design experiments that specifically test the contradicted claims.")
        if n_confounds > 0:
            suggestions.append("Control for identified confounds in experimental design.")
        if n_counter_examples > 0:
            suggestions.append("Test boundary conditions suggested by counter-examples.")
        if n_alternatives > 0:
            suggestions.append("Consider alternative explanations as competing hypotheses.")
        if not suggestions:
            suggestions.append(
                "Broaden literature search to identify potential falsifying evidence."
            )

        return {
            "hypothesis": hypothesis,
            "falsification_search_results": contradiction_evidence,
            "counter_examples": counter_examples,
            "confounds": confounds,
            "alternative_explanations": alternatives,
            "methodology_critique": critique,
            "overall_assessment": overall_assessment,
            "remaining_uncertainty": remaining_uncertainty,
            "suggestions": suggestions,
            "n_contradicting_sources_found": n_contradicting,
            "n_confounds_identified": n_confounds,
            "n_alternatives_proposed": n_alternatives,
            "n_counter_examples_generated": n_counter_examples,
        }

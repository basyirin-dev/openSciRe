# SPDX-License-Identifier: Apache-2.0

"""Auto-submission logic: extract negative results from a
FalsificationAgent report and persist them in the RegistryStore.
"""

from __future__ import annotations

import logging
from typing import Any

from openscire.negative_results.models import (
    NegativeResult,
    NegativeResultOutcome,
)
from openscire.negative_results.store import RegistryStore

logger = logging.getLogger(__name__)

_OUTCOME_MAP: dict[str, NegativeResultOutcome] = {
    "strong_contradicted": NegativeResultOutcome.contradictory,
    "strong_confounded": NegativeResultOutcome.methodological_failure,
    "moderate": NegativeResultOutcome.inconclusive,
}


def _detect_outcome(report: dict[str, Any]) -> NegativeResultOutcome:
    """Map a falsification report to the most specific outcome."""
    assessment = report.get("overall_assessment", "weak")
    n_contradicting = report.get("n_contradicting_sources_found", 0)
    n_confounds = report.get("n_confounds_identified", 0)

    if assessment == "strong" and n_contradicting > 0:
        return NegativeResultOutcome.contradictory
    if assessment == "strong" and n_confounds > 0:
        return NegativeResultOutcome.methodological_failure
    if assessment == "moderate":
        return NegativeResultOutcome.inconclusive
    return NegativeResultOutcome.null


def submit_from_falsification(
    store: RegistryStore,
    falsification_report: dict[str, Any],
    agent_id: str = "falsification",
    provenance_entry_id: str | None = None,
) -> str | None:
    """Extract and register a negative result from a FalsificationAgent report.

    Returns the ``result_id`` if a result was submitted, or ``None`` if
    the report was skipped (e.g. ``overall_assessment == "weak"``
    indicates an unproductive search rather than a genuine negative
    result).

    Args:
        store: An open :class:`RegistryStore` instance.
        falsification_report: The dict returned by
            :meth:`FalsificationAgent._build_report`.
        agent_id: The originating agent identifier.
        provenance_entry_id: Optional link to a provenance DAG entry.
    """
    assessment = falsification_report.get("overall_assessment", "weak")
    hypothesis = falsification_report.get("hypothesis", "")

    # Weak assessments mean the hypothesis wasn't meaningfully tested —
    # no reason to register.
    if assessment == "weak" or not hypothesis:
        logger.info(
            "Skipping auto-registration: overall_assessment='%s' hypothesis='%s'",
            assessment,
            hypothesis[:80] if hypothesis else "",
        )
        return None

    outcome = _detect_outcome(falsification_report)

    source_references: list[str] = []
    for item in falsification_report.get("falsification_search_results", []):
        sid = item.get("source_id", "")
        if sid:
            source_references.append(sid)

    result = NegativeResult(
        hypothesis=hypothesis,
        method_used="falsification_analysis",
        data_summary=_build_data_summary(falsification_report),
        outcome=outcome,
        confidence=_assess_confidence(falsification_report),
        reason_for_failure=_build_failure_reason(falsification_report),
        suggestions=falsification_report.get("suggestions", []),
        source_references=source_references,
        domain_tags=_extract_domain_tags(falsification_report),
        created_by=agent_id,
        provenance_entry_id=provenance_entry_id,
    )

    result_id = store.submit(result)
    logger.info(
        "Registered negative result %s: outcome=%s hypothesis=%s",
        result_id,
        outcome.value,
        hypothesis[:80],
    )
    return result_id


def _build_data_summary(report: dict[str, Any]) -> str:
    """Construct a human-readable data summary from the report."""
    parts: list[str] = []
    n_src = report.get("n_contradicting_sources_found", 0)
    n_conf = report.get("n_confounds_identified", 0)
    n_alt = report.get("n_alternatives_proposed", 0)
    n_ex = report.get("n_counter_examples_generated", 0)

    if n_src:
        parts.append(f"{n_src} contradicting source(s)")
    if n_conf:
        parts.append(f"{n_conf} confound(s) identified")
    if n_alt:
        parts.append(f"{n_alt} alternative explanation(s)")
    if n_ex:
        parts.append(f"{n_ex} counter-example(s)")

    assessment = report.get("overall_assessment", "")
    if assessment:
        parts.insert(0, f"Assessment: {assessment}.")
    return " ".join(parts) if parts else "No data"


def _assess_confidence(report: dict[str, Any]) -> float:
    """Heuristic confidence from the report."""
    assessment = report.get("overall_assessment", "weak")
    mapping = {"weak": 0.1, "moderate": 0.5, "strong": 0.9}
    return mapping.get(assessment, 0.0)


def _build_failure_reason(report: dict[str, Any]) -> str:
    """Summarise why the hypothesis failed."""
    parts: list[str] = []

    critique = report.get("methodology_critique", {})
    if isinstance(critique, dict):
        overall = critique.get("overall_critique", "")
        if overall:
            parts.append(overall)

    uncertainty = report.get("remaining_uncertainty", "")
    if uncertainty:
        parts.append(uncertainty)

    return " | ".join(parts) if parts else "Falsification analysis performed"


def _extract_domain_tags(report: dict[str, Any]) -> list[str]:
    """Attempt to extract domain tags from methodology critique."""
    critique = report.get("methodology_critique", {})
    if isinstance(critique, dict):
        dist = critique.get("methodology_distribution", {})
        if isinstance(dist, dict):
            return list(dist.keys())
    return []

from __future__ import annotations

import contextlib
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from openscire.logging import get_logger

logger = get_logger("openscire.ethics.indigenous_knowledge")

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class IndigenousKnowledgeCategory(StrEnum):
    SACRED_SECRET = "sacred_secret"
    CEREMONIAL = "ceremonial"
    TRADITIONAL_KNOWLEDGE = "traditional_knowledge"
    GENETIC_RESOURCE = "genetic_resource"
    OPEN = "open"


class CAREPrinciple(StrEnum):
    COLLECTIVE_BENEFIT = "collective_benefit"
    AUTHORITY_TO_CONTROL = "authority_to_control"
    RESPONSIBILITY = "responsibility"
    ETHICS = "ethics"


# ---------------------------------------------------------------------------
# Verdict model
# ---------------------------------------------------------------------------


class IndigenousKnowledgeVerdict(BaseModel):
    verdict_id: str
    category: IndigenousKnowledgeCategory = IndigenousKnowledgeCategory.OPEN
    blocked: bool = False
    care_principles_violated: list[CAREPrinciple] = Field(default_factory=list)
    requires_community_consent: bool = False
    requires_benefit_sharing: bool = False
    requires_ethics_review: bool = False
    restriction_summary: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# Field-level keyword maps for cultural restriction classification
# ---------------------------------------------------------------------------

CULTURAL_CATEGORY_KEYWORDS: dict[IndigenousKnowledgeCategory, dict[str, list[str]]] = {
    IndigenousKnowledgeCategory.SACRED_SECRET: {
        "cultural_restriction": [
            r"\bsacred\b",
            r"\bsecret[\- ]?sacred\b",
            r"\bsecret/sacred\b",
            r"\bmen['’]?s business\b",
            r"\bwomen['’]?s business\b",
            r"\bsorcery\b",
        ],
        "knowledge_type": [
            r"\binitiation\b",
            r"\bdreaming\b",
            r"\bsongline\b",
            r"\bdreamtime\b",
        ],
        "restriction_level": [
            r"\bno.access\b",
            r"\bstrictly.restricted\b",
            r"\btotally.restricted\b",
        ],
    },
    IndigenousKnowledgeCategory.CEREMONIAL: {
        "cultural_restriction": [
            r"\bceremonial\b",
            r"\britual\b",
            r"\bcustomary\b",
        ],
        "knowledge_type": [
            r"\bdance\b",
            r"\bchant\b",
            r"\bceremony\b",
            r"\brite\b",
        ],
        "restriction_level": [
            r"\bcommunity.only\b",
            r"\binitiated.only\b",
            r"\belders.only\b",
        ],
    },
    IndigenousKnowledgeCategory.TRADITIONAL_KNOWLEDGE: {
        "knowledge_type": [
            r"\btraditional knowledge\b",
            r"\bfolk\b",
            r"\bmedicinal\b",
            r"\becological\b",
            r"\bbush tucker\b",
            r"\bush (?:medicine|food|knowledge)\b",
        ],
        "origin": [
            r"\bindigenous\b",
            r"\btraditional\b",
            r"\bancestral\b",
        ],
        "source": [
            r"\belders?\b",
            r"\bcommunity knowledge\b",
            r"\boral tradition\b",
        ],
    },
    IndigenousKnowledgeCategory.GENETIC_RESOURCE: {
        "knowledge_type": [
            r"\bgenetic\b",
            r"\bgenomic\b",
            r"\bbioprospecting\b",
        ],
        "source": [
            r"\bblood\b",
            r"\btissue\b",
            r"\bdna\b",
        ],
        "legal_framework": [
            r"\bnagoya\b",
            r"\baccess and benefit sharing\b",
            r"\babs\b",
        ],
    },
}

# ---------------------------------------------------------------------------
# CARE principle field checks — metadata fields that satisfy each principle
# ---------------------------------------------------------------------------

_CARE_PRINCIPLE_FIELDS: dict[CAREPrinciple, set[str]] = {
    CAREPrinciple.COLLECTIVE_BENEFIT: {
        "benefit_sharing",
        "community_benefit_agreement",
    },
    CAREPrinciple.AUTHORITY_TO_CONTROL: {
        "fpic",
        "governing_authority",
        "community_consent",
    },
    CAREPrinciple.RESPONSIBILITY: {
        "permitted_use",
        "usage_scope",
    },
    CAREPrinciple.ETHICS: {
        "ethics_review",
        "review_board",
    },
}

# ---------------------------------------------------------------------------
# Category protection levels — which CARE principles must be satisfied
# ---------------------------------------------------------------------------

_CATEGORY_CARE_MAP: dict[
    IndigenousKnowledgeCategory,
    tuple[set[CAREPrinciple], bool],
] = {
    IndigenousKnowledgeCategory.SACRED_SECRET: (
        set(),  # always blocked — no CARE principle can unblock
        True,  # categorically blocked
    ),
    IndigenousKnowledgeCategory.CEREMONIAL: (
        {CAREPrinciple.AUTHORITY_TO_CONTROL},
        False,
    ),
    IndigenousKnowledgeCategory.TRADITIONAL_KNOWLEDGE: (
        {CAREPrinciple.COLLECTIVE_BENEFIT},
        False,
    ),
    IndigenousKnowledgeCategory.GENETIC_RESOURCE: (
        {CAREPrinciple.COLLECTIVE_BENEFIT, CAREPrinciple.ETHICS},
        False,
    ),
    IndigenousKnowledgeCategory.OPEN: (
        set(),
        False,
    ),
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _match_field(field_value: str, patterns: list[str]) -> bool:
    import re

    val = str(field_value).lower()
    return any(re.search(pat, val, re.IGNORECASE) for pat in patterns)


def _scan_fields(
    metadata: dict[str, Any],
    field_map: dict[str, list[str]],
) -> bool:
    for field_name, patterns in field_map.items():
        raw = metadata.get(field_name)
        if raw is None:
            continue
        if isinstance(raw, list) and any(_match_field(str(item), patterns) for item in raw):
            return True
        if isinstance(raw, str) and _match_field(raw, patterns):
            return True
        if isinstance(raw, dict) and _match_field(str(raw), patterns):
            return True
    return False


# ---------------------------------------------------------------------------
# Protector
# ---------------------------------------------------------------------------


class IndigenousKnowledgeProtector:
    """Classifies indigenous knowledge categories and enforces CARE principles.

    Inspects structured metadata dicts for culturally restricted data markers,
    classifies the knowledge into one of five categories (sacred_secret,
    ceremonial, traditional_knowledge, genetic_resource, open), and evaluates
    CARE Principle compliance (Collective Benefit, Authority to Control,
    Responsibility, Ethics).

    Designed to run independently from DataSovereigntyChecker — callers can
    short-circuit entirely when data origin is known non-indigenous.
    """

    def __init__(self, require_care_compliance: bool = True) -> None:
        self._require_care_compliance = require_care_compliance

    def check(
        self,
        metadata: dict[str, Any],
        provenance_tracker: Any = None,  # noqa: ANN401
    ) -> IndigenousKnowledgeVerdict:
        """Evaluate indigenous knowledge protections for a metadata context.

        Args:
            metadata: Structured dict with cultural restriction markers.
            provenance_tracker: Optional ProvenanceTracker for audit trail.

        Returns:
            An IndigenousKnowledgeVerdict with category, blocking status,
            and CARE principle violations.
        """
        verdict_id = __import__("uuid").uuid4().hex[:12]

        category = self._classify_category(metadata)
        blocked, care_violated, need_consent, need_benefit, need_ethics = self._evaluate_category(
            category, metadata
        )

        summary_parts: list[str] = []
        if blocked:
            summary_parts.append(
                f"Blocked: {category.value} knowledge — requires CARE principle compliance."
            )
        if care_violated:
            names = ", ".join(p.value for p in care_violated)
            summary_parts.append(f"CARE violation: {names}")
        if need_consent:
            summary_parts.append("Requires community consent.")
        if need_benefit:
            summary_parts.append("Requires benefit-sharing agreement.")
        if need_ethics:
            summary_parts.append("Requires ethics review.")
        if not summary_parts:
            summary_parts.append("No restrictions detected.")

        summary = " ".join(summary_parts)

        if provenance_tracker is not None:
            with contextlib.suppress(Exception):
                provenance_tracker.track(
                    action_type="indigenous_knowledge_check",
                    params={
                        "verdict_id": verdict_id,
                        "category": category.value,
                        "blocked": blocked,
                        "care_principles_violated": [p.value for p in care_violated],
                    },
                )

        return IndigenousKnowledgeVerdict(
            verdict_id=verdict_id,
            category=category,
            blocked=blocked,
            care_principles_violated=care_violated,
            requires_community_consent=need_consent,
            requires_benefit_sharing=need_benefit,
            requires_ethics_review=need_ethics,
            restriction_summary=summary,
            timestamp=datetime.now(),
        )

    def _classify_category(
        self,
        metadata: dict[str, Any],
    ) -> IndigenousKnowledgeCategory:
        """Classify metadata into an indigenous knowledge category.

        Checks categories in order of restrictiveness (sacred_secret first,
        open last).  Uses field-level keyword matching.
        """
        for cat in (
            IndigenousKnowledgeCategory.SACRED_SECRET,
            IndigenousKnowledgeCategory.CEREMONIAL,
            IndigenousKnowledgeCategory.TRADITIONAL_KNOWLEDGE,
            IndigenousKnowledgeCategory.GENETIC_RESOURCE,
        ):
            field_map = CULTURAL_CATEGORY_KEYWORDS[cat]
            if _scan_fields(metadata, field_map):
                return cat
        return IndigenousKnowledgeCategory.OPEN

    def _evaluate_category(
        self,
        category: IndigenousKnowledgeCategory,
        metadata: dict[str, Any],
    ) -> tuple[
        bool,
        list[CAREPrinciple],
        bool,
        bool,
        bool,
    ]:
        """Evaluate category-specific blocking rules and CARE compliance.

        Returns (blocked, care_violated, need_consent, need_benefit, need_ethics).
        """
        required_principals, categorically_blocked = _CATEGORY_CARE_MAP.get(
            category, (set(), False)
        )

        care_violated: list[CAREPrinciple] = []
        need_consent = False
        need_benefit = False
        need_ethics = False

        if categorically_blocked:
            return (True, care_violated, need_consent, need_benefit, need_ethics)

        for principle in required_principals:
            fields = _CARE_PRINCIPLE_FIELDS.get(principle, set())
            satisfied = any(_care_field_satisfied(metadata, field) for field in fields)
            if not satisfied:
                care_violated.append(principle)

        blocked = bool(care_violated) if self._require_care_compliance else False

        need_consent = CAREPrinciple.AUTHORITY_TO_CONTROL in care_violated
        need_benefit = CAREPrinciple.COLLECTIVE_BENEFIT in care_violated
        need_ethics = CAREPrinciple.ETHICS in care_violated

        return (blocked, care_violated, need_consent, need_benefit, need_ethics)


def _care_field_satisfied(metadata: dict[str, Any], field: str) -> bool:
    """Check if a CARE field is present and truthy in metadata."""
    raw = metadata.get(field)
    if raw is None:
        return False
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() not in ("", "false", "no", "0")
    return True

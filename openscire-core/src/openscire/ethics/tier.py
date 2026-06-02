from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

from openscire.constants import RiskTier
from openscire.logging import get_logger
from openscire.provider.base import ModelProvider

from .classifier import KeywordMatcher, LLMClassifier
from .models import (
    MatchType,
    TierGovernanceAction,
    TierResult,
)

logger = get_logger("openscire.ethics.tier")

# ---------------------------------------------------------------------------
# Domain keyword patterns per risk tier
# ---------------------------------------------------------------------------
# WARNING: These patterns identify research *domains*, not dangerous content.
# They are heuristic, English-biased, and will produce both false positives
# and false negatives. They are a starting filter for governance speed, not
# a security boundary. Unknown domains default to LOW to minimize friction.
#
# Patterns use word boundaries (\b) for regex matching.

TIER_KEYWORD_PATTERNS: dict[RiskTier, dict[str, list[str]]] = {
    RiskTier.HIGH: {
        "virology": [
            r"\bvirology\b",
            r"\bviral replication\b",
            r"\bhost[.\- ]?pathogen\b",
            r"\bpandemic preparedness\b",
            r"\bantiviral resistance\b",
        ],
        "toxin_research": [
            r"\btoxin research\b",
            r"\bbenchtop synthesis\b",
            r"\bchemical weapon\b",
            r"\bbiological toxin\b",
        ],
        "ai_safety": [
            r"\bAI safety\b",
            r"\balignment research\b",
            r"\bvalue learning\b",
            r"\bAI governance\b",
            r"\bcapability[.\- ]?control\b",
        ],
        "weapons": [
            r"\bweapon design\b",
            r"\bexplosive ordnance\b",
            r"\bmunitions\b",
            r"\bballistic missile\b",
        ],
        "dual_use_chemistry": [
            r"\bchemical synthesis\b",
            r"\bprecursor chemistry\b",
            r"\bnerve agent\b",
            r"\bchemical agent\b",
        ],
        "human_genetic_engineering": [
            r"\bgene editing\b",
            r"\bgermline\b",
            r"\bhuman genetic engineering\b",
            r"\bCRISPR[.\- ]?human\b",
            r"\bheritable modification\b",
        ],
    },
    RiskTier.MEDIUM: {
        "clinical_research": [
            r"\bclinical trial\b",
            r"\bIRB\b",
            r"\binformed consent\b",
            r"\bPhase [I1-3]\b",
            r"\bpatient study\b",
        ],
        "human_subjects": [
            r"\bhuman subjects\b",
            r"\bhuman data\b",
            r"\bpersonally identifiable\b",
            r"\bprivacy regulation\b",
            r"\bHIPAA\b",
        ],
        "animal_research": [
            r"\bin vivo\b",
            r"\banimal model\b",
            r"\bmouse model\b",
            r"\brodent study\b",
            r"\bIACUC\b",
        ],
        "controlled_substances": [
            r"\bSchedule [I1-5V]\b",
            r"\bcontrolled substance\b",
            r"\bDEA schedule\b",
            r"\bnarcotic\b",
            r"\bpsychoactive compound\b",
        ],
    },
    RiskTier.LOW: {
        "solar_forecasting": [
            r"\bsolar irradiance\b",
            r"\bphotovoltaic\b",
            r"\bsolar forecasting\b",
            r"\brenewable energy\b",
        ],
        "materials_science": [
            r"\bcrystal structure\b",
            r"\bmaterials science\b",
            r"\bthin film\b",
            r"\bnanomaterial\b",
            r"\bmetallurgy\b",
        ],
        "ecology": [
            r"\bpopulation dynamics\b",
            r"\becosystem model\b",
            r"\bbiodiversity\b",
            r"\bclimate ecology\b",
            r"\bconservation biology\b",
        ],
        "mathematics": [
            r"\btheorem\b",
            r"\btopology\b",
            r"\bnumber theory\b",
            r"\babstract algebra\b",
            r"\bproof theory\b",
        ],
        "theoretical_physics": [
            r"\bquantum field\b",
            r"\bstring theory\b",
            r"\bgeneral relativity\b",
            r"\bparticle physics\b",
            r"\bcosmology\b",
        ],
    },
}

TIER_DOMAIN_LABELS: dict[str, str] = {
    "virology": "Virology Research",
    "toxin_research": "Toxin Research",
    "ai_safety": "AI Safety Research",
    "weapons": "Weapons Research",
    "dual_use_chemistry": "Dual-Use Chemistry",
    "human_genetic_engineering": "Human Genetic Engineering",
    "clinical_research": "Clinical Research",
    "human_subjects": "Human Subjects Data",
    "animal_research": "Animal Research",
    "controlled_substances": "Controlled Substances",
    "solar_forecasting": "Solar Forecasting",
    "materials_science": "Materials Science",
    "ecology": "Ecology Observation",
    "mathematics": "Mathematics",
    "theoretical_physics": "Theoretical Physics",
}

# Seed phrases for optional embedding-based tier classification.
TIER_EMBEDDING_SEEDS: dict[str, list[str]] = {
    "virology": [
        "studying viral replication and host-pathogen interactions",
        "research on pandemic viruses and their transmission",
    ],
    "toxin_research": [
        "synthesizing and characterizing biological toxins",
        "chemical analysis of weaponizable compounds",
    ],
    "ai_safety": [
        "ensuring AI systems remain aligned with human values",
        "research on AI governance and capability control",
    ],
    "solar_forecasting": [
        "predicting solar irradiance for renewable energy",
        "modeling photovoltaic cell efficiency under varying conditions",
    ],
    "mathematics": [
        "proving theorems in abstract algebra and topology",
        "research in number theory and mathematical logic",
    ],
}

TIER_CLASSIFICATION_PROMPT = (
    "You are a research domain classifier. "
    "Your task is to classify the following research text "
    "into one of these risk tiers based on its domain:\n"
    "\n"
    "**Tier 1 (High Risk)** — requires cooling-off and external review:\n"
    "- virology, toxin research, AI safety, weapons, dual-use chemistry, "
    "human genetic engineering\n"
    "\n"
    "**Tier 2 (Medium Risk)** — requires human checkpoint:\n"
    "- clinical research, human subjects data, animal research, "
    "controlled substances\n"
    "\n"
    "**Tier 3 (Low Risk)** — standard workflow:\n"
    "- solar forecasting, materials science, ecology, mathematics, "
    "theoretical physics\n"
    "\n"
    "Text to classify:\n"
    "---\n"
    "{text}\n"
    "---\n"
    "\n"
    "Respond with a JSON object exactly like this (no other text):\n"
    '{{"tier": "tier_1_high" or "tier_2_medium" or "tier_3_low",\n'
    '  "domain": "domain_key",\n'
    '  "confidence": 0.0-1.0,\n'
    '  "reasoning": "short explanation"}}'
)


def _get_governance_action(tier: RiskTier) -> TierGovernanceAction:
    if tier == RiskTier.HIGH:
        return TierGovernanceAction.COOLING_OFF
    if tier == RiskTier.MEDIUM:
        return TierGovernanceAction.HUMAN_CHECKPOINT
    return TierGovernanceAction.STANDARD


def _tier_priority(tier: RiskTier) -> int:
    return {RiskTier.LOW: 0, RiskTier.MEDIUM: 1, RiskTier.HIGH: 2}.get(tier, 0)


def _can_escalate(current: RiskTier, new: RiskTier) -> bool:
    return _tier_priority(new) > _tier_priority(current)


def _is_downgrade(current: RiskTier, new: RiskTier) -> bool:
    return _tier_priority(new) < _tier_priority(current)


class TierClassifier:
    """Classifies research text into risk tiers for differential speed governance.

    Uses keyword matching (always), optional embedding matching, and optional
    LLM-assisted classification.  Unknown/unmatched text defaults to LOW.
    """

    def __init__(
        self,
        keyword_patterns: dict[RiskTier, dict[str, list[str]]] | None = None,
        llm_provider: ModelProvider | None = None,
        default_tier: RiskTier = RiskTier.LOW,
        min_confidence: float = 0.6,
        cool_off_hours: int = 24,
    ) -> None:
        flat_patterns: dict[str, list[str]] = {}
        source = keyword_patterns or TIER_KEYWORD_PATTERNS
        for _tier, domains in source.items():
            for domain, patterns in domains.items():
                flat_patterns[domain] = patterns
        self._keyword_matcher = KeywordMatcher(flat_patterns)
        self._llm = (
            LLMClassifier(
                provider=llm_provider,
                prompt_template=TIER_CLASSIFICATION_PROMPT,
            )
            if llm_provider
            else None
        )
        self._default_tier = default_tier
        self._min_confidence = min_confidence
        self._cool_off_hours = cool_off_hours

    async def classify(
        self,
        text: str,
        provenance_tracker: Any = None,  # noqa: ANN401
    ) -> TierResult:
        """Classify text into a risk tier.

        Args:
            text: The text to classify.
            provenance_tracker: Optional ProvenanceTracker for audit logging.

        Returns:
            A TierResult with the assigned tier, domain, and governance action.
        """
        # 1. Keyword matching
        kw_matches = self._keyword_matcher.scan(text)

        best_tier = self._default_tier
        best_domain = ""
        best_confidence = 0.0
        best_match_type: MatchType | None = None

        if kw_matches:
            domain_matches: dict[str, int] = {}
            for domain_key, _, _ in kw_matches:
                domain_matches[domain_key] = domain_matches.get(domain_key, 0) + 1

            best_domain = max(domain_matches, key=domain_matches.get) if domain_matches else ""
            count = domain_matches.get(best_domain, 0)
            best_confidence = min(0.5 + count * 0.15, 0.95)
            best_match_type = MatchType.KEYWORD

            for _tier, domains in TIER_KEYWORD_PATTERNS.items():
                if best_domain in domains:
                    best_tier = _tier
                    break

        # 2. LLM classification if keyword match is weak and LLM available
        if best_confidence < self._min_confidence and self._llm is not None:
            try:
                llm_results = await self._llm.classify(text, [])
                if llm_results:
                    llm_result = llm_results[0]
                    parsed = self._parse_llm_tier(llm_result)
                    if parsed and parsed["confidence"] > best_confidence:
                        best_tier = parsed["tier"]
                        best_domain = parsed["domain"]
                        best_confidence = parsed["confidence"]
                        best_match_type = MatchType.LLM
            except Exception:
                logger.warning("LLM tier classification failed", exc_info=True)

        # 3. Governance action
        action = _get_governance_action(best_tier)
        cool_off_until = None
        if action == TierGovernanceAction.COOLING_OFF:
            cool_off_until = datetime.now(UTC) + timedelta(hours=self._cool_off_hours)

        # 4. Provenance
        if provenance_tracker is not None:
            try:
                provenance_tracker.track(
                    action_type="risk_tier_classification",
                    params={
                        "tier": best_tier.value,
                        "domain": best_domain,
                        "confidence": best_confidence,
                        "match_type": best_match_type.value if best_match_type else "",
                        "governance_action": action.value,
                    },
                    input_hash=hashlib.sha256(text.encode()).hexdigest(),
                )
            except Exception:
                logger.warning("Failed to track tier classification provenance", exc_info=True)

        return TierResult(
            assigned_tier=best_tier,
            domain=best_domain,
            domain_label=TIER_DOMAIN_LABELS.get(best_domain, best_domain),
            match_type=best_match_type,
            confidence=best_confidence,
            governance_action=action,
            timestamp=datetime.now(UTC),
            cool_off_hours=self._cool_off_hours,
            cool_off_until=cool_off_until,
        )

    @staticmethod
    def _parse_llm_tier(result: Any) -> dict[str, Any] | None:  # noqa: ANN401
        if not hasattr(result, "matched_text") or not result.matched_text:
            return None
        import json

        try:
            parsed = json.loads(result.matched_text)
            if "tier" not in parsed:
                return None
            tier_map = {
                "tier_1_high": RiskTier.HIGH,
                "tier_2_medium": RiskTier.MEDIUM,
                "tier_3_low": RiskTier.LOW,
            }
            tier = tier_map.get(parsed["tier"])
            if tier is None:
                return None
            return {
                "tier": tier,
                "domain": parsed.get("domain", ""),
                "confidence": min(max(float(parsed.get("confidence", 0.5)), 0.0), 1.0),
            }
        except (ValueError, json.JSONDecodeError, TypeError):
            return None


# ---------------------------------------------------------------------------
# Cooling-off registry
# ---------------------------------------------------------------------------


class CoolOffRegistry:
    """Tracks cooling-off periods for Tier 1 (High Risk) queries.

    Maps input_hash to the timestamp when the query was first classified.
    On re-check, verifies that the configured cooling-off period has elapsed.
    """

    def __init__(self, conn: Any = None) -> None:  # noqa: ANN401
        self._conn = conn
        if conn is not None:
            self._init_table()

    def _init_table(self) -> None:
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS tier_cool_off ("
            "input_hash TEXT PRIMARY KEY,"
            "classified_at TEXT NOT NULL,"
            "cool_off_hours INTEGER NOT NULL DEFAULT 24"
            ")"
        )
        self._conn.commit()

    def register(self, input_hash: str, cool_off_hours: int = 24) -> None:
        if self._conn is None:
            return
        self._conn.execute(
            "INSERT OR IGNORE INTO tier_cool_off (input_hash, classified_at, cool_off_hours) "
            "VALUES (?, ?, ?)",
            (input_hash, datetime.now(UTC).isoformat(), cool_off_hours),
        )
        self._conn.commit()

    def is_eligible(self, input_hash: str) -> bool:
        """Check if the cooling-off period has elapsed for this input."""
        if self._conn is None:
            return True
        row = self._conn.execute(
            "SELECT classified_at, cool_off_hours FROM tier_cool_off WHERE input_hash = ?",
            (input_hash,),
        ).fetchone()
        if row is None:
            return True
        classified_at = datetime.fromisoformat(row[0])
        elapsed = datetime.now(UTC) - classified_at
        return elapsed.total_seconds() >= row[1] * 3600

    def query(self, input_hash: str) -> dict[str, Any] | None:
        """Return registration data for a hash, or None if unknown."""
        if self._conn is None:
            return None
        row = self._conn.execute(
            "SELECT input_hash, classified_at, cool_off_hours FROM tier_cool_off "
            "WHERE input_hash = ?",
            (input_hash,),
        ).fetchone()
        if row is None:
            return None
        return {
            "input_hash": row[0],
            "classified_at": row[1],
            "cool_off_hours": row[2],
        }

    def is_qualified(self, input_hash: str) -> bool:
        """Alias for is_eligible: check if cooling-off period has elapsed."""
        return self.is_eligible(input_hash)

    def remaining_seconds(self, input_hash: str) -> float:
        """Seconds remaining in the cooling-off period (0 if eligible)."""
        if self._conn is None:
            return 0.0
        row = self._conn.execute(
            "SELECT classified_at, cool_off_hours FROM tier_cool_off WHERE input_hash = ?",
            (input_hash,),
        ).fetchone()
        if row is None:
            return 0.0
        classified_at = datetime.fromisoformat(row[0])
        elapsed = datetime.now(UTC) - classified_at
        remaining = row[1] * 3600 - elapsed.total_seconds()
        return max(0.0, remaining)

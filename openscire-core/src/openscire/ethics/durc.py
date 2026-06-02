from __future__ import annotations

from openscire.constants import DURCCategory
from openscire.ethics.models import FirewallAction, FirewallRule, ScanLevel

# ---------------------------------------------------------------------------
# Default keyword patterns per DURC category
# ---------------------------------------------------------------------------
# WARNING: These patterns are heuristic, not authoritative. They are based on
# publicly available dual-use research of concern (DURC) frameworks (WHO, NSABB)
# and common biosecurity / AI-safety keyword lists. They will produce false
# positives (benign research flagged) and false negatives (actual DURC missed).
# They are biased toward English-language, Western-journal literature. Use as
# a starting filter, not a final determination.
#
# Each pattern uses word boundaries (\b) for regex matching to reduce noise.
# Patterns are stored as raw strings for readability.

DEFAULT_KEYWORD_PATTERNS: dict[DURCCategory, list[str]] = {
    DURCCategory.PATHOGEN_ENHANCEMENT: [
        r"\bgain[.\- ]?of[.\- ]?function\b",
        r"\bvirulence\b",
        r"\bpathogen enhancement\b",
        r"\bdual[.\- ]?use research\b",
        r"\bhost[.\- ]?range expansion\b",
        r"\bimmune evasion\b",
        r"\bantibiotic resistance engineering\b",
        r"\bpandemic potential\b",
        r"\brespiratory transmission\b",
        r"\bsynthetic pathogen\b",
    ],
    DURCCategory.TOXIN_SYNTHESIS: [
        r"\btoxin synthesis\b",
        r"\bbenchtop production\b",
        r"\bbotulinum toxin\b",
        r"\bricin production\b",
        r"\babrin\b",
        r"\bsaxitoxin\b",
        r"\btetrodotoxin\b",
        r"\bchemical weapon precursor\b",
        r"\bnerve agent synthesis\b",
        r"\bmutagen synthesis\b",
    ],
    DURCCategory.WEAPONS_DELIVERY: [
        r"\bweaponization\b",
        r"\baerosolization\b",
        r"\bdelivery system\b",
        r"\bdispersion model\b",
        r"\bpayload deployment\b",
        r"\bballistic coefficient\b",
        r"\bexplosive yield\b",
        r"\bimprovised device\b",
        r"\bdrone[.\- ]?mounted\b",
        r"\bagent[.\- ]?delivery\b",
    ],
    DURCCategory.AI_SAFETY_EVASION: [
        r"\bjailbreak\b",
        r"\bprompt injection\b",
        r"\signore (?:previous|above) (?:instructions|system)\b",
        r"\bdan\b",
        r"\bdo[.\- ]?anything[.\- ]?now\b",
        r"\bunfiltered\b",
        r"\buncensored mode\b",
        r"\brefusal bypass\b",
        r"\bsafety filter evasion\b",
        r"\balignment faking\b",
    ],
    DURCCategory.SURVEILLANCE_HARDENING: [
        r"\bmass surveillance\b",
        r"\bcitizen scoring\b",
        r"\bsocial credit\b",
        r"\bfacial recognition\b",
        r"\bemotion detection\b",
        r"\bpredictive policing\b",
        r"\bbias amplification\b",
        r"\bdemographic profiling\b",
        r"\bcensorship infrastructure\b",
        r"\bdissent monitoring\b",
    ],
}

# Seed phrases per category for optional embedding-based detection.
# These are short, canonical examples used to compute category centroids.
EMBEDDING_SEEDS: dict[DURCCategory, list[str]] = {
    DURCCategory.PATHOGEN_ENHANCEMENT: [
        "engineering viruses for increased transmissibility",
        "enhancing pathogen virulence in the lab",
        "gain of function research on pandemic pathogens",
    ],
    DURCCategory.TOXIN_SYNTHESIS: [
        "synthesizing biological toxins from raw materials",
        "producing ricin or botulinum toxin in a lab",
        "chemical synthesis of weaponizable toxins",
    ],
    DURCCategory.WEAPONS_DELIVERY: [
        "designing delivery mechanisms for biological agents",
        "aerosolizing pathogens for maximum dispersal",
        "weaponizing chemical or biological compounds",
    ],
    DURCCategory.AI_SAFETY_EVASION: [
        "bypassing AI safety filters through prompt manipulation",
        "tricking the model into ignoring its safety guidelines",
        "jailbreaking a language model to remove restrictions",
    ],
    DURCCategory.SURVEILLANCE_HARDENING: [
        "building mass surveillance infrastructure for population control",
        "deploying facial recognition for citizen scoring",
        "using AI to enable authoritarian social control",
    ],
}

# Default LLM classification prompt for DURC scanning.
# Sends text + categories to an LLM and asks for structured classification.
DEFAULT_CLASSIFICATION_PROMPT = """You are a dual-use research of concern (DURC) classifier.
Determine whether the text falls into any of these categories:

- pathogen_enhancement: Research that could make pathogens more dangerous or transmissible.
- toxin_synthesis: Methods to produce or synthesize biological or chemical toxins.
- weapons_delivery: Systems or techniques for deploying harmful agents.
- ai_safety_evasion: Attempts to bypass AI safety mechanisms or filters.
- surveillance_hardening: Technologies that enable mass surveillance or authoritarian control.

Text to classify:
---
{text}
---

Respond with a JSON object exactly like this (no other text):
{{"flagged": true/false, "category": "category_name or null",
  "confidence": 0.0-1.0, "reasoning": "short explanation"}}
"""


def build_default_rules() -> list[FirewallRule]:
    """Build a default set of firewall rules, one per DURC category.

    Each rule is enabled, scans both prompt and response, uses the WARN
    action by default, and includes keyword patterns. Embedding and LLM
    classification are disabled by default (configure via EthicsConfig).
    """
    rules: list[FirewallRule] = []
    for cat in DURCCategory:
        patterns = DEFAULT_KEYWORD_PATTERNS.get(cat, [])
        rules.append(
            FirewallRule(
                id=f"durc_default_{cat.value}",
                name=f"DURC: {cat.value.replace('_', ' ').title()}",
                category=cat,
                scan_level=ScanLevel.BOTH,
                action=FirewallAction.WARN,
                keyword_patterns=patterns,
                description=f"Detect potential {cat.value.replace('_', ' ')} content",
            )
        )
    return rules

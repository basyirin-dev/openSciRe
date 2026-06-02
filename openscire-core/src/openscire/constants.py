# SPDX-License-Identifier: Apache-2.0

"""Error codes, model provider enums, and system-wide constants."""

from enum import StrEnum


class DURCCategory(StrEnum):
    """Dual-use research of concern categories for the ethical firewall.

    These categories are based on the WHO and NSABB frameworks for
    identifying research with potential for dual-use misapplication.
    This list is neither exhaustive nor authoritative — it is a
    starting heuristic that requires ongoing expert review.
    """

    PATHOGEN_ENHANCEMENT = "pathogen_enhancement"
    TOXIN_SYNTHESIS = "toxin_synthesis"
    WEAPONS_DELIVERY = "weapons_delivery"
    AI_SAFETY_EVASION = "ai_safety_evasion"
    SURVEILLANCE_HARDENING = "surveillance_hardening"


class RiskTier(StrEnum):
    """Risk tiers for differential speed governance of research queries.

    Tier 1 (HIGH): Domains with clear dual-use potential — virology, toxins,
        weapons, AI safety, human genetic engineering.  Requires cooling-off
        period and external reviewer gate.
    Tier 2 (MEDIUM): Domains involving human or animal subjects, clinical
        data, or controlled substances.  Requires human checkpoint.
    Tier 3 (LOW): Standard research domains — mathematics, ecology, materials
        science, theoretical physics.  Standard workflow.

    Unknown/unclassified text defaults to LOW to minimize friction; the DURC
    firewall handles genuine dangerous content independently.
    """

    LOW = "tier_3_low"
    MEDIUM = "tier_2_medium"
    HIGH = "tier_1_high"


class ErrorCode(StrEnum):
    """Standardized error codes grouped by subsystem.

    Categories:
        ERR_BASE: Unclassified base errors.
        PROV_*: Provenance chain, signing, and tamper-detection errors.
        CONFIG_*: Configuration validation errors.
        MODEL_*: Model provider connection, auth, rate-limit, and capability errors.
        ETHICS_*: Ethical guardrail violations (DURC, sovereignty, firewall, carbon).
        VALIDATION_*: Claim, evidence, and citation validation failures.
        UNCERTAINTY_*: Uncertainty and epistemic boundary violations.
    """

    ERR_BASE = "ERR_BASE"

    PROV_SIGNING_FAILURE = "PROV_SIGNING_FAILURE"
    PROV_CHAIN_BREAK = "PROV_CHAIN_BREAK"
    PROV_TAMPER_DETECTED = "PROV_TAMPER_DETECTED"

    CONFIG_INVALID = "CONFIG_INVALID"
    CONFIG_KEY_MANAGEMENT = "CONFIG_KEY_MANAGEMENT"
    CONFIG_MISSING_FIELD = "CONFIG_MISSING_FIELD"
    CONFIG_TYPE_MISMATCH = "CONFIG_TYPE_MISMATCH"

    MODEL_CONNECTION_FAILURE = "MODEL_CONNECTION_FAILURE"
    MODEL_AUTH_FAILURE = "MODEL_AUTH_FAILURE"
    MODEL_RATE_LIMIT = "MODEL_RATE_LIMIT"
    MODEL_UNSUPPORTED_CAPABILITY = "MODEL_UNSUPPORTED_CAPABILITY"

    ETHICS_DURC_FLAG = "ETHICS_DURC_FLAG"
    ETHICS_SOVEREIGNTY_VIOLATION = "ETHICS_SOVEREIGNTY_VIOLATION"
    ETHICS_INDIGENOUS_RESTRICTION = "ETHICS_INDIGENOUS_RESTRICTION"
    ETHICS_FIREWALL_BLOCKED = "ETHICS_FIREWALL_BLOCKED"
    ETHICS_TIER_BLOCKED = "ETHICS_TIER_BLOCKED"
    ETHICS_EXPORT_BLOCKED = "ETHICS_EXPORT_BLOCKED"
    ETHICS_CARE_VIOLATION = "ETHICS_CARE_VIOLATION"
    ETHICS_CARBON_BUDGET_EXCEEDED = "ETHICS_CARBON_BUDGET_EXCEEDED"

    VALIDATION_CLAIM_INVALID = "VALIDATION_CLAIM_INVALID"
    VALIDATION_EVIDENCE_INSUFFICIENT = "VALIDATION_EVIDENCE_INSUFFICIENT"
    VALIDATION_CITATION_BROKEN = "VALIDATION_CITATION_BROKEN"
    VALIDATION_SOURCE_NOT_FOUND = "VALIDATION_SOURCE_NOT_FOUND"
    VALIDATION_RETRACTED_SOURCE = "VALIDATION_RETRACTED_SOURCE"
    UNCERTAINTY_INSUFFICIENT = "UNCERTAINTY_INSUFFICIENT"
    VALIDATION_ASYMMETRY_DETECTED = "VALIDATION_ASYMMETRY_DETECTED"
    VALIDATION_CONFABULATION_DETECTED = "VALIDATION_CONFABULATION_DETECTED"

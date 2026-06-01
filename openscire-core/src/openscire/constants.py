# SPDX-License-Identifier: Apache-2.0

"""Error codes, model provider enums, and system-wide constants."""

from enum import StrEnum


class ErrorCode(StrEnum):
    """Standardized error codes grouped by subsystem.

    Categories:
        ERR_BASE: Unclassified base errors.
        PROV_*: Provenance chain, signing, and tamper-detection errors.
        CONFIG_*: Configuration validation errors.
        MODEL_*: Model provider connection, auth, rate-limit, and capability errors.
        ETHICS_*: Ethical guardrail violations (DURC, sovereignty).
        VALIDATION_*: Claim, evidence, and citation validation failures.
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

    VALIDATION_CLAIM_INVALID = "VALIDATION_CLAIM_INVALID"
    VALIDATION_EVIDENCE_INSUFFICIENT = "VALIDATION_EVIDENCE_INSUFFICIENT"
    VALIDATION_CITATION_BROKEN = "VALIDATION_CITATION_BROKEN"

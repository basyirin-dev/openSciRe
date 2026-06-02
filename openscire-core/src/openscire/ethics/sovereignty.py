from __future__ import annotations

import contextlib
from datetime import datetime
from typing import Any

from openscire.logging import get_logger

from .models import (
    ConsentRestriction,
    DataOrigin,
    ExportRestriction,
    SovereigntyVerdict,
)

logger = get_logger("openscire.ethics.sovereignty")

# ---------------------------------------------------------------------------
# Field-level keyword maps for metadata-driven classification
# ---------------------------------------------------------------------------

ORIGIN_KEYWORDS: dict[DataOrigin, dict[str, list[str]]] = {
    DataOrigin.PUBLIC: {
        "origin": [r"\bpublic\b", r"\bopen\b", r"\bopen[.\- ]?access\b"],
        "license": [r"\bcc0\b", r"\bpublic domain\b", r"\bcc[.\- ]?by\b"],
        "source": [r"\bgov\b", r"\bgovernment\b", r"\bcensus\b"],
    },
    DataOrigin.LICENSED: {
        "origin": [r"\blicensed\b", r"\bcommercial license\b"],
        "license": [
            r"\blicense\b",
            r"\bapi key\b",
            r"\beula\b",
            r"\bterms of use\b",
        ],
        "source": [r"\bdatabase\b", r"\bproprietary api\b"],
    },
    DataOrigin.IRB_APPROVED: {
        "origin": [r"\birb\b", r"\bethics[.\- ]?approved\b"],
        "consent": [
            r"\birb\b",
            r"\binstitutional review\b",
            r"\bethics committee\b",
        ],
        "source": [r"\bclinical trial\b", r"\bstudy protocol\b"],
    },
    DataOrigin.INDIGENOUS: {
        "origin": [
            r"\bindigenous\b",
            r"\btraditional knowledge\b",
            r"\btribal\b",
            r"\bfirst nations\b",
            r"\bnative\b",
        ],
        "consent": [
            r"\bfpic\b",
            r"\bfree prior\b",
            r"\btraditional\b",
            r"\bcultural\b",
        ],
        "source": [
            r"\bindigenous\b",
            r"\btraditional\b",
            r"\bancestral\b",
        ],
    },
    DataOrigin.CLINICAL: {
        "origin": [r"\bclinical\b", r"\bpatient\b", r"\bmedical\b"],
        "consent": [
            r"\bpatient\b",
            r"\bhipaa\b",
            r"\bphi\b",
            r"\bprotected health\b",
        ],
        "source": [
            r"\behr\b",
            r"\belectronic health\b",
            r"\bhospital\b",
            r"\bclinic\b",
        ],
    },
    DataOrigin.PROPRIETARY: {
        "origin": [
            r"\bproprietary\b",
            r"\bconfidential\b",
            r"\binternal\b",
            r"\btrade secret\b",
        ],
        "license": [
            r"\bnda\b",
            r"\bnon[.\- ]?disclosure\b",
            r"\bconfidential\b",
        ],
        "source": [
            r"\bcompany\b",
            r"\bcorporation\b",
            r"\bproprietary\b",
        ],
    },
}

CONSENT_KEYWORDS: dict[ConsentRestriction, list[str]] = {
    ConsentRestriction.NO_ANALYSIS: [
        r"\bno[.\- ]?analysis\b",
        r"\banalysis[.\- ]?restricted\b",
        r"\bdo not analyze\b",
    ],
    ConsentRestriction.NO_SHARING: [
        r"\bno[.\- ]?sharing\b",
        r"\bno[.\- ]?redistribute\b",
        r"\bdo not share\b",
        r"\brestrict(?:ed)? sharing\b",
    ],
    ConsentRestriction.NO_EXPORT: [
        r"\bno[.\- ]?export\b",
        r"\bexport[.\- ]?restricted\b",
        r"\bcross[.\- ]?border\b",
        r"\bdata[.\- ]?localization\b",
    ],
    ConsentRestriction.ATTRIBUTION_REQUIRED: [
        r"\battribution\b",
        r"\bcitation required\b",
        r"\bcredit\b",
        r"\bcite\b",
    ],
    ConsentRestriction.DERIVED_RESTRICTIONS: [
        r"\bderived\b",
        r"\bderivative\b",
        r"\bsecondary use\b",
    ],
    ConsentRestriction.TIME_LIMITED: [
        r"\btime[.\- ]?limited\b",
        r"\bexpir(?:y|ed|es)\b",
        r"\bvalid until\b",
    ],
    ConsentRestriction.PURPOSE_LIMITED: [
        r"\bpurpose[.\- ]?limited\b",
        r"\brestricted use\b",
        r"\bspecific purpose\b",
        r"\bresearch only\b",
    ],
}

EXPORT_KEYWORDS: dict[ExportRestriction, list[str]] = {
    ExportRestriction.GDPR: [
        r"\bgdpr\b",
        r"\bgeneral data protection\b",
        r"\beu data\b",
        r"\beuropean data\b",
    ],
    ExportRestriction.HIPAA: [
        r"\bhipaa\b",
        r"\bprotected health\b",
        r"\bphi\b",
        r"\bhealth insurance portability\b",
    ],
    ExportRestriction.ITAR: [
        r"\bitar\b",
        r"\binternational traffic\b",
        r"\bdefense article\b",
        r"\bmilitary(?:[\- ]?related)?\b",
    ],
    ExportRestriction.SOVEREIGN_DATA: [
        r"\bsovereign\b",
        r"\bnational data\b",
        r"\bdata sovereignty\b",
        r"\bnational security\b",
    ],
}


def _match_field(field_value: str, patterns: list[str]) -> bool:
    """Check if any regex pattern matches the field value (case-insensitive)."""
    import re

    val = str(field_value).lower()
    return any(re.search(pat, val, re.IGNORECASE) for pat in patterns)


def _scan_fields(
    metadata: dict[str, Any],
    field_map: dict[str, list[str]],
) -> bool:
    """Scan metadata for any matching field -> pattern combination."""
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


class ConsentMetadataParser:
    """Static helpers for extracting sovereignty info from metadata dicts."""

    @staticmethod
    def parse_origin(metadata: dict[str, Any]) -> DataOrigin:
        """Classify data origin from metadata fields.

        Checks ``origin``, ``source``, ``license``, ``consent``,
        and ``data_origin`` keys in order of restrictiveness.
        Returns PUBLIC if no pattern matches.
        """
        raw = metadata.get("data_origin") or metadata.get("origin")
        if raw and isinstance(raw, str):
            try:
                return DataOrigin(raw.lower().replace(" ", "_"))
            except ValueError:
                pass

        for origin in (
            DataOrigin.INDIGENOUS,
            DataOrigin.PROPRIETARY,
            DataOrigin.CLINICAL,
            DataOrigin.IRB_APPROVED,
            DataOrigin.LICENSED,
            DataOrigin.PUBLIC,
        ):
            if _scan_fields(metadata, ORIGIN_KEYWORDS[origin]):
                return origin
        return DataOrigin.PUBLIC

    @staticmethod
    def parse_restrictions(
        metadata: dict[str, Any],
    ) -> list[ConsentRestriction]:
        """Extract consent restrictions from metadata."""
        found: list[ConsentRestriction] = []

        restrictions_raw = metadata.get("restrictions") or metadata.get("consent_restrictions")
        if isinstance(restrictions_raw, list):
            for r in restrictions_raw:
                with contextlib.suppress(ValueError):
                    found.append(ConsentRestriction(r.lower().replace(" ", "_")))

        consent_raw = metadata.get("consent") or metadata.get("usage_terms")
        if isinstance(consent_raw, str):
            for restriction, patterns in CONSENT_KEYWORDS.items():
                if restriction not in found and _match_field(consent_raw, patterns):
                    found.append(restriction)

        for restriction, patterns in CONSENT_KEYWORDS.items():
            if restriction not in found and _scan_fields(metadata, {restriction.value: patterns}):
                found.append(restriction)

        return found

    @staticmethod
    def full_parse(metadata: dict[str, Any]) -> dict[str, Any]:
        """Convenience: run all parsers and return a summary dict."""
        return {
            "origin": ConsentMetadataParser.parse_origin(metadata),
            "consent_restrictions": ConsentMetadataParser.parse_restrictions(metadata),
            "export_restrictions": ConsentMetadataParser.detect_export_restrictions(metadata),
        }

    @staticmethod
    def detect_export_restrictions(
        metadata: dict[str, Any],
    ) -> list[ExportRestriction]:
        """Detect cross-border data transfer restrictions."""
        found: list[ExportRestriction] = []

        export_raw = metadata.get("export_restrictions") or metadata.get("jurisdiction")
        if isinstance(export_raw, list):
            for r in export_raw:
                with contextlib.suppress(ValueError):
                    found.append(ExportRestriction(r.lower().replace(" ", "_")))
        elif isinstance(export_raw, str):
            with contextlib.suppress(ValueError):
                found.append(ExportRestriction(export_raw.lower().replace(" ", "_")))

        for restriction, patterns in EXPORT_KEYWORDS.items():
            if restriction not in found and _scan_fields(metadata, {restriction.value: patterns}):
                found.append(restriction)

        return found


class DataSovereigntyChecker:
    """Checks data provenance metadata for sovereignty and consent constraints.

    Inspects structured metadata (dict) for data origin classification,
    consent restrictions, and cross-border export restrictions.  Returns a
    SovereigntyVerdict that the EthicalFirewall enforces.
    """

    def __init__(
        self,
        require_origin: bool = True,
        human_review_origins: list[str] | None = None,
    ) -> None:
        self._require_origin = require_origin
        self._human_review_origins = (
            human_review_origins if human_review_origins else ["indigenous", "clinical"]
        )

    def check(
        self,
        metadata: dict[str, Any],
        provenance_tracker: Any = None,  # noqa: ANN401
    ) -> SovereigntyVerdict:
        """Evaluate data sovereignty for a given metadata context.

        Args:
            metadata: Structured dict with data provenance information.
            provenance_tracker: Optional ProvenanceTracker for audit trail.

        Returns:
            A SovereigntyVerdict with origin, restrictions, export flags,
            and overall approval status.
        """
        verdict_id = __import__("uuid").uuid4().hex[:12]

        origin = ConsentMetadataParser.parse_origin(metadata)
        restrictions = ConsentMetadataParser.parse_restrictions(metadata)
        export = ConsentMetadataParser.detect_export_restrictions(metadata)

        # --- Compute verdict ---
        approved = True
        requires_human_review = False
        summary_parts: list[str] = []

        # 3.3.4: Block analysis if NO_ANALYSIS restriction
        if ConsentRestriction.NO_ANALYSIS in restrictions:
            approved = False
            summary_parts.append("Analysis restricted by consent terms.")

        # 3.3.1: Require origin metadata
        if self._require_origin and origin == DataOrigin.PUBLIC and not metadata.get("origin"):
            if not approved:
                pass
            if restrictions:
                summary_parts.append("Origin metadata missing; classified by restriction context.")
            else:
                approved = False
                summary_parts.append("Data origin not specified and no classification possible.")

        # 3.3.5: Export restriction enforcement
        blocking_exports = {ExportRestriction.ITAR, ExportRestriction.SOVEREIGN_DATA}
        flagged_exports = {ExportRestriction.GDPR, ExportRestriction.HIPAA}
        has_blocking = set(export) & blocking_exports
        has_flagged = set(export) & flagged_exports

        if has_blocking:
            approved = False
            names = ", ".join(e.value for e in has_blocking)
            summary_parts.append(f"Export blocked: {names} restricts cross-border transfer.")

        if has_flagged:
            names = ", ".join(e.value for e in has_flagged)
            summary_parts.append(f"Export flagged: {names} may restrict cross-border transfer.")

        # 3.3.2: Human review for sensitive origins
        if origin.value in self._human_review_origins:
            has_consent = any(
                r
                for r in restrictions
                if r
                in (
                    ConsentRestriction.ATTRIBUTION_REQUIRED,
                    ConsentRestriction.PURPOSE_LIMITED,
                )
            )
            if not has_consent:
                requires_human_review = True
                summary_parts.append(
                    f"Human review required: {origin.value} data without explicit consent."
                )

        summary = " ".join(summary_parts) if summary_parts else "No restrictions detected."

        # Provenance tracking
        if provenance_tracker is not None:
            try:
                provenance_tracker.track(
                    action_type="data_sovereignty_check",
                    params={
                        "verdict_id": verdict_id,
                        "data_origin": origin.value,
                        "consent_restrictions": [r.value for r in restrictions],
                        "export_restrictions": [e.value for e in export],
                        "approved": approved,
                        "requires_human_review": requires_human_review,
                    },
                )
            except Exception:
                logger.warning("Failed to track sovereignty check provenance", exc_info=True)

        return SovereigntyVerdict(
            verdict_id=verdict_id,
            data_origin=origin,
            consent_restrictions=restrictions,
            export_restrictions=export,
            approved=approved,
            requires_human_review=requires_human_review,
            restriction_summary=summary,
            timestamp=datetime.now(),
        )

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from openscire.constants import ErrorCode
from openscire.exceptions import ValidationError
from openscire.logging import get_logger

from .models import (
    AsymmetryRecord,
    Source,
    SourceVerification,
    SourceVerificationStatus,
    VerifiabilityCategory,
    VerificationAsymmetryReport,
    VerificationPath,
    VerificationStatus,
)

logger = get_logger("openscire.ethics.verification_asymmetry")

# ---------------------------------------------------------------------------
# Verification score mapping
# ---------------------------------------------------------------------------

_VERIFICATION_SCORE_MAP: dict[SourceVerificationStatus, float] = {
    SourceVerificationStatus.VERIFIED: 0.9,
    SourceVerificationStatus.AMBIGUOUS: 0.4,
    SourceVerificationStatus.NOT_FOUND: 0.0,
    SourceVerificationStatus.RETRACTED: -0.5,
}

# ---------------------------------------------------------------------------
# Speculative and untestable language patterns
# ---------------------------------------------------------------------------

_SPECULATIVE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bmight\b"),
    re.compile(r"\bcould\b"),
    re.compile(r"\bpossibly\b"),
    re.compile(r"\bperhaps\b"),
    re.compile(r"\bconceivably\b"),
    re.compile(r"\bit is tempting to\b"),
    re.compile(r"\bwe speculate\b"),
    re.compile(r"\bwe hypothesize\b"),
    re.compile(r"\bmay indicate\b"),
    re.compile(r"\bwould suggest\b"),
]

_UNTESTABLE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bunobservable\b"),
    re.compile(r"\bmetaphysical\b"),
    re.compile(r"\bunknowable\b"),
    re.compile(r"\bin principle impossible\b"),
    re.compile(r"\boutside the scope of science\b"),
    re.compile(r"\bpurely theoretical\b"),
    re.compile(r"\bno known experiment\b"),
]

# ---------------------------------------------------------------------------
# Domain keyword → verification path mapping
# ---------------------------------------------------------------------------

_VERIFICATION_PATH_MAP: dict[str, list[dict[str, str]]] = {
    "gene": [
        {"approach": "RNA-seq transcriptomic analysis", "estimate": "1-4 weeks, moderate cost"},
        {"approach": "qPCR validation", "estimate": "1-2 weeks, low cost"},
        {"approach": "CRISPR knockout experiment", "estimate": "4-8 weeks, moderate cost"},
    ],
    "expression": [
        {"approach": "Transcriptomic profiling", "estimate": "2-4 weeks, moderate cost"},
        {"approach": "RT-qPCR quantification", "estimate": "1-2 weeks, low cost"},
        {"approach": "Reporter gene assay", "estimate": "2-4 weeks, moderate cost"},
    ],
    "protein": [
        {"approach": "Western blot analysis", "estimate": "1-2 weeks, low cost"},
        {"approach": "Co-immunoprecipitation", "estimate": "2-3 weeks, moderate cost"},
        {"approach": "Mass spectrometry", "estimate": "2-4 weeks, high cost"},
    ],
    "binding": [
        {"approach": "Surface plasmon resonance", "estimate": "1-2 weeks, high cost"},
        {"approach": "Isothermal titration calorimetry", "estimate": "1-2 weeks, high cost"},
        {"approach": "Fluorescence polarization assay", "estimate": "1-2 weeks, moderate cost"},
    ],
    "climate": [
        {"approach": "Historical data cross-validation", "estimate": "2-4 weeks, low cost"},
        {"approach": "Climate model ensemble comparison", "estimate": "4-8 weeks, high cost"},
        {"approach": "Proxy data verification", "estimate": "4-12 weeks, moderate cost"},
    ],
    "cell": [
        {"approach": "Cell culture viability assay", "estimate": "1-3 weeks, low cost"},
        {"approach": "Flow cytometry analysis", "estimate": "1-2 weeks, moderate cost"},
        {"approach": "Fluorescence microscopy", "estimate": "1-3 weeks, moderate cost"},
    ],
    "drug": [
        {"approach": "In vitro efficacy assay", "estimate": "2-4 weeks, moderate cost"},
        {"approach": "ADME-Tox profiling", "estimate": "4-8 weeks, high cost"},
        {"approach": "Clinical trial data review", "estimate": "variable, high cost"},
    ],
    "mutation": [
        {"approach": "Site-directed mutagenesis", "estimate": "2-4 weeks, low cost"},
        {"approach": "Deep mutational scanning", "estimate": "4-8 weeks, high cost"},
        {"approach": "Complementation assay", "estimate": "2-4 weeks, moderate cost"},
    ],
    "structure": [
        {"approach": "X-ray crystallography", "estimate": "4-12 weeks, high cost"},
        {"approach": "Cryo-electron microscopy", "estimate": "4-12 weeks, high cost"},
        {"approach": "NMR spectroscopy", "estimate": "4-8 weeks, high cost"},
    ],
    "computational": [
        {"approach": "Cross-validation on held-out data", "estimate": "1-3 days, low cost"},
        {"approach": "Benchmark against known dataset", "estimate": "1-2 weeks, low cost"},
        {"approach": "Ablation study", "estimate": "1-3 weeks, low cost"},
    ],
    "neuronal": [
        {"approach": "Electrophysiological recording", "estimate": "4-8 weeks, high cost"},
        {"approach": "Calcium imaging", "estimate": "4-8 weeks, high cost"},
        {"approach": "Optogenetic manipulation", "estimate": "8-12 weeks, high cost"},
    ],
    "signaling": [
        {"approach": "Phospho-specific western blot", "estimate": "1-2 weeks, low cost"},
        {"approach": "Kinase activity assay", "estimate": "1-2 weeks, moderate cost"},
        {"approach": "Reporter pathway assay", "estimate": "2-4 weeks, moderate cost"},
    ],
    "network": [
        {"approach": "Graph theoretical analysis", "estimate": "1-2 weeks, low cost"},
        {"approach": "Perturbation experiment", "estimate": "4-8 weeks, high cost"},
        {"approach": "Simulation validation", "estimate": "1-4 weeks, low cost"},
    ],
}

_GENERIC_PATHS: dict[VerifiabilityCategory, list[dict[str, str]]] = {
    VerifiabilityCategory.VERIFIABLE: [
        {
            "approach": "Design confirmatory experiment to validate the specific claim",
            "estimate": "variable",
        },
    ],
    VerifiabilityCategory.PARTIALLY_VERIFIABLE: [
        {
            "approach": "Systematic literature review to identify supporting evidence",
            "estimate": "2-4 weeks, low cost",
        },
        {"approach": "Meta-analysis of existing datasets", "estimate": "4-8 weeks, moderate cost"},
    ],
    VerifiabilityCategory.NON_VERIFIABLE: [
        {
            "approach": "Reformulate as a testable hypothesis with measurable outcomes",
            "estimate": "variable",
        },
        {
            "approach": "Identify proxy measurements or indirect evidence sources",
            "estimate": "2-4 weeks, low cost",
        },
    ],
}

# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def compute_asymmetry_gap(
    confidence_score: float,
    verifications: list[SourceVerification],
) -> float:
    """Compute the gap between claimed confidence and evidence strength.

    Args:
        confidence_score: The claim's confidence score (0-1).
        verifications: Source verification results.

    Returns:
        The asymmetry gap (confidence - max verification score).
        Negative values mean the evidence is stronger than the claim's confidence.
    """
    if not verifications:
        return confidence_score

    max_score = max(_VERIFICATION_SCORE_MAP.get(v.status, 0.0) for v in verifications)
    return confidence_score - max_score


def compute_max_verification_score(
    verifications: list[SourceVerification],
) -> float:
    """Compute the maximum verification score across all sources.

    Args:
        verifications: Source verification results.

    Returns:
        The maximum verification score (0.0 if no verifications).
    """
    if not verifications:
        return 0.0
    return max(_VERIFICATION_SCORE_MAP.get(v.status, 0.0) for v in verifications)


def _has_speculative_language(text: str) -> bool:
    return any(p.search(text) for p in _SPECULATIVE_PATTERNS)


def _has_untestable_language(text: str) -> bool:
    return any(p.search(text) for p in _UNTESTABLE_PATTERNS)


def _matches_any_domain(text: str) -> bool:
    lower = text.lower()
    return any(keyword in lower for keyword in _VERIFICATION_PATH_MAP)


def categorize_claim(
    claim_text: str,
    verifications: list[SourceVerification] | None = None,
    confidence_score: float = 0.0,
) -> tuple[VerifiabilityCategory, str]:
    """Classify a claim into a verifiability category.

    Args:
        claim_text: The claim text to classify.
        verifications: Source verification results (optional).
        confidence_score: The claim's confidence score (0-1).

    Returns:
        A tuple of (VerifiabilityCategory, reason string).
    """
    verifications = verifications or []

    if not claim_text.strip():
        return (VerifiabilityCategory.NON_VERIFIABLE, "Empty claim text.")

    if _has_untestable_language(claim_text):
        return (
            VerifiabilityCategory.NON_VERIFIABLE,
            "Claim contains language suggesting it is untestable in principle.",
        )

    has_verified = any(v.status == SourceVerificationStatus.VERIFIED for v in verifications)
    has_ambiguous = any(v.status == SourceVerificationStatus.AMBIGUOUS for v in verifications)
    has_not_found = any(v.status == SourceVerificationStatus.NOT_FOUND for v in verifications)
    has_retracted = any(v.status == SourceVerificationStatus.RETRACTED for v in verifications)

    if has_retracted:
        return (VerifiabilityCategory.NON_VERIFIABLE, "Claim depends on retracted sources.")

    if has_verified and not has_not_found and not has_ambiguous:
        gap = compute_asymmetry_gap(confidence_score, verifications)
        if gap <= 0.4:
            return (
                VerifiabilityCategory.VERIFIABLE,
                "Claim is supported by verified sources with consistent confidence.",
            )
        return (
            VerifiabilityCategory.PARTIALLY_VERIFIABLE,
            "Claim has verified sources but confidence exceeds evidence strength.",
        )

    if has_verified and (has_not_found or has_ambiguous):
        return (
            VerifiabilityCategory.PARTIALLY_VERIFIABLE,
            "Claim has some verified sources but also unverifiable citations.",
        )

    if verifications and not has_verified:
        return (
            VerifiabilityCategory.PARTIALLY_VERIFIABLE,
            "Claim has citations but none could be verified against known sources.",
        )

    if _has_speculative_language(claim_text):
        return (
            VerifiabilityCategory.NON_VERIFIABLE,
            "Claim uses speculative language without verified evidence.",
        )

    if not verifications and not _matches_any_domain(claim_text):
        return (
            VerifiabilityCategory.NON_VERIFIABLE,
            "No citations or known sources; claim falls outside tracked domains.",
        )

    return (
        VerifiabilityCategory.PARTIALLY_VERIFIABLE,
        "No direct evidence but claim is within a known research domain.",
    )


def suggest_verification(
    claim_text: str,
    category: VerifiabilityCategory = VerifiabilityCategory.VERIFIABLE,
) -> list[VerificationPath]:
    """Suggest verification approaches based on claim content and category.

    Args:
        claim_text: The claim text to analyze.
        category: The verifiability category of the claim.

    Returns:
        A list of VerificationPath suggestions.
    """
    lower = claim_text.lower()
    matched: list[VerificationPath] = []

    for keyword, approaches in _VERIFICATION_PATH_MAP.items():
        if keyword in lower:
            for ap in approaches:
                matched.append(
                    VerificationPath(
                        approach=ap["approach"],
                        resource_estimate=ap["estimate"],
                        feasibility=0.7 if category == VerifiabilityCategory.VERIFIABLE else 0.4,
                        category=category,
                    )
                )

    if matched:
        return matched[:3]

    generics = _GENERIC_PATHS.get(
        category, _GENERIC_PATHS[VerifiabilityCategory.PARTIALLY_VERIFIABLE]
    )
    return [
        VerificationPath(
            approach=g["approach"],
            resource_estimate=g["estimate"],
            feasibility=0.5,
            category=category,
        )
        for g in generics
    ]


# ---------------------------------------------------------------------------
# VerificationAsymmetryTracker
# ---------------------------------------------------------------------------


class VerificationAsymmetryTracker:
    """Tracks verification asymmetry across claims over time.

    Classifies claims by verifiability, computes the gap between claimed
    confidence and evidence strength, persists records for temporal
    re-evaluation, and suggests verification approaches.

    Not injected into EthicalFirewall — consumed by CLI/API layer as a
    reporting and analysis tool (same pattern as UncertaintyQuantifier).
    """

    def __init__(
        self,
        db_path: str = "data/verification_asymmetry.db",
        max_asymmetry_gap: float = 0.4,
        require_citation_verification: bool = True,
        provenance_tracker: Any = None,  # noqa: ANN401
    ) -> None:
        self._max_asymmetry_gap = max_asymmetry_gap
        self._require_citation_verification = require_citation_verification
        self._provenance_tracker = provenance_tracker

        self._db_path = str(Path(db_path).resolve())
        self._init_db()

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        db_dir = Path(self._db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS asymmetry_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id TEXT NOT NULL,
                    claim_hash TEXT NOT NULL,
                    claim_text TEXT NOT NULL,
                    category TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'unchecked',
                    confidence_score REAL DEFAULT 0.0,
                    asymmetry_gap REAL DEFAULT 0.0,
                    max_verification_score REAL DEFAULT 0.0,
                    reason TEXT DEFAULT '',
                    verification_paths TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_claim_hash ON asymmetry_records(claim_hash)"
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _claim_hash(claim_text: str) -> str:
        return hashlib.sha256(claim_text.encode()).hexdigest()

    def _insert_record(self, record: AsymmetryRecord) -> int:
        conn = sqlite3.connect(self._db_path)
        try:
            paths_json = json.dumps(
                [
                    {
                        "approach": p.approach,
                        "feasibility": p.feasibility,
                        "resource_estimate": p.resource_estimate,
                        "category": p.category.value,
                    }
                    for p in record.verification_paths
                ]
            )
            cur = conn.execute(
                """
                INSERT INTO asymmetry_records
                    (record_id, claim_hash, claim_text, category, status,
                     confidence_score, asymmetry_gap, max_verification_score,
                     reason, verification_paths, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex[:12],
                    record.claim_hash,
                    record.claim_text[:2000],
                    record.category.value,
                    record.status.value,
                    record.confidence_score,
                    record.asymmetry_gap,
                    record.max_verification_score,
                    "",
                    paths_json,
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                ),
            )
            conn.commit()
            return cur.lastrowid or 0
        finally:
            conn.close()

    def _find_records(self, claim_hash: str) -> list[AsymmetryRecord]:
        conn = sqlite3.connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM asymmetry_records WHERE claim_hash = ? ORDER BY id",
                (claim_hash,),
            ).fetchall()
            return [self._row_to_record(r) for r in rows]
        finally:
            conn.close()

    def _all_records(self) -> list[AsymmetryRecord]:
        conn = sqlite3.connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM asymmetry_records WHERE id IN "
                "(SELECT MAX(id) FROM asymmetry_records GROUP BY claim_hash) "
                "ORDER BY id"
            ).fetchall()
            return [self._row_to_record(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def _row_to_record(row: sqlite3.Row | tuple) -> AsymmetryRecord:
        if isinstance(row, tuple):
            return AsymmetryRecord(
                claim_hash=row[2],
                claim_text=row[3],
                category=VerifiabilityCategory(row[4]),
                status=VerificationStatus(row[5]),
                confidence_score=float(row[6]),
                asymmetry_gap=float(row[7]),
                max_verification_score=float(row[8]),
                created_at=datetime.fromisoformat(row[11]),
                updated_at=datetime.fromisoformat(row[12]),
                db_id=row[0],
            )
        return AsymmetryRecord(
            claim_hash=row["claim_hash"],
            claim_text=row["claim_text"],
            category=VerifiabilityCategory(row["category"]),
            status=VerificationStatus(row["status"]),
            confidence_score=float(row["confidence_score"]),
            asymmetry_gap=float(row["asymmetry_gap"]),
            max_verification_score=float(row["max_verification_score"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            db_id=row["id"],
        )

    # ------------------------------------------------------------------
    # Public API — 3.8.1: Claim categorization
    # ------------------------------------------------------------------

    def categorize_claim(
        self,
        claim_text: str,
        verifications: list[SourceVerification] | None = None,
        confidence_score: float = 0.0,
        sources: list[Source] | None = None,
    ) -> AsymmetryRecord:
        """Classify a claim and record its verification asymmetry.

        Args:
            claim_text: The claim text.
            verifications: Source verification results.
            confidence_score: Model confidence in the claim (0-1).
            sources: Known sources (used for verification path suggestions).

        Returns:
            An AsymmetryRecord with category, gap, and suggested paths.
        """
        _ = sources
        claim_hash = self._claim_hash(claim_text)
        now = datetime.now()

        category, _ = categorize_claim(
            claim_text,
            verifications,
            confidence_score,
        )

        gap = compute_asymmetry_gap(
            confidence_score,
            verifications or [],
        )
        max_score = compute_max_verification_score(verifications or [])

        paths = suggest_verification(claim_text, category)

        record = AsymmetryRecord(
            claim_hash=claim_hash,
            claim_text=claim_text[:2000],
            category=category,
            status=(
                VerificationStatus.CONFIRMED
                if category == VerifiabilityCategory.VERIFIABLE
                else VerificationStatus.UNRESOLVED
            ),
            confidence_score=confidence_score,
            asymmetry_gap=gap,
            max_verification_score=max_score,
            verification_paths=paths,
            created_at=now,
            updated_at=now,
        )

        record.db_id = self._insert_record(record)

        if self._provenance_tracker is not None:
            import contextlib

            with contextlib.suppress(Exception):
                self._provenance_tracker.track(
                    action_type="verification_asymmetry",
                    params={
                        "claim_hash": claim_hash,
                        "category": category.value,
                        "asymmetry_gap": gap,
                        "confidence_score": confidence_score,
                    },
                )

        return record

    # ------------------------------------------------------------------
    # Public API — 3.8.2: Track over time
    # ------------------------------------------------------------------

    def re_evaluate(
        self,
        claim_text: str,
        verifications: list[SourceVerification] | None = None,
        confidence_score: float | None = None,
    ) -> AsymmetryRecord:
        """Re-evaluate a previously tracked claim with new evidence.

        Inserts a new record (append-only history) with updated category
        and status reflecting the new evidence.

        Args:
            claim_text: The claim text (matched by hash).
            verifications: New source verification results.
            confidence_score: Updated confidence score (None = keep previous).

        Returns:
            The new AsymmetryRecord.
        """
        claim_hash = self._claim_hash(claim_text)
        previous = self._find_records(claim_hash)
        prev_score = previous[-1].confidence_score if previous else 0.0
        prev_category = previous[-1].category if previous else VerifiabilityCategory.NON_VERIFIABLE

        score = confidence_score if confidence_score is not None else prev_score

        category, _ = categorize_claim(claim_text, verifications or [], score)
        gap = compute_asymmetry_gap(score, verifications or [])
        max_score = compute_max_verification_score(verifications or [])

        paths = suggest_verification(claim_text, category)
        now = datetime.now()

        status = VerificationStatus.UNRESOLVED
        if previous and category != prev_category:
            status = VerificationStatus.REVISED
        elif category == VerifiabilityCategory.VERIFIABLE:
            status = VerificationStatus.CONFIRMED
        elif previous:
            status = VerificationStatus.IN_PROGRESS

        record = AsymmetryRecord(
            claim_hash=claim_hash,
            claim_text=claim_text[:2000],
            category=category,
            status=status,
            confidence_score=score,
            asymmetry_gap=gap,
            max_verification_score=max_score,
            verification_paths=paths,
            created_at=now,
            updated_at=now,
        )
        record.db_id = self._insert_record(record)
        return record

    def get_claim_history(
        self,
        claim_text: str,
    ) -> list[AsymmetryRecord]:
        """Return all historical evaluations for a claim.

        Args:
            claim_text: The claim text.

        Returns:
            Chronological list of AsymmetryRecords.
        """
        claim_hash = self._claim_hash(claim_text)
        return self._find_records(claim_hash)

    # ------------------------------------------------------------------
    # Public API — 3.8.3: Gap reporting
    # ------------------------------------------------------------------

    def build_report(self) -> VerificationAsymmetryReport:
        """Aggregate verification asymmetry statistics across tracked claims.

        Returns:
            A VerificationAsymmetryReport with category breakdown,
            verification rate, and gap statistics.
        """
        records = self._all_records()
        total = len(records)

        if total == 0:
            return VerificationAsymmetryReport()

        n_verifiable = sum(1 for r in records if r.category == VerifiabilityCategory.VERIFIABLE)
        n_partial = sum(
            1 for r in records if r.category == VerifiabilityCategory.PARTIALLY_VERIFIABLE
        )
        n_non = sum(1 for r in records if r.category == VerifiabilityCategory.NON_VERIFIABLE)

        gaps = [r.asymmetry_gap for r in records]
        avg_gap = sum(gaps) / len(gaps) if gaps else 0.0
        max_gap = max(gaps) if gaps else 0.0

        return VerificationAsymmetryReport(
            total_claims=total,
            n_verifiable=n_verifiable,
            n_partially_verifiable=n_partial,
            n_non_verifiable=n_non,
            verification_rate=(n_verifiable / total * 100.0) if total > 0 else 0.0,
            avg_asymmetry_gap=avg_gap,
            max_asymmetry_gap=max_gap,
            claims_by_category={
                VerifiabilityCategory.VERIFIABLE.value: n_verifiable,
                VerifiabilityCategory.PARTIALLY_VERIFIABLE.value: n_partial,
                VerifiabilityCategory.NON_VERIFIABLE.value: n_non,
            },
        )

    # ------------------------------------------------------------------
    # Public API — 3.8.4: Verification path suggestions
    # ------------------------------------------------------------------

    def suggest_verification(
        self,
        claim_text: str,
        category: VerifiabilityCategory = VerifiabilityCategory.VERIFIABLE,
    ) -> list[VerificationPath]:
        """Suggest verification approaches for a claim.

        Args:
            claim_text: The claim text.
            category: The verifiability category.

        Returns:
            List of VerificationPath suggestions.
        """
        return suggest_verification(claim_text, category)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def raise_if_asymmetric(self, record: AsymmetryRecord) -> None:
        """Raise ValidationError if asymmetry gap exceeds the threshold.

        Args:
            record: The AsymmetryRecord to check.

        Raises:
            ValidationError: If asymmetry_gap > max_asymmetry_gap.
        """
        if record.asymmetry_gap > self._max_asymmetry_gap:
            raise ValidationError(
                message=(
                    f"Verification asymmetry detected: confidence score "
                    f"{record.confidence_score:.2f} exceeds verification score "
                    f"by {record.asymmetry_gap:.2f} "
                    f"(threshold: {self._max_asymmetry_gap:.2f}). "
                    f"Claim: {record.claim_text[:100]}"
                ),
                source="verification_asymmetry.raise_if_asymmetric",
                error_code=ErrorCode.VALIDATION_ASYMMETRY_DETECTED,
            )

    def reset(self) -> None:
        """Clear all records (for testing)."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("DELETE FROM asymmetry_records")
            conn.commit()
        finally:
            conn.close()

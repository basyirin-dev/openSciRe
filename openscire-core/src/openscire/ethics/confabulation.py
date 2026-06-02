from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from openscire.constants import ErrorCode
from openscire.exceptions import ValidationError
from openscire.logging import get_logger
from openscire.models.philosophy import BoundaryCategory, KnowledgeBoundaryFlag
from openscire.quantification.contradiction import ContradictionDetector
from openscire.quantification.models import ClaimConfidence, Contradiction

from .models import (
    ConfabulationFlag,
    ConfabulationReport,
    ConfabulationType,
    HallucinationRecord,
    Source,
)

logger = get_logger("openscire.ethics.confabulation")

# ---------------------------------------------------------------------------
# Sentence extraction (mirrors source_grounding._extract_claim_sentences)
# ---------------------------------------------------------------------------

_FACTUAL_PATTERN = re.compile(r"^[A-Z].+[.?!]$")


def _extract_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    for part in re.split(r"[.?!]\s+", text):
        part = part.strip()
        if not part or len(part) < 15:
            continue
        candidate = part if part.endswith((".", "!", "?")) else part + "."
        if _FACTUAL_PATTERN.match(candidate):
            sentences.append(part)
    return sentences


# ---------------------------------------------------------------------------
# Jaccard overlap helper
# ---------------------------------------------------------------------------

_NEGATION_MARKERS: set[str] = {
    "not",
    "no",
    "never",
    "neither",
    "nor",
    "cannot",
    "can't",
    "doesn't",
    "don't",
    "didn't",
    "won't",
    "wouldn't",
    "shouldn't",
    "isn't",
    "aren't",
    "wasn't",
    "weren't",
    "hasn't",
    "haven't",
    "hadn't",
    "does not",
    "do not",
    "did not",
    "will not",
    "would not",
    "should not",
    "is not",
    "are not",
    "was not",
    "were not",
    "has not",
    "have not",
    "had not",
    "fails to",
    "lack of",
    "absence of",
}


_STOPWORDS: set[str] = {
    "the",
    "and",
    "in",
    "is",
    "with",
    "to",
    "of",
    "for",
    "on",
    "are",
    "has",
    "have",
    "been",
    "were",
    "was",
    "be",
    "a",
    "an",
    "or",
    "but",
    "not",
    "by",
    "at",
    "from",
    "as",
    "it",
    "that",
    "this",
    "which",
    "these",
    "those",
    "its",
    "their",
    "our",
    "we",
    "they",
    "can",
    "may",
}


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower())) - _STOPWORDS


def _has_negation(text: str) -> bool:
    words = text.lower().split()
    word_set = set(words)
    for marker in _NEGATION_MARKERS:
        if " " in marker:
            if marker in text.lower():
                return True
        elif marker in word_set:
            return True
    return False


def _jaccard(text_a: str, text_b: str) -> float:
    tokens_a = _tokenize(text_a)
    tokens_b = _tokenize(text_b)
    union = tokens_a | tokens_b
    if not union:
        return 0.0
    overlap = len(tokens_a & tokens_b)
    return overlap / len(union)


def _max_jaccard_against_sources(claim_text: str, sources: list[Source]) -> float:
    """Return the maximum Jaccard overlap between claim and any source abstract."""
    if not sources:
        return 0.0
    best = 0.0
    for src in sources:
        src_text = f"{src.title} {src.abstract}"
        score = _jaccard(claim_text, src_text)
        if score > best:
            best = score
    return best


def _find_contradictory_source(
    claim_text: str,
    sources: list[Source],
    threshold: float = 0.3,
) -> str:
    """Return the first source abstract that contradicts the claim."""
    for src in sources:
        src_text = f"{src.title} {src.abstract}"
        score = _jaccard(claim_text, src_text)
        if score > threshold and _has_negation(claim_text) != _has_negation(src_text):
            return src_text[:200]
    return ""


def _recommend_action(severity: float) -> str:
    if severity < 0.3:
        return "retry"
    if severity < 0.7:
        return "escalate"
    return "discard"


def _doc_id() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# ConfabulationDetector
# ---------------------------------------------------------------------------


class ConfabulationDetector:
    """Detects confabulations across agent outputs.

    Two detection passes:
      1. Claim-vs-Claim — delegates to ContradictionDetector to find
         contradictory statements within the output.
      2. Claim-vs-Literature — compares each claim against known Source
         abstracts using Jaccard overlap; flags claims with no support
         or direct contradiction.

    Historical hallucination tracking via SQLite enables per-domain
    flag-rate monitoring and auto-escalation.

    Not injected into EthicalFirewall — consumed by CLI/API layer as a
    post-generation analysis pass (same pattern as UncertaintyQuantifier
    and VerificationAsymmetryTracker).
    """

    def __init__(
        self,
        claim_vs_literature_threshold: float = 0.05,
        boundary_confidence_threshold: float = 0.3,
        domain_hallucination_threshold: float = 0.15,
        db_path: str = "data/confabulation.db",
        contradiction_detector: ContradictionDetector | None = None,
    ) -> None:
        self._literature_threshold = claim_vs_literature_threshold
        self._boundary_threshold = boundary_confidence_threshold
        self._domain_threshold = domain_hallucination_threshold
        self._db_path = str(Path(db_path).resolve())
        self._contradiction_detector = contradiction_detector or ContradictionDetector()

        self._init_db()

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS hallucination_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain TEXT NOT NULL,
                    claim_hash TEXT NOT NULL,
                    flag_type TEXT NOT NULL,
                    severity REAL DEFAULT 0.0,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_hallucination_domain "
                "ON hallucination_records(domain)"
            )
            conn.commit()
        finally:
            conn.close()

    def record_flag(
        self,
        domain: str,
        flag: ConfabulationFlag,
    ) -> None:
        """Persist a hallucination flag to the historical tracking DB.

        Args:
            domain: The domain/topic of the claim.
            flag: The confabulation flag to record.
        """
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                """
                INSERT INTO hallucination_records
                    (domain, claim_hash, flag_type, severity, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    domain[:100],
                    _doc_id(),
                    flag.flag_type.value,
                    flag.severity,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_domain_stats(self, domain: str) -> HallucinationRecord:
        """Compute hallucination statistics for a domain.

        Args:
            domain: The domain to query.

        Returns:
            A HallucinationRecord with flag count, rate, and breakdown by type.
        """
        conn = sqlite3.connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT flag_type, COUNT(*) as cnt FROM hallucination_records "
                "WHERE domain = ? GROUP BY flag_type",
                (domain,),
            ).fetchall()
        finally:
            conn.close()

        total_flags = sum(r[1] for r in rows)
        by_type = {r[0]: r[1] for r in rows}

        return HallucinationRecord(
            domain=domain,
            n_flags=total_flags,
            flag_rate=0.0,
            by_type=by_type,
        )

    def _count_total_domain_claims(self, domain: str) -> int:
        conn = sqlite3.connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM hallucination_records WHERE domain = ?",
                (domain,),
            ).fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Pass 1 — Claim-vs-Claim via ContradictionDetector
    # ------------------------------------------------------------------

    def _detect_claim_contradictions(
        self,
        claim_texts: list[str],
        confidences: list[ClaimConfidence] | None,
    ) -> list[Contradiction]:
        if len(claim_texts) < 2:
            return []

        claims = confidences or [ClaimConfidence(claim_text=t) for t in claim_texts]
        return self._contradiction_detector.detect(claims)

    # ------------------------------------------------------------------
    # Pass 2 — Claim-vs-Literature
    # ------------------------------------------------------------------

    def _detect_literature_confabulations(
        self,
        claim_texts: list[str],
        sources: list[Source] | None,
        confidences: list[ClaimConfidence] | None,
    ) -> list[ConfabulationFlag]:
        sources = sources or []
        confidences_map: dict[str, float] = {}
        if confidences:
            for c in confidences:
                confidences_map[c.claim_text] = c.confidence_score

        flags: list[ConfabulationFlag] = []

        for text in claim_texts:
            confidence = confidences_map.get(text, 0.0)
            sentences = _extract_sentences(text) or [text]

            for sentence in sentences:
                max_j = _max_jaccard_against_sources(sentence, sources)
                contradictory = _find_contradictory_source(sentence, sources)

                if contradictory:
                    severity = min(1.0, max_j * 1.5) if max_j > 0 else 0.7
                    flags.append(
                        ConfabulationFlag(
                            claim_text=sentence,
                            flag_type=ConfabulationType.CONTRADICTS_LITERATURE,
                            severity=round(severity, 4),
                            contradicted_by=contradictory,
                            confidence=confidence,
                            recommended_action=_recommend_action(severity),
                        )
                    )
                elif max_j < self._literature_threshold:
                    severity = max(0.0, 1.0 - max_j * 5)
                    flags.append(
                        ConfabulationFlag(
                            claim_text=sentence,
                            flag_type=ConfabulationType.NO_LITERATURE_SUPPORT,
                            severity=round(severity, 4),
                            confidence=confidence,
                            recommended_action=_recommend_action(severity),
                        )
                    )

        return flags

    # ------------------------------------------------------------------
    # Knowledge boundary flagging (3.9.3)
    # ------------------------------------------------------------------

    def _flag_boundaries(
        self,
        flags: list[ConfabulationFlag],
        confidences: list[ClaimConfidence] | None,
    ) -> list[KnowledgeBoundaryFlag]:
        boundaries: list[KnowledgeBoundaryFlag] = []
        conf_map: dict[str, float] = {}
        if confidences:
            for c in confidences:
                conf_map[c.claim_text] = c.confidence_score

        for flag in flags:
            conf = conf_map.get(flag.claim_text, flag.confidence)
            if conf < self._boundary_threshold:
                boundaries.append(
                    KnowledgeBoundaryFlag(
                        category=BoundaryCategory.confabulation_suspected,
                        query=flag.claim_text[:200],
                        confidence=max(0.0, 1.0 - conf),
                        threshold=self._boundary_threshold,
                        detail=(
                            f"Confidence {conf:.2f} below boundary threshold "
                            f"{self._boundary_threshold}. "
                            f"Flag type: {flag.flag_type.value}"
                        ),
                    )
                )

        return boundaries

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def check_claims(
        self,
        claim_texts: list[str],
        sources: list[Source] | None = None,
        claim_confidences: list[ClaimConfidence] | None = None,
        domain: str = "",
    ) -> ConfabulationReport:
        """Run full confabulation detection on a set of claims.

        Args:
            claim_texts: The generated claim texts to analyze.
            sources: Known literature sources for comparison.
            claim_confidences: Optional confidence scores per claim.
            domain: Domain/topic for hallucination tracking.

        Returns:
            A ConfabulationReport with flags, contradictions, boundaries,
            and hallucination stats.
        """
        sources = sources or []

        # Pass 1: claim-vs-claim
        contradictions = self._detect_claim_contradictions(
            claim_texts,
            claim_confidences,
        )

        # Pass 2: claim-vs-literature
        lit_flags = self._detect_literature_confabulations(
            claim_texts,
            sources,
            claim_confidences,
        )

        # Merge: contradiction flags
        contradiction_flags: list[ConfabulationFlag] = []
        for c in contradictions:
            contradiction_flags.append(
                ConfabulationFlag(
                    claim_text=c.claim_a[:200],
                    flag_type=ConfabulationType.CONTRADICTS_CLAIM,
                    severity=round(c.severity, 4),
                    contradicted_by=c.claim_b[:200],
                    confidence=min(c.confidence_a, c.confidence_b),
                    recommended_action=_recommend_action(c.severity),
                )
            )

        all_flags = contradiction_flags + lit_flags
        n_flagged = len(all_flags)

        # Knowledge boundaries
        boundaries = self._flag_boundaries(all_flags, claim_confidences)

        # Hallucination stats + auto-escalation
        hallucination_stats = HallucinationRecord(domain=domain)
        auto_escalated = False

        if domain and all_flags:
            for flag in all_flags:
                self.record_flag(domain, flag)

            total = self._count_total_domain_claims(domain)
            stats = self.get_domain_stats(domain)
            rate = stats.n_flags / total if total > 0 else 0.0

            hallucination_stats = HallucinationRecord(
                domain=domain,
                total_claims=total,
                n_flags=stats.n_flags,
                flag_rate=round(rate, 4),
                auto_escalated=rate > self._domain_threshold,
                by_type=stats.by_type,
            )
            auto_escalated = rate > self._domain_threshold

        if n_flagged > 0:
            logger.info(
                "Confabulation detection complete",
                n_flagged=n_flagged,
                n_contradictions=len(contradictions),
                n_boundaries=len(boundaries),
                auto_escalated=auto_escalated,
                domain=domain,
            )

        return ConfabulationReport(
            total_claims=len(claim_texts),
            n_flagged=n_flagged,
            flags=all_flags,
            contradictions=contradictions,
            boundaries=boundaries,
            hallucination_stats=hallucination_stats,
            auto_escalated=auto_escalated,
            domain=domain,
        )

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def raise_if_confabulation(self, report: ConfabulationReport) -> None:
        """Raise ValidationError if confabulations were detected.

        Args:
            report: The ConfabulationReport to check.

        Raises:
            ValidationError: If the report has any flagged claims.
        """
        if report.n_flagged > 0:
            raise ValidationError(
                message=(
                    f"Confabulation detected: {report.n_flagged} claim(s) flagged "
                    f"({report.auto_escalated=}). "
                    f"Flags: {[f.flag_type.value for f in report.flags[:5]]}"
                ),
                source="confabulation.raise_if_confabulation",
                error_code=ErrorCode.VALIDATION_CONFABULATION_DETECTED,
            )

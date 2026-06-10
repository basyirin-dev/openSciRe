from __future__ import annotations

import re

from openscire.constants import ErrorCode
from openscire.exceptions import ValidationError
from openscire.logging import get_logger

from .models import (
    Citation,
    CitationSupport,
    FirewallAction,
    GroundingVerdict,
    Source,
    SourceVerification,
    SourceVerificationStatus,
    UnsupportedClaimFlag,
)

logger = get_logger("openscire.ethics.source_grounding")

# ---------------------------------------------------------------------------
# Citation extraction patterns
# ---------------------------------------------------------------------------

_NUMERIC_PATTERN = re.compile(r"\[(\d+(?:\s*[,;&-]\s*\d+)*)\]")
_PAREN_AUTHOR_YEAR_PATTERN = re.compile(
    r"\(([A-Z][a-zà-ü]+(?:\s+(?:et\s+al\.?|&\s+[A-Z][a-zà-ü]+))?,\s*\d{4}[a-z]?)\)"
)
_DOI_PATTERN = re.compile(r"(?:doi|DOI):\s*(10\.\d{4,}/[^\s)\].;:!?]+)")
_PMID_PATTERN = re.compile(r"(?:pmid|PMID):?\s*(\d{8})")
_ARXIV_PATTERN = re.compile(r"(?:arxiv|arXiv):\s*(\d{4}\.\d{4,5})")

# ---------------------------------------------------------------------------
# Claim sentence detection helpers
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

_FACTUAL_PATTERN = re.compile(r"^[A-Z].+[.?!]$")

# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def extract_citations(text: str) -> list[Citation]:
    """Extract citations from generated text using regex patterns.

    Supports numeric brackets [1], parenthetical author-year (Smith, 2023),
    DOI, PMID, and arXiv identifiers.

    Args:
        text: The generated text to scan.

    Returns:
        A list of extracted Citation objects.
    """
    citations: list[Citation] = []
    seen: set[str] = set()

    for match in _DOI_PATTERN.finditer(text):
        raw = match.group(0).strip()
        if raw not in seen:
            seen.add(raw)
            citations.append(Citation(raw_text=raw, doi=match.group(1)))

    for match in _PMID_PATTERN.finditer(text):
        raw = match.group(0).strip()
        if raw not in seen:
            seen.add(raw)
            citations.append(Citation(raw_text=raw, pmid=match.group(1)))

    for match in _ARXIV_PATTERN.finditer(text):
        raw = match.group(0).strip()
        if raw not in seen:
            seen.add(raw)
            citations.append(Citation(raw_text=raw, arxiv_id=match.group(1)))

    for match in _PAREN_AUTHOR_YEAR_PATTERN.finditer(text):
        raw = match.group(0).strip()
        if raw not in seen:
            seen.add(raw)
            content = match.group(1)
            author_part = re.sub(r",\s*\d{4}[a-z]?$", "", content)
            year_match = re.search(r"(\d{4})", content)
            year = int(year_match.group(1)) if year_match else None
            citations.append(Citation(raw_text=raw, authors=author_part.strip(), year=year))

    for match in _NUMERIC_PATTERN.finditer(text):
        raw = match.group(0).strip()
        if raw not in seen:
            seen.add(raw)
            citations.append(Citation(raw_text=raw))

    return citations


# ---------------------------------------------------------------------------
# Source verification
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _find_matching_source(citation: Citation, known_sources: list[Source]) -> Source | None:
    for src in known_sources:
        if citation.doi and src.doi and _normalize(citation.doi) == _normalize(src.doi):
            return src
        if citation.pmid and src.pmid and citation.pmid == src.pmid:
            return src
        if citation.arxiv_id and src.arxiv_id and citation.arxiv_id == src.arxiv_id:
            return src
        if citation.authors and citation.year and src.authors and src.year:
            cit_author_last = citation.authors.split(",")[0].strip().split()[-1].lower()
            src_author_last = src.authors.split(",")[0].strip().split()[-1].lower()
            if cit_author_last == src_author_last and citation.year == src.year:
                return src
    return None


def verify_citations(
    citations: list[Citation],
    known_sources: list[Source],
    verify_retraction: bool = True,
) -> list[SourceVerification]:
    """Verify extracted citations against a list of known sources.

    Args:
        citations: Citations extracted from generated text.
        known_sources: Sources from retrieved literature to match against.
        verify_retraction: Whether to flag retracted sources.

    Returns:
        A list of SourceVerification results.
    """
    results: list[SourceVerification] = []

    for citation in citations:
        source = _find_matching_source(citation, known_sources)
        if source is None:
            results.append(
                SourceVerification(
                    source_id="",
                    status=SourceVerificationStatus.NOT_FOUND,
                    detail="No matching source found in known literature.",
                )
            )
        elif verify_retraction and source.retracted:
            results.append(
                SourceVerification(
                    source_id=source.source_id,
                    status=SourceVerificationStatus.RETRACTED,
                    detail=f"Source {source.source_id} has been retracted.",
                )
            )
        else:
            results.append(
                SourceVerification(
                    source_id=source.source_id,
                    status=SourceVerificationStatus.VERIFIED,
                    detail=f"Matched to source {source.source_id}.",
                    match_score=1.0,
                )
            )

    return results


# ---------------------------------------------------------------------------
# Citation support assessment
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


def _has_negation(text: str, citation_pos: int) -> bool:
    words_before = text[:citation_pos].lower().split()
    return any(marker in " ".join(words_before[-20:]) for marker in _NEGATION_MARKERS)


def assess_citation_support(
    claim_text: str,
    citation: Citation,
    source: Source | None = None,
) -> CitationSupport:
    """Assess how well a citation supports a claim.

    Uses word overlap between the claim and the source's title/abstract.
    Detects negation markers near the citation as potential contradictions.

    Args:
        claim_text: The claim text to evaluate.
        citation: The citation associated with the claim.
        source: The verified source (None if unverified).

    Returns:
        A CitationSupport value.
    """
    if source is None:
        return CitationSupport.UNVERIFIED

    claim_tokens = _tokenize(claim_text)
    source_text = f"{source.title} {source.abstract}"
    source_tokens = _tokenize(source_text)

    if not claim_tokens or not source_tokens:
        return CitationSupport.NEUTRAL

    overlap = len(claim_tokens & source_tokens)
    jaccard = overlap / len(claim_tokens | source_tokens) if claim_tokens | source_tokens else 0.0

    cit_index = claim_text.lower().find(citation.raw_text.lower())
    if cit_index >= 0 and _has_negation(claim_text, cit_index):
        return CitationSupport.CONTRADICTS

    if jaccard > 0.15:
        return CitationSupport.SUPPORTS

    return CitationSupport.NEUTRAL


# ---------------------------------------------------------------------------
# Claim extraction from text
# ---------------------------------------------------------------------------


def _extract_claim_sentences(text: str) -> list[str]:
    """Split text into candidate factual claim sentences.

    Filters out questions, exclamations, very short fragments,
    and sentences that are purely meta-commentary.
    """
    sentences: list[str] = []
    for part in re.split(r"[.?!]\s+", text):
        part = part.strip()
        if not part:
            continue
        if len(part) < 15:
            continue
        candidate = part if part.endswith((".", "!", "?")) else part + "."
        if not _FACTUAL_PATTERN.match(candidate):
            continue
        sentences.append(part)
    return sentences


# ---------------------------------------------------------------------------
# SourceGroundingEngine
# ---------------------------------------------------------------------------


class SourceGroundingEngine:
    """Validates that generated claims are grounded in verifiable sources.

    Extracts citations from generated text, verifies them against known
    literature, assesses support relationships, and flags unsupported claims.

    Designed to be injected into EthicalFirewall as an optional sub-module
    following the same pattern as CarbonBudgetTracker, DataSovereigntyChecker,
    and IndigenousKnowledgeProtector.
    """

    def __init__(
        self,
        require_citations: bool = True,
        verify_retraction_status: bool = True,
        min_sources_per_claim: int = 1,
        max_citation_age_years: int = 20,
        allow_unsupported_claims: bool = False,
        check_support_level: bool = True,
        extraction_enabled: bool = True,
        provenance_tracker: Any = None,
    ) -> None:
        self._require_citations = require_citations
        self._verify_retraction_status = verify_retraction_status
        self._min_sources_per_claim = min_sources_per_claim
        self._max_citation_age_years = max_citation_age_years
        self._allow_unsupported_claims = allow_unsupported_claims
        self._check_support_level = check_support_level
        self._extraction_enabled = extraction_enabled
        self._provenance_tracker = provenance_tracker

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_citations(self, text: str) -> list[Citation]:
        """Extract citations from generated text.

        Args:
            text: Generated text to scan for citations.

        Returns:
            List of extracted Citation objects.
        """
        if not self._extraction_enabled or not text:
            return []
        return extract_citations(text)

    def verify_citations(
        self,
        citations: list[Citation],
        known_sources: list[Source],
    ) -> list[SourceVerification]:
        """Verify extracted citations against known sources.

        Args:
            citations: Citations to verify.
            known_sources: Sources from retrieved literature.

        Returns:
            List of verification results.
        """
        return verify_citations(
            citations,
            known_sources,
            verify_retraction=self._verify_retraction_status,
        )

    def assess_citation_support(
        self,
        claim_text: str,
        citation: Citation,
        source: Source | None = None,
    ) -> CitationSupport:
        """Assess how well a citation supports a claim.

        Args:
            claim_text: The claim text.
            citation: The citation to evaluate.
            source: The verified source (None if unverified).

        Returns:
            The support relationship.
        """
        return assess_citation_support(claim_text, citation, source)

    def enforce_citations(
        self,
        text: str,
        known_sources: list[Source] | None = None,
    ) -> GroundingVerdict:
        """Full citation enforcement pipeline on generated text.

        Extracts citations -> verifies -> assesses support -> flags
        unsupported claims.

        Args:
            text: Generated text to validate.
            known_sources: Sources from retrieved literature.

        Returns:
            A GroundingVerdict with approved status and flags.
        """
        known_sources = known_sources or []
        claims_flagged: list[UnsupportedClaimFlag] = []
        all_verifications: list[SourceVerification] = []
        overall = CitationSupport.NEUTRAL

        if not text.strip():
            return GroundingVerdict(
                approved=not self._require_citations,
                overall_support=CitationSupport.NEUTRAL,
            )

        citations = self.extract_citations(text)
        claim_sentences = _extract_claim_sentences(text)

        if self._require_citations and not citations and claim_sentences:
            for sent in claim_sentences:
                claims_flagged.append(
                    UnsupportedClaimFlag(
                        claim_text=sent,
                        reason="no_citations",
                        severity=FirewallAction.FLAG,
                    )
                )
            overall = CitationSupport.NEUTRAL

        if citations and known_sources:
            all_verifications = self.verify_citations(citations, known_sources)

            for citation, verification in zip(citations, all_verifications, strict=False):
                affected = [s for s in claim_sentences if citation.raw_text.lower() in s.lower()]
                if verification.status == SourceVerificationStatus.RETRACTED:
                    for sent in affected:
                        claims_flagged.append(
                            UnsupportedClaimFlag(
                                claim_text=sent,
                                reason="retracted_source",
                                severity=FirewallAction.FLAG,
                            )
                        )
                    overall = CitationSupport.CONTRADICTS

                if verification.status == SourceVerificationStatus.NOT_FOUND:
                    for sent in affected:
                        claims_flagged.append(
                            UnsupportedClaimFlag(
                                claim_text=sent,
                                reason="citation_not_found",
                                severity=FirewallAction.FLAG,
                            )
                        )
                    if overall != CitationSupport.CONTRADICTS:
                        overall = CitationSupport.UNVERIFIED

        n_verified = sum(
            1 for v in all_verifications if v.status == SourceVerificationStatus.VERIFIED
        )

        if self._require_citations and citations and n_verified < self._min_sources_per_claim:
            for sent in claim_sentences:
                already_flagged = any(
                    f.claim_text == sent and f.reason != "no_citations" for f in claims_flagged
                )
                if not already_flagged:
                    claims_flagged.append(
                        UnsupportedClaimFlag(
                            claim_text=sent,
                            reason="insufficient_verified_sources",
                            severity=FirewallAction.FLAG,
                        )
                    )

        if self._check_support_level and citations and known_sources:
            for sent in claim_sentences:
                for citation in citations:
                    source = _find_matching_source(citation, known_sources)
                    support = self.assess_citation_support(sent, citation, source)
                    if support == CitationSupport.CONTRADICTS:
                        claims_flagged.append(
                            UnsupportedClaimFlag(
                                claim_text=sent,
                                reason="citation_contradicts",
                                severity=FirewallAction.FLAG,
                            )
                        )
                        overall = CitationSupport.CONTRADICTS

        approved = not claims_flagged or self._allow_unsupported_claims

        if not approved:
            logger.warning(
                "Source grounding failed",
                n_flags=len(claims_flagged),
                n_verified=n_verified,
                total_claims=len(claim_sentences),
            )

        if self._provenance_tracker is not None:
            try:
                self._provenance_tracker.track(
                    action_type="citation_grounding",
                    params={
                        "n_claims_flagged": len(claims_flagged),
                        "n_citations_verified": n_verified,
                        "n_claim_sentences": len(claim_sentences),
                        "approved": approved,
                        "overall_support": overall.value if overall else "",
                    },
                )
            except Exception:
                logger.warning("Failed to record citation grounding provenance", exc_info=True)

        return GroundingVerdict(
            approved=approved,
            claims_flagged=claims_flagged,
            citations_verified=all_verifications,
            overall_support=overall,
        )

    def check_claims(
        self,
        claim_texts: list[str],
        citations: list[list[Citation]],
        known_sources: list[Source] | None = None,
    ) -> GroundingVerdict:
        """Batch check pre-parsed claim+citation pairs.

        Args:
            claim_texts: List of claim texts.
            citations: List of citation lists (one per claim).
            known_sources: Sources from retrieved literature.

        Returns:
            A GroundingVerdict with per-claim results.
        """
        known_sources = known_sources or []
        claims_flagged: list[UnsupportedClaimFlag] = []
        all_verifications: list[SourceVerification] = []

        for claim_text, claim_citations in zip(claim_texts, citations, strict=False):
            if self._require_citations and not claim_citations:
                claims_flagged.append(
                    UnsupportedClaimFlag(
                        claim_text=claim_text,
                        reason="no_citations",
                        severity=FirewallAction.FLAG,
                    )
                )
                continue

            verifications = self.verify_citations(claim_citations, known_sources)
            all_verifications.extend(verifications)

            for v in verifications:
                if v.status == SourceVerificationStatus.RETRACTED:
                    claims_flagged.append(
                        UnsupportedClaimFlag(
                            claim_text=claim_text,
                            reason="retracted_source",
                            severity=FirewallAction.FLAG,
                        )
                    )

                if v.status == SourceVerificationStatus.NOT_FOUND:
                    claims_flagged.append(
                        UnsupportedClaimFlag(
                            claim_text=claim_text,
                            reason="citation_not_found",
                            severity=FirewallAction.FLAG,
                        )
                    )

            n_verified = sum(
                1 for v in verifications if v.status == SourceVerificationStatus.VERIFIED
            )
            if n_verified < self._min_sources_per_claim:
                claims_flagged.append(
                    UnsupportedClaimFlag(
                        claim_text=claim_text,
                        reason="insufficient_verified_sources",
                        severity=FirewallAction.FLAG,
                    )
                )

        approved = not claims_flagged or self._allow_unsupported_claims
        return GroundingVerdict(
            approved=approved,
            claims_flagged=claims_flagged,
            citations_verified=all_verifications,
        )

    def raise_if_unsupported(self, verdict: GroundingVerdict) -> None:
        """Raise ValidationError if grounding verdict is not approved.

        Args:
            verdict: The GroundingVerdict to check.

        Raises:
            ValidationError: If the verdict has unsupported claims.
        """
        if not verdict.approved:
            reasons = {f.reason for f in verdict.claims_flagged}
            codes = {
                "retracted_source": ErrorCode.VALIDATION_RETRACTED_SOURCE,
                "citation_not_found": ErrorCode.VALIDATION_SOURCE_NOT_FOUND,
                "citation_contradicts": ErrorCode.VALIDATION_CITATION_BROKEN,
            }
            primary_code = ErrorCode.VALIDATION_CITATION_BROKEN
            for reason in sorted(reasons):
                if reason in codes:
                    primary_code = codes[reason]
                    break

            detail = "; ".join(
                f"{f.claim_text[:60]}... -> {f.reason}" for f in verdict.claims_flagged[:5]
            )
            raise ValidationError(
                message=(
                    f"Source grounding failed: {len(verdict.claims_flagged)} claim(s) "
                    f"unsupported. {detail}"
                ),
                source="source_grounding.raise_if_unsupported",
                error_code=primary_code,
            )

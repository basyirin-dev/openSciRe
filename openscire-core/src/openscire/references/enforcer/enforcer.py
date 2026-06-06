from __future__ import annotations

import re
from typing import Any

from openscire.ethics.models import Source, SourceVerificationStatus
from openscire.ethics.source_grounding import extract_citations, verify_citations
from openscire.references.enforcer.cross_check import CrossCheckVerdict, SemanticCrossChecker
from openscire.references.enforcer.models import (
    CitationMode,
    CitationSuggestion,
    SourceEnforcementReport,
    UnsupportedClaim,
)

_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z"])')

_STOPWORDS: set[str] = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "by", "with", "from", "as", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can", "its",
    "it", "this", "that", "these", "those", "not", "no", "nor", "so",
    "if", "than", "then", "also", "very", "just", "about", "above",
    "after", "again", "all", "any", "because", "before", "between",
    "both", "each", "few", "more", "most", "other", "some", "such",
    "only", "own", "same", "too", "under", "up", "down", "out", "off",
    "over", "into", "through", "during", "above", "below", "among",
    "around", "across", "along", "within", "without",
}


class SourceEnforcer:
    def __init__(self, grounding: Any = None) -> None:
        self._grounding = grounding

    def enforce(  # noqa: PLR0912
        self,
        text: str,
        known_sources: list[Source],
        mode: CitationMode = CitationMode.AUDIT,
        provider: Any = None,
    ) -> SourceEnforcementReport:
        if not text or not text.strip():
            return SourceEnforcementReport(mode=mode, approved=True)

        citations = extract_citations(text)
        verified = verify_citations(citations, known_sources)

        cit_map: dict[str, SourceVerificationStatus] = {}
        raw_to_source: dict[str, str] = {}
        source_map: dict[str, Source] = {}
        for cit, ver in zip(citations, verified, strict=False):
            cit_map[cit.raw_text] = ver.status
            if ver.source_id:
                raw_to_source[cit.raw_text] = ver.source_id
                if ver.source_id not in source_map:
                    match = [s for s in known_sources if s.source_id == ver.source_id]
                    if match:
                        source_map[ver.source_id] = match[0]

        verified_count = sum(1 for v in verified if v.status == SourceVerificationStatus.VERIFIED)
        unverified_count = len(verified) - verified_count

        sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]
        cited_sentences = 0
        unsupported: list[UnsupportedClaim] = []
        cross_check_results: list[Any] = []

        for sidx, sentence in enumerate(sentences):
            present_cit_raws = [raw for raw in cit_map if raw in sentence]

            if not present_cit_raws:
                claim = UnsupportedClaim(
                    claim_text=sentence,
                    sentence_index=sidx,
                    reason="no_citation",
                    suggestions=self._suggest(sentence, known_sources),
                )
                unsupported.append(claim)
                continue

            statuses = [cit_map[raw] for raw in present_cit_raws]
            if SourceVerificationStatus.VERIFIED in statuses:
                cited_sentences += 1
                if provider is not None:
                    self._run_cross_check(
                        sentence, present_cit_raws, cit_map, raw_to_source,
                        source_map, cross_check_results, unsupported, provider, sidx,
                    )
                continue

            if SourceVerificationStatus.RETRACTED in statuses:
                reason = "retracted"
            else:
                reason = "citation_not_found"

            claim = UnsupportedClaim(
                claim_text=sentence,
                sentence_index=sidx,
                reason=reason,
                suggestions=self._suggest(sentence, known_sources),
            )
            unsupported.append(claim)

        total_suggested = sum(len(c.suggestions) for c in unsupported)

        if mode == CitationMode.STRICT:
            approved = len(unsupported) == 0
        else:
            approved = True

        return SourceEnforcementReport(
            mode=mode,
            total_sentences=len(sentences),
            cited_sentences=cited_sentences,
            verified_citations=verified_count,
            unverified_citations=unverified_count,
            unsupported_claims=unsupported,
            suggested_citations=total_suggested,
            approved=approved,
            cross_check_results=cross_check_results,
            cross_check_enabled=provider is not None,
        )

    def _run_cross_check(
        self,
        sentence: str,
        present_cit_raws: list[str],
        cit_map: dict[str, SourceVerificationStatus],
        raw_to_source: dict[str, str],
        source_map: dict[str, Source],
        cross_check_results: list[Any],
        unsupported: list[UnsupportedClaim],
        provider: Any,
        sidx: int,
    ) -> None:
        checker = SemanticCrossChecker(provider)
        for raw in present_cit_raws:
            if cit_map[raw] != SourceVerificationStatus.VERIFIED:
                continue
            src_id = raw_to_source.get(raw)
            if src_id is None:
                continue
            src = source_map.get(src_id)
            if src is None:
                continue
            result = checker.check(sentence, src)
            cross_check_results.append(result)
            if result.verdict in (
                CrossCheckVerdict.CONTRADICTS,
                CrossCheckVerdict.INSUFFICIENT_EVIDENCE,
            ):
                unsupported.append(
                    UnsupportedClaim(
                        claim_text=sentence,
                        sentence_index=sidx,
                        reason="semantic_mismatch",
                    )
                )

    def _suggest(
        self,
        claim: str,
        sources: list[Source],
    ) -> list[CitationSuggestion]:
        claim_tokens = self._tokenize(claim)
        if not claim_tokens:
            return []
        scored: list[tuple[float, Source]] = []
        for src in sources:
            title_tokens = self._tokenize(src.title)
            if not title_tokens:
                continue
            intersection = len(claim_tokens & title_tokens)
            union = len(claim_tokens | title_tokens)
            jaccard = intersection / union if union > 0 else 0.0
            if jaccard > 0.05:
                scored.append((jaccard, src))
        scored.sort(key=lambda x: -x[0])
        return [
            CitationSuggestion(
                claim_text=claim,
                suggested_reference_id=src.source_id,
                suggested_title=src.title,
                confidence=jaccard,
                authors=src.authors,
            )
            for jaccard, src in scored[:3]
        ]

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {t for t in re.findall(r"[a-z]+", text.lower()) if t not in _STOPWORDS}

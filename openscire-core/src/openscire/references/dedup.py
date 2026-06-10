# SPDX-License-Identifier: Apache-2.0

"""Deduplication engine for reference items.

Uses three strategies in priority order:
1. DOI exact match — confidence 1.0
2. Title fuzzy match — confidence via rapidfuzz ratio
3. Author + year match — confidence via author name overlap
"""

from __future__ import annotations

import re

from openscire.references.models import (
    DedupMatchMethod,
    DedupResult,
    ReferenceItem,
)


def _normalize_title(title: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    t = title.lower()
    t = re.sub(r"[^\w\s]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _author_signature(item: ReferenceItem) -> str:
    """Space-joined last names for author comparison."""
    names = []
    for a in item.authors:
        if a.last:
            names.append(a.last.lower().strip())
        elif a.full:
            parts = a.full.strip().split()
            if parts:
                names.append(parts[-1].lower())
    return " ".join(sorted(names))


class DedupEngine:
    """Deduplicate a list of ReferenceItems using multiple matching strategies.

    Strategies are applied in priority order. Once an item is matched as a
    duplicate, it is not checked against lower-priority strategies.
    """

    def __init__(self, threshold: float = 0.85) -> None:
        self._threshold = threshold

    def dedup(
        self,
        items: list[ReferenceItem],
        threshold: float | None = None,
    ) -> list[DedupResult]:
        """Run deduplication over a list of items.

        Args:
            items: List of reference items to deduplicate.
            threshold: Override the default similarity threshold (0-1).

        Returns:
            List of DedupResult — one per input item, with ``duplicate_of``
            set if a higher-confidence duplicate was found earlier in the list.
        """
        effective = threshold if threshold is not None else self._threshold
        seen: list[ReferenceItem] = []
        results: list[DedupResult] = []

        for item in items:
            match = self._find_match(item, seen, effective)
            if match is not None:
                dup_item, confidence, method = match
                results.append(
                    DedupResult(
                        item=item,
                        duplicate_of=dup_item,
                        confidence=confidence,
                        match_method=method,
                    )
                )
            else:
                results.append(DedupResult(item=item, confidence=1.0))
                seen.append(item)

        return results

    def _find_match(
        self,
        item: ReferenceItem,
        seen: list[ReferenceItem],
        threshold: float,
    ) -> tuple[ReferenceItem, float, DedupMatchMethod] | None:
        """Find the best match among previously seen items.

        Returns (matched_item, confidence, method) or None.
        """
        # Strategy 1: DOI exact
        if item.doi:
            for candidate in seen:
                if candidate.doi and candidate.doi.lower() == item.doi.lower():
                    return (candidate, 1.0, DedupMatchMethod.doi_exact)

        # Strategy 2: Title fuzzy
        if item.title:
            norm_title = _normalize_title(item.title)
            if len(norm_title) > 10:
                for candidate in seen:
                    if not candidate.title:
                        continue
                    norm_candidate = _normalize_title(candidate.title)
                    if len(norm_candidate) < 10:
                        continue
                    similarity = self._title_similarity(norm_title, norm_candidate)
                    if similarity >= threshold:
                        return (
                            candidate,
                            similarity,
                            DedupMatchMethod.title_fuzzy,
                        )

        # Strategy 3: Author + year
        if item.authors and item.year is not None:
            sig = _author_signature(item)
            if sig:
                for candidate in seen:
                    if candidate.year != item.year:
                        continue
                    if not candidate.authors:
                        continue
                    cand_sig = _author_signature(candidate)
                    if not cand_sig:
                        continue
                    author_sim = self._author_overlap(sig, cand_sig)
                    if author_sim >= threshold:
                        return (
                            candidate,
                            author_sim,
                            DedupMatchMethod.author_year,
                        )

        return None

    @staticmethod
    def _title_similarity(a: str, b: str) -> float:
        """Fuzzy title comparison using token overlap (stdlib-only fallback).

        If rapidfuzz is available, uses it for better accuracy.
        """
        try:
            from rapidfuzz import fuzz

            return float(fuzz.token_sort_ratio(a, b)) / 100.0
        except ImportError:
            tokens_a = set(a.split())
            tokens_b = set(b.split())
            if not tokens_a or not tokens_b:
                return 0.0
            intersection = tokens_a & tokens_b
            return len(intersection) / max(len(tokens_a), len(tokens_b))

    @staticmethod
    def _author_overlap(sig_a: str, sig_b: str) -> float:
        """Compute author name overlap as Jaccard similarity."""
        tokens_a = set(sig_a.split())
        tokens_b = set(sig_b.split())
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        return len(intersection) / len(union)


def find_duplicates(
    items: list[ReferenceItem],
    threshold: float = 0.85,
) -> list[tuple[ReferenceItem, ReferenceItem, float, DedupMatchMethod]]:
    """Convenience: return only the duplicate pairs.

    Returns list of (original, duplicate, confidence, method) tuples.
    """
    engine = DedupEngine(threshold)
    pairs: list[tuple[ReferenceItem, ReferenceItem, float, DedupMatchMethod]] = []
    for result in engine.dedup(items):
        if result.duplicate_of is not None and result.match_method is not None:
            pairs.append(
                (
                    result.duplicate_of,
                    result.item,
                    result.confidence,
                    result.match_method,
                )
            )
    return pairs

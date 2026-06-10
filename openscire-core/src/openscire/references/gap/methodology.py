from __future__ import annotations

import re
from typing import Any

from openscire.references.gap.models import GapSeverity, GapType, LiteratureGap
from openscire.references.models import ReferenceItem

_METHOD_PATTERNS: dict[str, list[str]] = {
    "in vitro": [r"\bin vitro\b", r"\bcell culture\b", r"\bcell line\b"],
    "in vivo": [r"\bin vivo\b", r"\banimal model\b", r"\bmurine\b"],
    "clinical trial": [r"\bclinical trial\b", r"\brandomized\b", r"\bphase [iiv]+\b"],
    "meta-analysis": [r"\bmeta-analysis\b", r"\bmeta analysis\b", r"\bsystematic review\b"],
    "computational": [r"\bcomputational\b", r"\bin silico\b", r"\bmachine learning\b"],
    "observational": [
        r"\bobservational\b",
        r"\bcohort\b",
        r"\bcase-control\b",
        r"\bcross-sectional\b",
    ],
    "longitudinal": [r"\blongitudinal\b", r"\bprospective\b", r"\bfollow-up\b"],
    "qualitative": [r"\bqualitative\b", r"\binterview\b", r"\bthematic analysis\b"],
    "quantitative": [r"\bquantitative\b", r"\bstatistical\b", r"\bregression\b"],
    "case study": [r"\bcase study\b", r"\bcase report\b"],
    "theoretical": [r"\btheoretical\b", r"\bmathematical model\b", r"\bconceptual framework\b"],
}


class MethodologicalMonocultureDetector:
    """Detects domains where all studies use the same experimental methods."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        self.min_method_categories = config.get("gap_min_method_categories", 2)
        self.method_patterns = _METHOD_PATTERNS

    def detect(
        self,
        topic: str,
        items: list[ReferenceItem],
    ) -> list[LiteratureGap]:
        gaps: list[LiteratureGap] = []
        if len(items) < 2:
            return gaps
        found_methods: set[str] = set()
        method_counts: dict[str, int] = {}
        for ref in items:
            text = f"{ref.title} {ref.abstract}".lower()
            for method, patterns in self.method_patterns.items():
                for pat in patterns:
                    if re.search(pat, text):
                        if method not in found_methods:
                            found_methods.add(method)
                        method_counts[method] = method_counts.get(method, 0) + 1
                        break
        n_methods = len(found_methods)
        if n_methods == 0:
            gaps.append(
                LiteratureGap(
                    gap_type=GapType.methodological_monoculture,
                    severity=GapSeverity.medium,
                    topic=topic,
                    description=(
                        f"No methodological keywords detected in '{topic}' studies. "
                        "Methods may be implicit or unreported."
                    ),
                    recommendation=(
                        f"Review abstracts of '{topic}' studies manually to identify methods, "
                        "or search with explicit method terms."
                    ),
                    affected_count=len(items),
                    details={"n_methods_detected": 0},
                )
            )
        elif n_methods < self.min_method_categories:
            severity = GapSeverity.high if n_methods == 1 else GapSeverity.medium
            gaps.append(
                LiteratureGap(
                    gap_type=GapType.methodological_monoculture,
                    severity=severity,
                    topic=topic,
                    description=(
                        f"'{topic}' studies use only {n_methods} method category(ies): "
                        f"{', '.join(sorted(found_methods))}. "
                        f"Minimum {self.min_method_categories} recommended for methodological diversity."
                    ),
                    recommendation=(
                        f"Search for studies using: "
                        f"{', '.join(m for m in self.method_patterns if m not in found_methods)}."
                    ),
                    affected_count=len(items),
                    details={
                        "methods_found": sorted(found_methods),
                        "method_counts": {m: method_counts[m] for m in sorted(found_methods)},
                        "n_methods": n_methods,
                    },
                )
            )
        return gaps

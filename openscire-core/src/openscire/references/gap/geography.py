from __future__ import annotations

from typing import Any

from openscire.references.gap.models import GapSeverity, GapType, LiteratureGap
from openscire.references.models import ReferenceItem

_LANGUAGE_REGION: dict[str, str] = {
    "en": "global_north",
    "de": "global_north",
    "fr": "global_north",
    "es": "global_north",
    "it": "global_north",
    "pt": "global_north",
    "nl": "global_north",
    "sv": "global_north",
    "da": "global_north",
    "no": "global_north",
    "fi": "global_north",
    "ja": "global_north",
    "ko": "global_north",
    "zh": "global_south",
    "ar": "global_south",
    "hi": "global_south",
    "bn": "global_south",
    "pa": "global_south",
    "ta": "global_south",
    "te": "global_south",
    "mr": "global_south",
    "gu": "global_south",
    "kn": "global_south",
    "ml": "global_south",
    "th": "global_south",
    "vi": "global_south",
    "id": "global_south",
    "ms": "global_south",
    "tl": "global_south",
    "sw": "global_south",
    "yo": "global_south",
    "ha": "global_south",
    "zu": "global_south",
    "am": "global_south",
    "ru": "global_north",
    "pl": "global_north",
    "cs": "global_north",
    "hu": "global_north",
    "ro": "global_north",
    "el": "global_north",
    "tr": "global_south",
    "fa": "global_south",
    "ur": "global_south",
    "uk": "global_north",
    "he": "global_south",
}

_GLOBAL_SOUTH_AFFILIATIONS: list[str] = [
    "africa",
    "asia",
    "south america",
    "latin america",
    "india",
    "china",
    "brazil",
    "nigeria",
    "indonesia",
    "pakistan",
    "bangladesh",
    "russia",
    "mexico",
    "ethiopia",
    "philippines",
    "egypt",
    "vietnam",
    "drc",
    "turkey",
    "iran",
    "thailand",
    "tanzania",
    "south africa",
    "kenya",
    "uganda",
    "algeria",
    "sudan",
    "iraq",
    "afghanistan",
    "poland",
    "romania",
    "ukraine",
    "argentina",
    "colombia",
    "peru",
    "venezuela",
    "chile",
    "malaysia",
    "indonesia",
    "myanmar",
    "nepal",
    "sri lanka",
    "ghana",
    "côte d'ivoire",
    "cameroon",
    "angola",
    "mozambique",
    "kenya",
    "ethiopia",
    "tanzania",
    "sudan",
    "morocco",
]


class GeographicGapDetector:
    """Detects gaps in geographic/language representation."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        self.min_global_south = config.get("gap_min_global_south", 1)

    def detect(
        self,
        topic: str,
        items: list[ReferenceItem],
        country_map: dict[str, str] | None = None,
    ) -> list[LiteratureGap]:
        gaps: list[LiteratureGap] = []
        if not items:
            return gaps
        languages: set[str] = set()
        global_south_count = 0
        for ref in items:
            lang = ref.original_language or "en"
            languages.add(lang)
            region = _LANGUAGE_REGION.get(lang, "unknown")
            if region == "global_south":
                global_south_count += 1
        if country_map:
            for _identifier, country_raw in country_map.items():
                country = country_raw.lower()
                if any(s in country for s in _GLOBAL_SOUTH_AFFILIATIONS):
                    global_south_count += 1
        if global_south_count == 0 and len(items) > 0:
            gaps.append(
                LiteratureGap(
                    gap_type=GapType.geographic,
                    severity=GapSeverity.high,
                    topic=topic,
                    description=(
                        f"All {len(items)} studies for '{topic}' are from Global North sources "
                        f"(languages: {', '.join(sorted(languages)) or 'none detected'}). "
                        "No Global South representation found."
                    ),
                    recommendation=(
                        "Search regional databases (SciELO, AJOL, CNKI, Wanfang) or "
                        "include non-English keywords to capture Global South research."
                    ),
                    affected_count=len(items),
                    details={
                        "languages_detected": sorted(languages),
                        "has_global_south": False,
                        "n_total": len(items),
                    },
                )
            )
        elif 0 < global_south_count < self.min_global_south:
            gaps.append(
                LiteratureGap(
                    gap_type=GapType.geographic,
                    severity=GapSeverity.medium,
                    topic=topic,
                    description=(
                        f"Minimal Global South representation in '{topic}' studies "
                        f"({global_south_count}/{len(items)} papers from Global South). "
                        f"Languages: {', '.join(sorted(languages))}."
                    ),
                    recommendation=(
                        "Consider broadening search to include more Global South databases and languages."
                    ),
                    affected_count=len(items),
                    details={
                        "languages_detected": sorted(languages),
                        "global_south_count": global_south_count,
                        "has_global_south": True,
                        "min_required": self.min_global_south,
                    },
                )
            )
        return gaps

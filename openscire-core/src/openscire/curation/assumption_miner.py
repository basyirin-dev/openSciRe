from __future__ import annotations

import re
from typing import Any

from openscire.curation.models import Assumption

logger = __import__("logging").getLogger("openscire.curation.assumption_miner")


class AssumptionMiner:
    """Extracts implicit assumptions from a research question."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    def extract(self, research_question: str) -> list[Assumption]:
        if not research_question.strip():
            return []
        assumptions: list[Assumption] = []
        markers = [
            r"\bassuming\b",
            r"\bgiven that\b",
            r"\bpresupposes?\b",
            r"\bimplies?\b",
            r"\btakes?\s+for\s+granted\b",
        ]
        for marker in markers:
            for match in re.finditer(marker, research_question, re.IGNORECASE):
                start = max(0, match.start() - 40)
                end = min(len(research_question), match.end() + 60)
                excerpt = research_question[start:end].strip()
                assumptions.append(
                    Assumption(
                        assumption_text=excerpt,
                        extracted_from=research_question,
                    )
                )
        if not assumptions:
            sentences = re.split(r"[.!?]", research_question)
            for sent in sentences:
                sent = sent.strip()
                if not sent:
                    continue
                if any(
                    kw in sent.lower()
                    for kw in ["assume", "presuppose", "imply", "given", "taking for granted"]
                ):
                    assumptions.append(
                        Assumption(
                            assumption_text=sent,
                            extracted_from=research_question,
                        )
                    )
        if not assumptions:
            words = research_question.split()
            if len(words) > 5:
                assumptions.append(
                    Assumption(
                        assumption_text=" ".join(words[:5]) + "...",
                        extracted_from=research_question,
                    )
                )
        return assumptions


class AssumptionTester:
    """Searches for sources that support or contradict assumptions."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        bridges: dict[str, Any] | None = None,
    ) -> None:
        self.config = config or {}
        self.bridges = bridges or {}

    async def test(self, assumptions: list[Assumption]) -> list[Assumption]:
        for assumption in assumptions:
            query = f"evidence for or against: {assumption.assumption_text}"
            for bridge_name, bridge in self.bridges.items():
                try:
                    items = await bridge.search(query)
                    for item in items:
                        text = f"{item.title} {item.abstract}".lower()
                        assumption_text = assumption.assumption_text.lower()
                        supported_words = set(assumption_text.split()) & set(text.split())
                        if len(supported_words) / max(len(assumption_text.split()), 1) > 0.3:
                            assumption.supporting_sources.append(item)
                        else:
                            assumption.contradicting_sources.append(item)
                except Exception:
                    logger.exception("Bridge %s failed for assumption test", bridge_name)
        return assumptions

"""Semantic cross-checker — uses LLM to verify claims against source content."""

from __future__ import annotations

import asyncio
import enum
import json
import logging
import re
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

_CROSS_CHECK_SYSTEM_PROMPT = """\
You are a scientific claim verifier. Given a CLAIM and a SOURCE \
(title + abstract), determine whether the source supports, \
contradicts, or lacks sufficient evidence for the claim.

Respond with a JSON object containing three keys:
- "verdict": one of "supports", "contradicts", "insufficient_evidence", or "ambiguous"
- "confidence": a float between 0.0 and 1.0
- "explanation": a brief 1-2 sentence explanation

Definitions:
- supports: The source explicitly or implicitly confirms the claim
- contradicts: The source explicitly or implicitly contradicts the claim
- insufficient_evidence: The source is related but does not provide evidence either way
- ambiguous: The source contains partial or conflicting evidence about the claim

Return ONLY valid JSON, no other text."""


def _build_cross_check_prompt(claim_text: str, source_title: str, source_abstract: str) -> str:
    """Build the user message for the cross-check LLM call."""
    abstract_part = source_abstract if source_abstract else "[No abstract available]"
    return f"CLAIM: {claim_text}\n\nSOURCE TITLE: {source_title}\nSOURCE ABSTRACT: {abstract_part}"


def _parse_llm_response(raw: str) -> dict[str, Any]:
    """Extract and parse JSON from an LLM response string."""
    # Try direct JSON parse first
    text = raw.strip()
    # Remove markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    # Try to extract JSON object with regex
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback: try to extract verdict via keyword match
        for v in ("supports", "contradicts", "insufficient_evidence", "ambiguous", "unverifiable"):
            if v in text.lower():
                return {
                    "verdict": v,
                    "confidence": 0.0,
                    "explanation": "Parsed from unstructured response.",
                }  # noqa: E501
        return {}


class CrossCheckVerdict(enum.StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    AMBIGUOUS = "ambiguous"
    UNVERIFIABLE = "unverifiable"


class CrossCheckResult(BaseModel):
    claim_text: str = ""
    source_id: str = ""
    source_title: str = ""
    verdict: CrossCheckVerdict = CrossCheckVerdict.UNVERIFIABLE
    confidence: float = 0.0
    explanation: str = ""
    llm_model: str = ""


class SemanticCrossChecker:
    """Verify whether a claim is supported by its cited source using an LLM."""

    def __init__(
        self,
        provider: Any,  # noqa: ANN401
        config: dict[str, Any] | None = None,
    ) -> None:
        self._provider = provider
        self._config = config or {}
        self._llm_model: str = getattr(provider, "model", "") or self._config.get("model", "")

    def check(
        self,
        claim_text: str,
        source: Any,  # noqa: ANN401
    ) -> CrossCheckResult:
        """Check a single claim against a single source."""
        source_id = getattr(source, "source_id", "")
        source_title = getattr(source, "title", "")
        source_abstract = getattr(source, "abstract", "")

        if not source_title and not source_abstract:
            return CrossCheckResult(
                claim_text=claim_text,
                source_id=source_id,
                source_title=source_title,
                verdict=CrossCheckVerdict.UNVERIFIABLE,
                explanation="No source content available for cross-check.",
                llm_model=self._llm_model,
            )

        try:
            raw = asyncio.run(self._call_llm(claim_text, source_title, source_abstract))
            parsed = _parse_llm_response(raw)
        except Exception as exc:
            logger.warning("LLM cross-check failed for claim %r: %s", claim_text[:60], exc)
            return CrossCheckResult(
                claim_text=claim_text,
                source_id=source_id,
                source_title=source_title,
                verdict=CrossCheckVerdict.UNVERIFIABLE,
                explanation=f"LLM call failed: {exc}",
                llm_model=self._llm_model,
            )

        verdict_str = parsed.get("verdict", "unverifiable")
        try:
            verdict = CrossCheckVerdict(verdict_str)
        except ValueError:
            verdict = CrossCheckVerdict.UNVERIFIABLE

        return CrossCheckResult(
            claim_text=claim_text,
            source_id=source_id,
            source_title=source_title,
            verdict=verdict,
            confidence=float(parsed.get("confidence", 0.0)),
            explanation=parsed.get("explanation", ""),
            llm_model=self._llm_model,
        )

    def batch_check(
        self,
        items: list[tuple[str, Any]],
    ) -> list[CrossCheckResult]:
        """Cross-check multiple (claim_text, source) pairs."""
        return [self.check(claim, source) for claim, source in items]

    async def _call_llm(self, claim_text: str, source_title: str, source_abstract: str) -> str:
        from openscire.provider.models import ChatMessage

        messages = [
            ChatMessage.system(_CROSS_CHECK_SYSTEM_PROMPT),
            ChatMessage.user(_build_cross_check_prompt(claim_text, source_title, source_abstract)),
        ]
        content = ""
        async for chunk in self._provider.stream_chat(messages, temperature=0.0):
            content += chunk.delta_content or ""
        return content

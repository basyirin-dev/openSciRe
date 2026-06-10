"""Tests for SemanticCrossChecker — LLM-based claim-vs-source verification."""

import json
from collections.abc import AsyncIterator
from typing import Any

from openscire.ethics.models import Source
from openscire.references.enforcer import (
    CitationMode,
    CrossCheckResult,
    CrossCheckVerdict,
    SemanticCrossChecker,
    SourceEnforcer,
)
from openscire.references.enforcer.cross_check import (
    _build_cross_check_prompt,
    _parse_llm_response,
)
from openscire.references.enforcer.models import SourceEnforcementReport

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SOURCE = Source(
    source_id="src1",
    doi="10.1000/abc123",
    title="DNA Methylation in Cancer",
    authors="Smith",
    year=2020,
    abstract="We found that DNA methylation patterns are altered in cancer cells.",
)

_SOURCE_NO_ABSTRACT = Source(
    source_id="src2",
    doi="10.1000/def456",
    title="Gene Expression",
    authors="Jones",
    year=2021,
    abstract="",
)

_SOURCE_EMPTY = Source(
    source_id="src3",
    title="",
    authors="",
    abstract="",
)


class FakeChunk:
    """Simulates a streaming LLM chunk."""

    def __init__(self, text: str) -> None:
        self.delta_content = text


class FakeProvider:
    """A mock provider that returns pre-determined LLM responses."""

    def __init__(self, response: str, model: str = "mock-model") -> None:
        self.response = response
        self.model = model

    async def stream_chat(
        self,
        messages: list[Any],
        temperature: float | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[FakeChunk]:
        yield FakeChunk(self.response)


def _make_provider(verdict: str, confidence: float = 0.9, explanation: str = "") -> Any:
    data = {
        "verdict": verdict,
        "confidence": confidence,
        "explanation": explanation or f"{verdict} verdict",
    }
    return FakeProvider(json.dumps(data))


# ---------------------------------------------------------------------------
# CrossCheckVerdict
# ---------------------------------------------------------------------------


class TestCrossCheckVerdict:
    def test_values(self) -> None:
        assert CrossCheckVerdict.SUPPORTS.value == "supports"
        assert CrossCheckVerdict.CONTRADICTS.value == "contradicts"
        assert CrossCheckVerdict.INSUFFICIENT_EVIDENCE.value == "insufficient_evidence"
        assert CrossCheckVerdict.AMBIGUOUS.value == "ambiguous"
        assert CrossCheckVerdict.UNVERIFIABLE.value == "unverifiable"

    def test_members(self) -> None:
        assert len(CrossCheckVerdict) == 5


# ---------------------------------------------------------------------------
# CrossCheckResult
# ---------------------------------------------------------------------------


class TestCrossCheckResult:
    def test_defaults(self) -> None:
        r = CrossCheckResult()
        assert r.claim_text == ""
        assert r.verdict == CrossCheckVerdict.UNVERIFIABLE

    def test_custom_values(self) -> None:
        r = CrossCheckResult(
            claim_text="Test claim",
            source_id="src1",
            source_title="Test",
            verdict=CrossCheckVerdict.SUPPORTS,
            confidence=0.95,
            explanation="Clearly supported",
            llm_model="gpt-4",
        )
        assert r.claim_text == "Test claim"
        assert r.verdict == CrossCheckVerdict.SUPPORTS
        assert r.confidence == 0.95


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    def test_contains_claim_and_source(self) -> None:
        prompt = _build_cross_check_prompt("Test claim", "Test title", "Test abstract")
        assert "CLAIM: Test claim" in prompt
        assert "SOURCE TITLE: Test title" in prompt
        assert "SOURCE ABSTRACT: Test abstract" in prompt

    def test_missing_abstract(self) -> None:
        prompt = _build_cross_check_prompt("Claim", "Title", "")
        assert "[No abstract available]" in prompt


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


class TestParseLLMResponse:
    def test_direct_json(self) -> None:
        raw = '{"verdict": "supports", "confidence": 0.9, "explanation": "ok"}'
        result = _parse_llm_response(raw)
        assert result["verdict"] == "supports"

    def test_code_fenced_json(self) -> None:
        raw = '```json\n{"verdict": "contradicts", "confidence": 0.8, "explanation": "no"}\n```'
        result = _parse_llm_response(raw)
        assert result["verdict"] == "contradicts"

    def test_unstructured_fallback(self) -> None:
        raw = "The verdict is supports because the evidence matches."
        result = _parse_llm_response(raw)
        assert result.get("verdict") == "supports"

    def test_unparseable(self) -> None:
        raw = "This is completely unparseable gibberish."
        result = _parse_llm_response(raw)
        assert result == {}


# ---------------------------------------------------------------------------
# SemanticCrossChecker.check()
# ---------------------------------------------------------------------------


class TestCheck:
    def test_supports_verdict(self) -> None:
        provider = _make_provider("supports")
        checker = SemanticCrossChecker(provider)
        result = checker.check("Methylation is altered in cancer", _SOURCE)
        assert result.verdict == CrossCheckVerdict.SUPPORTS
        assert result.source_id == "src1"
        assert result.llm_model == "mock-model"

    def test_contradicts_verdict(self) -> None:
        provider = _make_provider("contradicts")
        checker = SemanticCrossChecker(provider)
        result = checker.check("Methylation never changes", _SOURCE)
        assert result.verdict == CrossCheckVerdict.CONTRADICTS

    def test_insufficient_evidence(self) -> None:
        provider = _make_provider("insufficient_evidence", confidence=0.3)
        checker = SemanticCrossChecker(provider)
        result = checker.check("Unknown relation", _SOURCE)
        assert result.verdict == CrossCheckVerdict.INSUFFICIENT_EVIDENCE

    def test_ambiguous(self) -> None:
        provider = _make_provider("ambiguous")
        checker = SemanticCrossChecker(provider)
        result = checker.check("Mixed signals", _SOURCE)
        assert result.verdict == CrossCheckVerdict.AMBIGUOUS

    def test_no_source_content(self) -> None:
        provider = _make_provider("supports")
        checker = SemanticCrossChecker(provider)
        result = checker.check("Claim", _SOURCE_EMPTY)
        assert result.verdict == CrossCheckVerdict.UNVERIFIABLE
        assert "No source content" in result.explanation

    def test_provider_raises_exception(self) -> None:
        async def _broken_stream(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
            raise RuntimeError("LLM unavailable")
            yield  # pragma: no cover

        class BrokenProvider:
            model = "broken"
            stream_chat = _broken_stream

        checker = SemanticCrossChecker(BrokenProvider())
        result = checker.check("Claim", _SOURCE)
        assert result.verdict == CrossCheckVerdict.UNVERIFIABLE
        assert "LLM unavailable" in result.explanation


# ---------------------------------------------------------------------------
# SemanticCrossChecker.batch_check()
# ---------------------------------------------------------------------------


class TestBatchCheck:
    def test_multiple_items(self) -> None:
        provider = _make_provider("supports")
        checker = SemanticCrossChecker(provider)
        results = checker.batch_check(
            [
                ("Claim one", _SOURCE),
                ("Claim two", _SOURCE),
                ("Claim three", _SOURCE_EMPTY),
            ]
        )
        assert len(results) == 3
        assert results[0].verdict == CrossCheckVerdict.SUPPORTS
        assert results[1].verdict == CrossCheckVerdict.SUPPORTS
        assert results[2].verdict == CrossCheckVerdict.UNVERIFIABLE

    def test_empty_list(self) -> None:
        provider = _make_provider("supports")
        checker = SemanticCrossChecker(provider)
        assert checker.batch_check([]) == []


# ---------------------------------------------------------------------------
# _parse_llm_response edge cases
# ---------------------------------------------------------------------------


class TestParseEdgeCases:
    def test_extract_json_from_noisy_text(self) -> None:
        raw = "Here is my analysis.\n\n{'verdict': 'supports', 'confidence': 0.85, 'explanation': 'Yes'}"
        result = _parse_llm_response(raw)
        # This won't parse because single quotes are not valid JSON.
        # Should fall back to keyword match.
        assert result.get("verdict") in ("supports",)

    def test_extra_whitespace_code_fence(self) -> None:
        raw = '  ```  json  \n{"verdict": "supports"}\n  ```  '
        result = _parse_llm_response(raw)
        assert result.get("verdict") == "supports"


# ---------------------------------------------------------------------------
# Integration: SourceEnforcer.enforce() with provider
# ---------------------------------------------------------------------------


_SOURCE_INT = Source(
    source_id="s1",
    doi="10.1000/test",
    title="Test Study on Methylation",
    authors="Smith",
    year=2020,
    abstract="Methylation patterns are altered in cancer.",
)


class TestEnforcerIntegration:
    def test_enforce_without_provider_returns_empty_cross_check(self) -> None:
        enforcer = SourceEnforcer()
        text = "Methylation is altered (Smith, 2020)."
        report = enforcer.enforce(text, [_SOURCE_INT])
        assert report.cross_check_enabled is False
        assert report.cross_check_results == []

    def test_enforce_with_provider_cross_checks_verified(self) -> None:
        provider = _make_provider("supports")
        enforcer = SourceEnforcer()
        text = "Methylation is altered (Smith, 2020)."
        report = enforcer.enforce(text, [_SOURCE_INT], provider=provider)
        assert report.cross_check_enabled is True
        assert len(report.cross_check_results) == 1
        assert report.cross_check_results[0].verdict == CrossCheckVerdict.SUPPORTS

    def test_semantic_contradiction_adds_unsupported_claim(self) -> None:
        provider = _make_provider("contradicts")
        enforcer = SourceEnforcer()
        text = "Methylation never changes (Smith, 2020)."
        report = enforcer.enforce(text, [_SOURCE_INT], provider=provider)
        semantic_flags = [c for c in report.unsupported_claims if c.reason == "semantic_mismatch"]
        assert len(semantic_flags) == 1
        assert "Methylation never changes" in semantic_flags[0].claim_text

    def test_supports_does_not_add_unsupported_claim(self) -> None:
        provider = _make_provider("supports")
        enforcer = SourceEnforcer()
        text = "Methylation is altered (Smith, 2020)."
        report = enforcer.enforce(text, [_SOURCE_INT], provider=provider)
        semantic_flags = [c for c in report.unsupported_claims if c.reason == "semantic_mismatch"]
        assert len(semantic_flags) == 0

    def test_strict_mode_with_semantic_mismatch_blocks(self) -> None:
        provider = _make_provider("contradicts")
        enforcer = SourceEnforcer()
        text = "Methylation never changes (Smith, 2020)."
        report = enforcer.enforce(text, [_SOURCE_INT], mode=CitationMode.STRICT, provider=provider)
        assert report.approved is False

    def test_multiple_sentences_some_cited_some_not(self) -> None:
        provider = _make_provider("supports")
        enforcer = SourceEnforcer()
        text = "Methylation is altered (Smith, 2020). This is unsupported. Another finding (Smith, 2020)."
        report = enforcer.enforce(text, [_SOURCE_INT], provider=provider)
        assert report.total_sentences == 3
        assert len(report.cross_check_results) == 2  # two sentences with verified citations

    def test_insufficient_evidence_adds_unsupported_claim(self) -> None:
        provider = _make_provider("insufficient_evidence", confidence=0.2)
        enforcer = SourceEnforcer()
        text = "Methylation is altered in a specific way (Smith, 2020)."
        report = enforcer.enforce(text, [_SOURCE_INT], provider=provider)
        semantic_flags = [c for c in report.unsupported_claims if c.reason == "semantic_mismatch"]
        assert len(semantic_flags) == 1


# ---------------------------------------------------------------------------
# Report model defaults with cross_check fields
# ---------------------------------------------------------------------------


class TestReportDefaults:
    def test_cross_check_fields_default(self) -> None:
        report = SourceEnforcementReport()
        assert report.cross_check_results == []
        assert report.cross_check_enabled is False

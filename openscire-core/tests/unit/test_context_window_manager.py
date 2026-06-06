"""Tests for ContextWindowManager, TokenBudget, and related models."""

from unittest.mock import MagicMock

import pytest
from openscire.references.context import (
    ContextItem,
    ContextPackage,
    ContextWindowConfig,
    ContextWindowManager,
    OverflowReport,
    TokenBudget,
)
from openscire.references.utils import estimate_tokens


def _make_item(
    text: str,
    score: float = 1.0,
    doc_id: str = "",
    section: str = "",
    token_count: int = -1,
) -> ContextItem:
    return ContextItem(
        id=doc_id,
        text=text,
        score=score,
        document_id=doc_id,
        section=section,
        token_count=token_count if token_count >= 0 else estimate_tokens(text),
    )


class TestContextWindowConfig:
    def test_defaults(self) -> None:
        cfg = ContextWindowConfig()
        assert cfg.model == ""
        assert cfg.max_context_tokens == 0
        assert cfg.reserved_output_tokens == 1024
        assert cfg.min_chunk_tokens == 50
        assert cfg.compression_strategy == "truncate"
        assert cfg.overflow_strategy == "drop"
        assert cfg.format_style == "structured"
        assert cfg.include_citation_context is False

    def test_custom_values(self) -> None:
        cfg = ContextWindowConfig(
            model="gpt-4",
            max_context_tokens=8192,
            reserved_output_tokens=2048,
            min_chunk_tokens=100,
            compression_strategy="drop",
            overflow_strategy="truncate",
            format_style="minimal",
            include_citation_context=True,
        )
        assert cfg.model == "gpt-4"
        assert cfg.max_context_tokens == 8192
        assert cfg.reserved_output_tokens == 2048
        assert cfg.min_chunk_tokens == 100
        assert cfg.compression_strategy == "drop"
        assert cfg.overflow_strategy == "truncate"
        assert cfg.format_style == "minimal"
        assert cfg.include_citation_context is True


class TestTokenBudget:
    def test_defaults(self) -> None:
        b = TokenBudget()
        assert b.capacity == 4096
        assert b.reserved_output == 1024
        assert b.available == 3072
        assert b.used == 0
        assert b.remaining == 3072

    def test_capacity_stored(self) -> None:
        b = TokenBudget(capacity=8192, reserved_output=2048)
        assert b.capacity == 8192
        assert b.reserved_output == 2048

    def test_custom_values_preserved(self) -> None:
        b = TokenBudget(capacity=4096, reserved_output=0, used=500, available=4096, remaining=3596)
        assert b.available == 4096
        assert b.remaining == 3596


class TestOverflowReport:
    def test_defaults(self) -> None:
        r = OverflowReport()
        assert r.total_items == 0
        assert r.kept == 0
        assert r.truncated == 0
        assert r.summarized == 0
        assert r.dropped == 0
        assert r.total_overflow_tokens == 0


class TestContextPackage:
    def test_defaults(self) -> None:
        pkg = ContextPackage()
        assert pkg.model == ""
        assert pkg.formatted_text == ""
        assert pkg.citation_context_attached is False
        assert isinstance(pkg.budget, TokenBudget)
        assert isinstance(pkg.overflow, OverflowReport)
        assert pkg.items == []


class TestBudgetComputation:
    def test_uses_config_context_window(self) -> None:
        cfg = ContextWindowConfig(max_context_tokens=2048, reserved_output_tokens=0)
        mgr = ContextWindowManager(config=cfg)
        assert mgr._compute_budget().capacity == 2048
        assert mgr._compute_budget().available == 2048

    def test_defaults_to_4096(self) -> None:
        mgr = ContextWindowManager()
        assert mgr._compute_budget().capacity == 4096

    def test_reserved_output_subtracted(self) -> None:
        cfg = ContextWindowConfig(max_context_tokens=4096, reserved_output_tokens=512)
        mgr = ContextWindowManager(config=cfg)
        assert mgr._compute_budget().available == 3584
        assert mgr._compute_budget().remaining == 3584

    def test_reserved_output_capped(self) -> None:
        cfg = ContextWindowConfig(max_context_tokens=100, reserved_output_tokens=200)
        mgr = ContextWindowManager(config=cfg)
        budget = mgr._compute_budget()
        assert budget.reserved_output == 99
        assert budget.available == 1


class TestBuildContextPriority:
    def test_highest_score_first_in_formatted_text(self) -> None:
        mgr = ContextWindowManager(
            config=ContextWindowConfig(max_context_tokens=2000, reserved_output_tokens=0)
        )
        items = [
            _make_item("low priority text", score=0.1, doc_id="low"),
            _make_item("high priority text", score=0.9, doc_id="high"),
            _make_item("medium priority text", score=0.5, doc_id="med"),
        ]
        pkg = mgr.build_context(items)
        # highest score item should appear first
        high_idx = pkg.formatted_text.index("high priority text")
        med_idx = pkg.formatted_text.index("medium priority text")
        low_idx = pkg.formatted_text.index("low priority text")
        assert high_idx < med_idx < low_idx

    def test_items_have_rank_in_order(self) -> None:
        mgr = ContextWindowManager(
            config=ContextWindowConfig(max_context_tokens=2000, reserved_output_tokens=0)
        )
        items = [
            _make_item("a", score=0.3),
            _make_item("b", score=0.9),
            _make_item("c", score=0.1),
        ]
        pkg = mgr.build_context(items)
        ranks = {i.text: i.rank for i in pkg.items}
        assert ranks["b"] == 1
        assert ranks["a"] == 2
        assert ranks["c"] == 3


class TestBuildContextBudget:
    def test_budget_respected(self) -> None:
        mgr = ContextWindowManager(
            config=ContextWindowConfig(max_context_tokens=2000, reserved_output_tokens=0)
        )
        items = [_make_item(f"paragraph {i} " * 20, score=1.0 - i * 0.1) for i in range(10)]
        pkg = mgr.build_context(items)
        actual_tokens = estimate_tokens(pkg.formatted_text)
        assert actual_tokens <= pkg.budget.available * 1.1

    def test_single_item_fits(self) -> None:
        mgr = ContextWindowManager(
            config=ContextWindowConfig(max_context_tokens=1000, reserved_output_tokens=0)
        )
        item = _make_item("short text", score=1.0)
        pkg = mgr.build_context([item])
        assert len(pkg.items) == 1
        assert pkg.items[0].status == "kept"
        assert "short text" in pkg.formatted_text

    def test_all_items_fit(self) -> None:
        mgr = ContextWindowManager(
            config=ContextWindowConfig(max_context_tokens=4000, reserved_output_tokens=0)
        )
        items = [_make_item(f"item {i}", score=1.0, token_count=10) for i in range(5)]
        pkg = mgr.build_context(items)
        assert pkg.overflow.kept == 5
        assert pkg.overflow.dropped == 0
        assert pkg.overflow.truncated == 0

    def test_empty_items(self) -> None:
        mgr = ContextWindowManager()
        pkg = mgr.build_context([])
        assert pkg.formatted_text == ""
        assert pkg.items == []
        assert pkg.overflow.total_items == 0

    def test_empty_text_item(self) -> None:
        mgr = ContextWindowManager(
            config=ContextWindowConfig(max_context_tokens=500, reserved_output_tokens=0)
        )
        item = _make_item("", score=1.0, token_count=0)
        pkg = mgr.build_context([item])
        assert len(pkg.items) == 1
        assert pkg.items[0].status == "kept"


class TestOverflow:
    def test_drops_lowest_score_when_over_budget(self) -> None:
        mgr = ContextWindowManager(
            config=ContextWindowConfig(
                max_context_tokens=200,
                reserved_output_tokens=0,
                min_chunk_tokens=200,
            )
        )
        items = [
            _make_item("high value " * 50, score=1.0),
            _make_item("low value " * 50, score=0.1),
        ]
        pkg = mgr.build_context(items)
        assert pkg.overflow.dropped >= 1
        assert len(pkg.items) == 1

    def test_truncates_partial_fit(self) -> None:
        mgr = ContextWindowManager(
            config=ContextWindowConfig(
                max_context_tokens=200,
                reserved_output_tokens=0,
                min_chunk_tokens=10,
            )
        )
        small_high = _make_item("Short high priority", score=1.0, token_count=30)
        big_low = _make_item("Long text that exceeds budget " * 50, score=0.5, token_count=400)
        pkg = mgr.build_context([big_low, small_high])
        truncated = [i for i in pkg.items if i.status == "truncated"]
        kept = [i for i in pkg.items if i.status == "kept"]
        assert len(truncated) >= 1
        assert len(kept) >= 1

    def test_force_truncate_below_min_tokens(self) -> None:
        mgr = ContextWindowManager(
            config=ContextWindowConfig(
                max_context_tokens=100,
                reserved_output_tokens=0,
                min_chunk_tokens=50,
                overflow_strategy="truncate",
            )
        )
        big_item = _make_item("Data " * 100, score=1.0, token_count=400)
        pkg = mgr.build_context([big_item])
        assert pkg.overflow.truncated == 1
        assert pkg.overflow.dropped == 0

    def test_summarize_not_implemented(self) -> None:
        mgr = ContextWindowManager(
            config=ContextWindowConfig(
                max_context_tokens=100,
                reserved_output_tokens=0,
                min_chunk_tokens=100,
                overflow_strategy="summarize",
            )
        )
        item = _make_item("A" * 1000, score=1.0, token_count=500)
        with pytest.raises(NotImplementedError, match="Summarize"):
            mgr.build_context([item])


class TestFormat:
    def test_structured_format_has_headers(self) -> None:
        mgr = ContextWindowManager(
            config=ContextWindowConfig(max_context_tokens=2000, reserved_output_tokens=0)
        )
        item = _make_item("body text", score=1.0, doc_id="doc1", section="Intro")
        pkg = mgr.build_context([item])
        assert "[Document: doc1]" in pkg.formatted_text
        assert "[Section: Intro]" in pkg.formatted_text
        assert "body text" in pkg.formatted_text

    def test_structured_format_empty_headers(self) -> None:
        mgr = ContextWindowManager(
            config=ContextWindowConfig(max_context_tokens=2000, reserved_output_tokens=0)
        )
        item = _make_item("body text", score=1.0)
        pkg = mgr.build_context([item])
        assert "[Document: ]" in pkg.formatted_text
        assert "[Section: ]" in pkg.formatted_text

    def test_minimal_format_no_headers(self) -> None:
        cfg = ContextWindowConfig(
            max_context_tokens=2000, reserved_output_tokens=0, format_style="minimal"
        )
        mgr = ContextWindowManager(config=cfg)
        items = [
            _make_item("first item", score=1.0, doc_id="doc1"),
            _make_item("second item", score=0.5, doc_id="doc2"),
        ]
        pkg = mgr.build_context(items)
        assert "[Document:" not in pkg.formatted_text
        assert "first item" in pkg.formatted_text
        assert "second item" in pkg.formatted_text

    def test_separator_between_items(self) -> None:
        mgr = ContextWindowManager(
            config=ContextWindowConfig(max_context_tokens=2000, reserved_output_tokens=0)
        )
        items = [
            _make_item("first", score=1.0),
            _make_item("second", score=0.5),
        ]
        pkg = mgr.build_context(items)
        assert "---" in pkg.formatted_text


class TestCitationContext:
    def test_included_when_configured(self) -> None:
        cfg = ContextWindowConfig(
            max_context_tokens=4000, reserved_output_tokens=0, include_citation_context=True
        )
        mgr = ContextWindowManager(config=cfg)
        item = _make_item("text", score=1.0, token_count=10)
        mock_cc = MagicMock()
        mock_cc.citations = [MagicMock()]
        mock_cc.contradictions = []
        mock_cc.density_scores = []
        pkg = mgr.build_context([item], citation_context=mock_cc)
        assert pkg.citation_context_attached is True
        assert "=== Citation Context ===" in pkg.formatted_text

    def test_skipped_when_not_configured(self) -> None:
        cfg = ContextWindowConfig(
            max_context_tokens=4000, reserved_output_tokens=0, include_citation_context=False
        )
        mgr = ContextWindowManager(config=cfg)
        item = _make_item("text", score=1.0, token_count=10)
        mock_cc = MagicMock()
        pkg = mgr.build_context([item], citation_context=mock_cc)
        assert pkg.citation_context_attached is False
        assert "=== Citation Context ===" not in pkg.formatted_text

    def test_skipped_when_no_citation_context_passed(self) -> None:
        cfg = ContextWindowConfig(
            max_context_tokens=4000, reserved_output_tokens=0, include_citation_context=True
        )
        mgr = ContextWindowManager(config=cfg)
        item = _make_item("text", score=1.0, token_count=10)
        pkg = mgr.build_context([item])
        assert pkg.citation_context_attached is False

    def test_contradictions_included(self) -> None:
        cfg = ContextWindowConfig(
            max_context_tokens=4000, reserved_output_tokens=0, include_citation_context=True
        )
        mgr = ContextWindowManager(config=cfg)
        item = _make_item("text", score=1.0, token_count=10)
        mock_cc = MagicMock()
        mock_cc.citations = [MagicMock()]
        mock_cc.contradictions = [MagicMock()]
        mock_cc.contradictions[0].signal_type = "retraction"
        mock_cc.contradictions[0].description = "Paper retracted"
        mock_cc.density_scores = []
        pkg = mgr.build_context([item], citation_context=mock_cc)
        assert "[!] retraction: Paper retracted" in pkg.formatted_text

    def test_no_issues_message_when_clean(self) -> None:
        cfg = ContextWindowConfig(
            max_context_tokens=4000, reserved_output_tokens=0, include_citation_context=True
        )
        mgr = ContextWindowManager(config=cfg)
        item = _make_item("text", score=1.0, token_count=10)
        mock_cc = MagicMock()
        mock_cc.citations = [MagicMock()]
        mock_cc.contradictions = []
        mock_cc.density_scores = []
        pkg = mgr.build_context([item], citation_context=mock_cc)
        assert "No citation issues detected." in pkg.formatted_text

    def test_high_density_noted(self) -> None:
        cfg = ContextWindowConfig(
            max_context_tokens=4000, reserved_output_tokens=0, include_citation_context=True
        )
        mgr = ContextWindowManager(config=cfg)
        item = _make_item("text", score=1.0, token_count=10)
        mock_cc = MagicMock()
        mock_cc.citations = [MagicMock()]
        mock_cc.contradictions = []
        mock_density = MagicMock()
        mock_density.density_label = "high"
        mock_cc.density_scores = [mock_density]
        pkg = mgr.build_context([item], citation_context=mock_cc)
        assert "High-density citations" in pkg.formatted_text


class TestCustomTokenEstimator:
    def test_custom_estimator_used(self) -> None:
        call_count = 0

        def dummy_estimator(_text: str) -> int:
            nonlocal call_count
            call_count += 1
            return 10  # fixed token count

        mgr = ContextWindowManager(
            config=ContextWindowConfig(max_context_tokens=100, reserved_output_tokens=0),
            token_estimator=dummy_estimator,
        )
        items = [_make_item("test", score=1.0)]
        mgr.build_context(items)
        assert call_count > 0


class TestModelName:
    def test_model_name_in_package(self) -> None:
        cfg = ContextWindowConfig(
            model="llama3.1", max_context_tokens=2000, reserved_output_tokens=0
        )
        mgr = ContextWindowManager(config=cfg)
        item = _make_item("test", score=1.0, token_count=10)
        pkg = mgr.build_context([item])
        assert pkg.model == "llama3.1"

    def test_default_model_name_empty(self) -> None:
        mgr = ContextWindowManager(
            config=ContextWindowConfig(max_context_tokens=500, reserved_output_tokens=0)
        )
        item = _make_item("test", score=1.0, token_count=10)
        pkg = mgr.build_context([item])
        assert pkg.model == ""


class TestTruncationEdgeCases:
    def test_truncate_empty_text(self) -> None:
        mgr = ContextWindowManager()
        assert mgr._truncate("", 100) == ""

    def test_truncate_zero_budget(self) -> None:
        mgr = ContextWindowManager()
        assert mgr._truncate("some text", 0) == ""

    def test_truncate_negative_budget(self) -> None:
        mgr = ContextWindowManager()
        assert mgr._truncate("some text", -1) == ""

    def test_truncate_already_fits(self) -> None:
        mgr = ContextWindowManager()
        text = "short"
        assert mgr._truncate(text, 100) == text

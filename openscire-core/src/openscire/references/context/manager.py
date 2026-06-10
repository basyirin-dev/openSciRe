from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from openscire.references.context.models import (
    ContextItem,
    ContextPackage,
    ContextWindowConfig,
    OverflowReport,
    TokenBudget,
)
from openscire.references.utils import estimate_tokens as _default_estimator

logger = logging.getLogger(__name__)


class ContextWindowManager:
    def __init__(
        self,
        config: ContextWindowConfig | None = None,
        provider: Any = None,  # noqa: ANN401
        token_estimator: Callable[[str], int] | None = None,
    ) -> None:
        self.config = config or ContextWindowConfig()
        self._provider = provider
        self._token_estimator = token_estimator or _default_estimator

    def build_context(
        self,
        items: list[ContextItem],
        citation_context: Any = None,  # noqa: ANN401
    ) -> ContextPackage:
        if not items:
            budget = self._compute_budget()
            return ContextPackage(
                model=self.config.model,
                budget=budget,
                formatted_text="",
            )

        budget = self._compute_budget()
        sorted_items = sorted(items, key=lambda i: i.score, reverse=True)

        selected: list[ContextItem] = []
        overflow = OverflowReport(total_items=len(items))
        rank_counter = 1

        for item in sorted_items:
            item.rank = rank_counter
            rank_counter += 1
            if item.token_count <= 0:
                item.token_count = self._token_estimator(item.text)

            pos = len(selected)
            overhead = self._estimate_item_overhead(pos, item)
            content_tokens = item.token_count
            total_cost = content_tokens + overhead

            if total_cost <= budget.remaining:
                budget.used += content_tokens
                budget.remaining -= total_cost
                item.status = "kept"
                selected.append(item)
                overflow.kept += 1

            elif (
                budget.remaining >= self.config.min_chunk_tokens + overhead
                or self.config.overflow_strategy == "truncate"
            ):
                target_tokens = max(1, budget.remaining - overhead)
                truncated_text = self._truncate(item.text, target_tokens)
                truncated_tokens = self._token_estimator(truncated_text)
                item.text = truncated_text
                item.token_count = truncated_tokens
                total_after = truncated_tokens + overhead
                budget.used += truncated_tokens
                budget.remaining -= total_after
                item.status = "truncated"
                selected.append(item)
                overflow.truncated += 1
                overflow.total_overflow_tokens += max(0, content_tokens - truncated_tokens)

            elif self.config.overflow_strategy == "summarize":
                msg = "Summarize overflow strategy not yet implemented"
                raise NotImplementedError(msg)

            else:
                item.status = "dropped"
                overflow.dropped += 1
                overflow.total_overflow_tokens += content_tokens

        formatted_text = self._format(selected)
        budget.used = self._token_estimator(formatted_text)
        budget.remaining = max(0, budget.available - budget.used)

        citation_attached = False
        if citation_context is not None and self.config.include_citation_context:
            citation_block = self._format_citation_context(citation_context)
            citation_tokens = self._token_estimator(citation_block)
            if citation_tokens <= budget.remaining:
                formatted_text += "\n\n" + citation_block
                budget.used += citation_tokens
                budget.remaining = max(0, budget.remaining - citation_tokens)
                citation_attached = True

        return ContextPackage(
            model=self.config.model,
            budget=budget,
            items=selected,
            formatted_text=formatted_text,
            overflow=overflow,
            citation_context_attached=citation_attached,
        )

    def _estimate_item_overhead(self, position: int, item: ContextItem) -> int:
        if position < 0:
            return 0
        if self.config.format_style == "minimal":
            return 0 if position == 0 else self._token_estimator("\n---\n")
        header = f"[Document: {item.document_id}]\n[Section: {item.section}]\n"
        overhead = self._token_estimator(header)
        if position > 0:
            overhead += self._token_estimator("\n---\n")
        return overhead

    def _compute_budget(self) -> TokenBudget:
        capacity = self.config.max_context_tokens if self.config.max_context_tokens > 0 else 4096

        reserved = min(self.config.reserved_output_tokens, capacity - 1) if capacity > 1 else 0
        available = max(0, capacity - reserved)
        return TokenBudget(
            capacity=capacity,
            reserved_output=reserved,
            available=available,
            remaining=available,
        )

    def _truncate(self, text: str, max_tokens: int) -> str:
        if not text or max_tokens <= 0:
            return ""
        tokens = self._token_estimator(text)
        if tokens <= max_tokens:
            return text
        ratio = (max_tokens / tokens) * 0.9
        char_target = max(1, int(len(text) * ratio))
        return text[:char_target]

    def _format(self, items: list[ContextItem]) -> str:
        if not items:
            return ""
        parts: list[str] = []
        for item in items:
            if self.config.format_style == "minimal":
                parts.append(item.text)
            else:
                parts.append(
                    f"[Document: {item.document_id}]\n[Section: {item.section}]\n{item.text}"
                )
        return "\n---\n".join(parts)

    def _format_citation_context(self, citation_context: Any) -> str:  # noqa: ANN401
        lines = ["=== Citation Context ==="]
        try:
            if hasattr(citation_context, "citations") and citation_context.citations:
                lines.append(f"References cited: {len(citation_context.citations)}")
            if hasattr(citation_context, "contradictions") and citation_context.contradictions:
                for c in citation_context.contradictions:
                    lines.append(f"[!] {c.signal_type}: {c.description}")
            if hasattr(citation_context, "density_scores") and citation_context.density_scores:
                high = [d for d in citation_context.density_scores if d.density_label == "high"]
                if high:
                    lines.append(f"High-density citations: {len(high)}")
            if not getattr(citation_context, "contradictions", None):
                lines.append("No citation issues detected.")
        except Exception:
            lines.append("Citation context unavailable.")
        return "\n".join(lines)

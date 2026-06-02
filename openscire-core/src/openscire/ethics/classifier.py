from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from openscire.constants import DURCCategory
from openscire.logging import get_logger
from openscire.provider.base import ModelProvider
from openscire.provider.models import ChatMessage

from .models import DURCResult, FirewallAction, FirewallRule, MatchType

logger = get_logger("openscire.ethics.classifier")

_MATCHED_TRUNCATE_LENGTH = 500


class KeywordMatcher:
    """Regex-based keyword pattern matching for DURC detection.

    Compiles patterns on init for performance.  Each pattern is matched
    with word boundaries where present in the source definition.
    """

    def __init__(self, patterns: dict[DURCCategory, list[str]]) -> None:
        self._compiled: dict[DURCCategory, list[re.Pattern[str]]] = {}
        for cat, pats in patterns.items():
            compiled: list[re.Pattern[str]] = []
            for p in pats:
                try:
                    compiled.append(re.compile(p, re.IGNORECASE))
                except re.error:
                    logger.warning("Invalid DURC keyword pattern", category=cat.value, pattern=p)
            self._compiled[cat] = compiled

    def scan(
        self,
        text: str,
        categories: list[DURCCategory] | None = None,
    ) -> list[tuple[DURCCategory, str, str]]:
        """Scan text against keyword patterns.

        Args:
            text: The text to scan.
            categories: Categories to check; defaults to all defined.

        Returns:
            List of (category, matched_text, pattern) tuples for each match.
        """
        results: list[tuple[DURCCategory, str, str]] = []
        cats = categories or list(self._compiled.keys())
        for cat in cats:
            patterns = self._compiled.get(cat, [])
            for pat in patterns:
                match = pat.search(text)
                if match:
                    matched = match.group(0)
                    results.append((cat, matched[:_MATCHED_TRUNCATE_LENGTH], pat.pattern))
        return results


class EmbeddingMatcher:
    """Optional embedding-based DURC detection using sentence-transformers.

    If sentence-transformers is not installed, ``available`` will be
    False and ``score()`` returns 0.0 for all categories.  This keeps
    the dependency optional but provides richer semantic detection when
    available.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        self._model: Any = None
        self._centroids: dict[DURCCategory, Any] | None = None
        self.available = self._try_load()

    def _try_load(self) -> bool:
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
            return True
        except ImportError:
            logger.info(
                "sentence-transformers not available; embedding detection disabled. "
                "Install with: pip install openscire[ethics]"
            )
            return False
        except Exception:
            logger.warning("Failed to load embedding model", model=self._model_name, exc_info=True)
            return False

    def _ensure_centroids(self, seeds: dict[DURCCategory, list[str]]) -> None:
        if self._centroids is not None or not self.available:
            return
        import numpy as np

        self._centroids = {}
        all_texts: list[str] = []
        cat_indices: list[tuple[DURCCategory, int]] = []
        for cat, texts in seeds.items():
            if texts:
                start = len(all_texts)
                all_texts.extend(texts)
                for i in range(len(texts)):
                    cat_indices.append((cat, start + i))

        if not all_texts or self._model is None:
            return

        embeddings = self._model.encode(all_texts, show_progress_bar=False)
        cat_embs: dict[DURCCategory, list[Any]] = {cat: [] for cat in seeds}
        for cat, idx in cat_indices:
            cat_embs[cat].append(embeddings[idx])

        for cat, emb_list in cat_embs.items():
            if emb_list:
                self._centroids[cat] = np.mean(emb_list, axis=0)
            else:
                self._centroids[cat] = np.zeros(embeddings.shape[1])

    def score(
        self,
        text: str,
        seeds: dict[DURCCategory, list[str]],
        threshold: float = 0.75,
    ) -> dict[DURCCategory, float]:
        """Compute embedding similarity scores against category centroids.

        Args:
            text: Text to classify.
            seeds: Seed phrases per category (from durc module).
            threshold: Minimum similarity to report.

        Returns:
            Dict mapping category to similarity score (0.0 if unavailable).
        """
        if not self.available or self._model is None:
            return {cat: 0.0 for cat in seeds}

        self._ensure_centroids(seeds)
        if self._centroids is None:
            return {cat: 0.0 for cat in seeds}

        import numpy as np

        text_emb = self._model.encode([text], show_progress_bar=False)[0]
        scores: dict[DURCCategory, float] = {}
        for cat, centroid in self._centroids.items():
            denom = np.linalg.norm(text_emb) * np.linalg.norm(centroid) + 1e-10
            sim = float(np.dot(text_emb, centroid) / denom)
            scores[cat] = sim if sim >= threshold else 0.0
        return scores


class LLMClassifier:
    """Optional LLM-assisted DURC classification.

    Uses a (separate, configurable) LLM provider to classify text against
    DURC categories.  This is the most accurate but most expensive option.
    """

    def __init__(
        self,
        provider: ModelProvider | None = None,
        prompt_template: str = "",
    ) -> None:
        self._provider = provider
        self._prompt_template = prompt_template

    async def classify(
        self,
        text: str,
        categories: list[DURCCategory],
    ) -> list[DURCResult]:
        """Classify text via LLM for the given categories.

        Args:
            text: The text to classify.
            categories: The DURC categories to check.

        Returns:
            List of DURCResult with LLM-based classifications.
        """
        if self._provider is None:
            return []

        from openscire.ethics.durc import DEFAULT_CLASSIFICATION_PROMPT

        prompt = (self._prompt_template or DEFAULT_CLASSIFICATION_PROMPT).format(text=text[:3000])
        messages = [ChatMessage.system("You are a DURC classifier."), ChatMessage.user(prompt)]

        results: list[DURCResult] = []
        try:
            full_response = ""
            async for chunk in self._provider.stream_chat(messages):
                if chunk.delta_content:
                    full_response += chunk.delta_content

            parsed = self._parse_response(full_response)
            if parsed and parsed.get("flagged"):
                cat_name = parsed.get("category")
                matched_cat = next((c for c in categories if c.value == cat_name), None)
                if matched_cat:
                    confidence = min(max(float(parsed.get("confidence", 0.5)), 0.0), 1.0)
                    results.append(
                        DURCResult(
                            triggered=True,
                            category=matched_cat,
                            rule_id="llm_classifier",
                            match_type=MatchType.LLM,
                            matched_text=text[:_MATCHED_TRUNCATE_LENGTH],
                            confidence=confidence,
                            action_taken=FirewallAction.WARN,
                            timestamp=datetime.now(UTC),
                        )
                    )
        except Exception:
            logger.warning("LLM DURC classification failed", exc_info=True)
        return results

    @staticmethod
    def _parse_response(response: str) -> dict[str, Any] | None:
        import json

        try:
            start = response.index("{")
            end = response.rindex("}") + 1
            parsed = json.loads(response[start:end])
            assert isinstance(parsed, dict)
            return parsed
        except (ValueError, json.JSONDecodeError, AssertionError):
            logger.warning("Failed to parse LLM classification response")
            return None


class DURCClassifier:
    """Orchestrates keyword, embedding, and LLM-based DURC detection.

    Runs all enabled detection methods for each rule and aggregates results.
    """

    def __init__(
        self,
        keyword_patterns: dict[DURCCategory, list[str]] | None = None,
        embedding_seeds: dict[DURCCategory, list[str]] | None = None,
        embedding_model_name: str = "",
        llm_provider: ModelProvider | None = None,
        llm_prompt_template: str = "",
    ) -> None:
        self._keyword_matcher = KeywordMatcher(keyword_patterns or {})
        self._embedding_seeds = embedding_seeds
        self._embedding_matcher = (
            EmbeddingMatcher(embedding_model_name) if embedding_model_name else None
        )
        self._llm_classifier = (
            LLMClassifier(provider=llm_provider, prompt_template=llm_prompt_template)
            if llm_provider
            else None
        )

    async def scan(
        self,
        text: str,
        rules: list[FirewallRule],
        default_action: FirewallAction = FirewallAction.WARN,
    ) -> list[DURCResult]:
        """Scan text against all enabled rules.

        For each rule, runs keyword matching always, then embedding (if
        configured and available), then LLM (if enabled on the rule).

        Args:
            text: Text to scan.
            rules: Firewall rules to evaluate.
            default_action: Fallback action if a rule doesn't specify one.

        Returns:
            Sorted list of triggered DURCResults (highest confidence first).
        """
        results: list[DURCResult] = []
        enabled_rules = [r for r in rules if r.enabled]

        if not enabled_rules:
            return results

        # --- Keyword matching (always runs) ---
        kw_results = self._keyword_matcher.scan(text)
        for cat, matched_text, _ in kw_results:
            rule = next((r for r in enabled_rules if r.category == cat), None)
            if rule is None:
                continue
            results.append(
                DURCResult(
                    triggered=True,
                    category=cat,
                    rule_id=rule.id,
                    match_type=MatchType.KEYWORD,
                    matched_text=matched_text,
                    confidence=0.8,
                    action_taken=rule.action if rule.action else default_action,
                    timestamp=datetime.now(UTC),
                )
            )

        # --- Embedding matching (if available) ---
        if self._embedding_matcher and self._embedding_seeds:
            embed_cats = [r.category for r in enabled_rules if r.embedding_threshold is not None]
            if embed_cats:
                seeds_subset = {c: self._embedding_seeds.get(c, []) for c in embed_cats}
                embed_scores = self._embedding_matcher.score(text, seeds_subset)
                for cat, score in embed_scores.items():
                    if score > 0.0:
                        rule = next((r for r in enabled_rules if r.category == cat), None)
                        if rule is None:
                            continue
                        results.append(
                            DURCResult(
                                triggered=True,
                                category=cat,
                                rule_id=rule.id,
                                match_type=MatchType.EMBEDDING,
                                matched_text=text[:_MATCHED_TRUNCATE_LENGTH],
                                confidence=score,
                                action_taken=rule.action if rule.action else default_action,
                                timestamp=datetime.now(UTC),
                            )
                        )

        # --- LLM classification (if enabled per rule) ---
        llm_cats = [r.category for r in enabled_rules if r.llm_classification]
        if llm_cats and self._llm_classifier:
            llm_results = await self._llm_classifier.classify(text, llm_cats)
            results.extend(llm_results)

        results.sort(key=lambda r: r.confidence, reverse=True)
        return results

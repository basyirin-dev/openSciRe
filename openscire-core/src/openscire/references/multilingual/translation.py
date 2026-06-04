# SPDX-License-Identifier: Apache-2.0

"""Translation with uncertainty metadata.

This module does NOT perform translation itself.  It provides a wrapper
that accepts translations from any source (LLM, NLLB-200, external API)
and attaches confidence scoring and meaning-loss flags.

The simplest initial implementation uses an LLM call with a structured
prompt asking the model to rate its own translation confidence.
"""

from __future__ import annotations

import logging
from typing import Any

from openscire.references.multilingual.models import (
    MeaningLossFlag,
    TranslationEntry,
)

logger = logging.getLogger(__name__)


class TranslationService:
    """Wraps a translation with uncertainty metadata.

    The translation itself is delegated to a callable (e.g., an LLM
    invocation, a local NLLB-200 model, or an external API).  This
    service adds confidence scoring and meaning-loss flags.

    Args:
        translator: A callable that accepts (text, source_lang, target_lang)
            and returns a dict with keys:
            - "translated_text": str
            - "confidence": float (0.0-1.0)
            - "meaning_loss_flags": list[str] (optional)
            - "method": str (optional, e.g. "llm", "nllb-200")
            - "model_name": str (optional)
    """

    def __init__(
        self,
        translator: Any = None,  # noqa: ANN401
    ) -> None:
        self._translator = translator

    @staticmethod
    def estimate_meaning_loss(
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str = "en",
    ) -> list[MeaningLossFlag]:
        """Heuristic estimation of potential meaning loss.

        Checks for:
        - Very short translations (potential truncation)
        - Length ratio anomalies (expansion/contraction beyond 5x)
        - Untranslated segments (source text appearing in target)

        This is a basic heuristic; LLM-based estimation is more accurate.
        """
        flags: list[MeaningLossFlag] = []

        if not translated_text:
            flags.append(MeaningLossFlag.LOW_CONFIDENCE)
            return flags

        source_words = len(source_text.split())
        target_words = len(translated_text.split())

        if source_words > 1 and target_words == 0:
            flags.append(MeaningLossFlag.LOW_CONFIDENCE)

        ratio = target_words / max(source_words, 1)
        if ratio > 5.0 or ratio < 0.2:
            flags.append(MeaningLossFlag.LOW_CONFIDENCE)

        source_lower = source_text.lower()
        target_lower = translated_text.lower()
        if source_lang != target_lang and len(source_lower) > 10:
            for word in source_lower.split():
                if len(word) > 4 and word in target_lower:
                    flags.append(MeaningLossFlag.UNKNOWN)
                    break

        return flags

    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str = "en",
    ) -> TranslationEntry:
        """Translate text and attach uncertainty metadata.

        If no translator callable is configured, returns an entry with
        empty translated_text and confidence 0.0.
        """
        if not self._translator:
            return TranslationEntry(
                source_text=text,
                translated_text="",
                source_language=source_lang,
                target_language=target_lang,
                confidence=0.0,
                meaning_loss_flags=[MeaningLossFlag.LOW_CONFIDENCE],
            )

        result = await self._translator(text, source_lang, target_lang)
        translated = result.get("translated_text", "")
        confidence = result.get("confidence", 0.0)
        flags_raw = result.get("meaning_loss_flags", [])
        method = result.get("method", "external")
        model_name = result.get("model_name", "")

        flags = [
            MeaningLossFlag(f) if isinstance(f, str) else f
            for f in flags_raw
        ]

        heuristic = self.estimate_meaning_loss(
            text, translated, source_lang, target_lang
        )
        for hf in heuristic:
            if hf not in flags:
                flags.append(hf)

        return TranslationEntry(
            source_text=text,
            translated_text=translated,
            source_language=source_lang,
            target_language=target_lang,
            confidence=confidence,
            translation_method=method,
            meaning_loss_flags=flags,
            model_name=model_name,
        )

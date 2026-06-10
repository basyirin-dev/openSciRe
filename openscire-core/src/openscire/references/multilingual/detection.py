# SPDX-License-Identifier: Apache-2.0

"""Language detection on ingestion.

Auto-detects the language of title/abstract text when bridge clients
fetch metadata.  Uses langdetect by default (lightweight, 55 languages)
with a fallback to 'unknown' for short or ambiguous text.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class LanguageDetector:
    """Detect language of text using langdetect.

    Lightweight — pure Python, no model downloads.  Covers 55 languages.
    For broader coverage (176 languages), use fasttext via the
    multilingual extra.

    Usage:
        detector = LanguageDetector()
        lang = detector.detect("This is English text")
        lang, conf = detector.detect_with_confidence("Ceci est du français")
    """

    def __init__(self) -> None:
        self._detector: Any = None  # noqa: ANN401

    def _lazy_init(self) -> None:
        if self._detector is not None:
            return
        try:
            from langdetect import DetectorFactory

            DetectorFactory.seed = 42
            import langdetect as _ld  # noqa: F811

            self._detector = _ld
        except ImportError:
            logger.warning("langdetect not installed. Install with: pip install langdetect")
            self._detector = False

    def detect(self, text: str) -> str:
        """Detect language, returning ISO 639-1 code or 'unknown'."""
        self._lazy_init()
        if not text or not text.strip():
            return "unknown"
        if self._detector is False:
            return "unknown"
        try:
            return self._detector.detect(text)  # type: ignore[no-any-return]
        except Exception:
            return "unknown"

    def detect_with_confidence(self, text: str) -> tuple[str, float]:
        """Detect language with confidence score.

        Returns (language_code, confidence) or ('unknown', 0.0).
        """
        self._lazy_init()
        if not text or not text.strip():
            return "unknown", 0.0
        if self._detector is False:
            return "unknown", 0.0
        try:
            results = self._detector.detect_langs(text)
            if results:
                return str(results[0].lang), float(results[0].prob)
            return "unknown", 0.0
        except Exception:
            return "unknown", 0.0

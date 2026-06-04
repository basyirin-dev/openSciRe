# SPDX-License-Identifier: Apache-2.0

"""Multilingual corpus support: language detection, translation, and embeddings."""

from openscire.references.multilingual.detection import LanguageDetector
from openscire.references.multilingual.embedding import MultilingualEmbedder
from openscire.references.multilingual.models import (
    MeaningLossFlag,
    ParallelText,
    TranslationEntry,
)

__all__ = [
    "LanguageDetector",
    "MultilingualEmbedder",
    "ParallelText",
    "TranslationEntry",
    "MeaningLossFlag",
]

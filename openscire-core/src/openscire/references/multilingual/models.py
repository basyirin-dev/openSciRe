# SPDX-License-Identifier: Apache-2.0

"""Data models for multilingual corpus support.

Defines ParallelText and TranslationEntry for carrying original-language
content alongside translations, with uncertainty metadata.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class MeaningLossFlag(StrEnum):
    """Flags indicating potential meaning loss in a translation."""
    IDIOM = "idiom"
    TECHNICAL_TERM = "technical_term"
    AMBIGUOUS_GRAMMAR = "ambiguous_grammar"
    CULTURAL_REFERENCE = "cultural_reference"
    LOW_CONFIDENCE = "low_confidence"
    UNKNOWN = "unknown"


class TranslationEntry(BaseModel):
    """A single translation with uncertainty metadata.

    Carries both source and target text, along with confidence scoring
    and flags for potential meaning loss.  The translation itself may
    come from an LLM, a dedicated translation model (NLLB-200, M2M-100),
    or an external API — the method is recorded but not enforced here.
    """
    source_text: str = ""
    translated_text: str = ""
    source_language: str = ""
    target_language: str = "en"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    translation_method: str = ""
    meaning_loss_flags: list[MeaningLossFlag] = Field(default_factory=list)
    model_name: str = ""


class ParallelText(BaseModel):
    """Original text alongside its translation.

    Used to store non-English title and abstract content while preserving
    the original for reference and verification.
    """
    original: str = ""
    translated: str = ""
    source_language: str = ""
    target_language: str = "en"
    translation: TranslationEntry | None = None

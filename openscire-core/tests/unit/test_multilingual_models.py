# SPDX-License-Identifier: Apache-2.0

import pytest
from openscire.references.multilingual.models import (
    MeaningLossFlag,
    ParallelText,
    TranslationEntry,
)


class TestMeaningLossFlag:
    def test_values(self) -> None:
        assert MeaningLossFlag.IDIOM.value == "idiom"
        assert MeaningLossFlag.TECHNICAL_TERM.value == "technical_term"
        assert MeaningLossFlag.AMBIGUOUS_GRAMMAR.value == "ambiguous_grammar"
        assert MeaningLossFlag.CULTURAL_REFERENCE.value == "cultural_reference"
        assert MeaningLossFlag.LOW_CONFIDENCE.value == "low_confidence"
        assert MeaningLossFlag.UNKNOWN.value == "unknown"

    def test_from_string(self) -> None:
        assert MeaningLossFlag("idiom") == MeaningLossFlag.IDIOM
        assert MeaningLossFlag("low_confidence") == MeaningLossFlag.LOW_CONFIDENCE


class TestTranslationEntry:
    def test_defaults(self) -> None:
        entry = TranslationEntry()
        assert entry.source_text == ""
        assert entry.translated_text == ""
        assert entry.source_language == ""
        assert entry.target_language == "en"
        assert entry.confidence == 0.0
        assert entry.translation_method == ""
        assert entry.meaning_loss_flags == []
        assert entry.model_name == ""

    def test_full_construction(self) -> None:
        entry = TranslationEntry(
            source_text="Bonjour le monde",
            translated_text="Hello world",
            source_language="fr",
            target_language="en",
            confidence=0.95,
            translation_method="llm",
            meaning_loss_flags=[MeaningLossFlag.IDIOM],
            model_name="gpt-4",
        )
        assert entry.source_text == "Bonjour le monde"
        assert entry.translated_text == "Hello world"
        assert entry.source_language == "fr"
        assert entry.confidence == 0.95
        assert entry.meaning_loss_flags == [MeaningLossFlag.IDIOM]

    def test_confidence_bounds(self) -> None:
        with pytest.raises(ValueError, match="less_than_equal"):
            TranslationEntry(confidence=1.5)
        with pytest.raises(ValueError, match="greater_than_equal"):
            TranslationEntry(confidence=-0.1)


class TestParallelText:
    def test_defaults(self) -> None:
        pt = ParallelText()
        assert pt.original == ""
        assert pt.translated == ""
        assert pt.source_language == ""
        assert pt.target_language == "en"
        assert pt.translation is None

    def test_with_translation(self) -> None:
        trans = TranslationEntry(
            source_text="Hola mundo",
            translated_text="Hello world",
            source_language="es",
            confidence=0.9,
        )
        pt = ParallelText(
            original="Hola mundo",
            translated="Hello world",
            source_language="es",
            translation=trans,
        )
        assert pt.original == "Hola mundo"
        assert pt.translated == "Hello world"
        assert pt.translation is not None
        assert pt.translation.confidence == 0.9

    def test_roundtrip(self) -> None:
        pt = ParallelText(
            original="今天天气很好",
            translated="The weather is nice today",
            source_language="zh",
        )
        serialized = pt.model_dump()
        restored = ParallelText.model_validate(serialized)
        assert restored.original == pt.original
        assert restored.translated == pt.translated
        assert restored.source_language == pt.source_language

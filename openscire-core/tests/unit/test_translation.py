# SPDX-License-Identifier: Apache-2.0

import pytest
from openscire.references.multilingual.models import MeaningLossFlag
from openscire.references.multilingual.translation import TranslationService


class TestTranslationService:
    @pytest.mark.asyncio
    async def test_translate_no_translator(self) -> None:
        service = TranslationService()
        entry = await service.translate("Bonjour le monde", "fr")
        assert entry.source_text == "Bonjour le monde"
        assert entry.translated_text == ""
        assert entry.confidence == 0.0
        assert MeaningLossFlag.LOW_CONFIDENCE in entry.meaning_loss_flags

    @pytest.mark.asyncio
    async def test_translate_with_mock_translator(self) -> None:
        async def mock_translator(_text: str, _src: str, _tgt: str) -> dict:
            return {
                "translated_text": "Hello world",
                "confidence": 0.92,
                "meaning_loss_flags": [],
                "method": "mock",
                "model_name": "mock-model",
            }

        service = TranslationService(translator=mock_translator)
        entry = await service.translate("Bonjour le monde", "fr")
        assert entry.translated_text == "Hello world"
        assert entry.confidence == 0.92
        assert entry.translation_method == "mock"
        assert entry.model_name == "mock-model"

    def test_estimate_meaning_loss_no_loss(self) -> None:
        flags = TranslationService.estimate_meaning_loss(
            "Hello world", "Bonjour le monde", "en", "fr"
        )
        assert flags == []

    def test_estimate_meaning_loss_empty_translation(self) -> None:
        flags = TranslationService.estimate_meaning_loss(
            "Hello world", "", "en", "fr"
        )
        assert MeaningLossFlag.LOW_CONFIDENCE in flags

    def test_estimate_meaning_loss_ratio_anomaly(self) -> None:
        short_source = "Hi"
        long_translation = " ".join(["word"] * 20)
        flags = TranslationService.estimate_meaning_loss(
            short_source, long_translation, "en", "fr"
        )
        assert MeaningLossFlag.LOW_CONFIDENCE in flags

    def test_estimate_meaning_loss_untranslated_segment(self) -> None:
        flags = TranslationService.estimate_meaning_loss(
            "This is a test of the emergency broadcast system",
            "Ceci est un test of the emergency broadcast system",
            "en",
            "fr",
        )
        assert MeaningLossFlag.UNKNOWN in flags

    @pytest.mark.asyncio
    async def test_translate_with_meaning_loss_flags(self) -> None:
        async def mock_translator(_text: str, _src: str, _tgt: str) -> dict:
            return {
                "translated_text": "short",
                "confidence": 0.5,
                "meaning_loss_flags": ["idiom"],
                "method": "mock",
            }

        service = TranslationService(translator=mock_translator)
        entry = await service.translate(
            "This is a very long sentence that should trigger ratio warnings",
            "en",
        )
        assert MeaningLossFlag.IDIOM in entry.meaning_loss_flags

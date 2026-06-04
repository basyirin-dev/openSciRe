# SPDX-License-Identifier: Apache-2.0

from openscire.references.multilingual.detection import LanguageDetector


class TestLanguageDetector:
    def test_detect_english(self) -> None:
        detector = LanguageDetector()
        lang = detector.detect("This is a test sentence in English.")
        assert lang == "en"

    def test_detect_french(self) -> None:
        detector = LanguageDetector()
        lang = detector.detect("Ceci est une phrase de test en français.")
        assert lang == "fr"

    def test_detect_spanish(self) -> None:
        detector = LanguageDetector()
        lang = detector.detect("Esta es una frase de prueba en español.")
        assert lang == "es"

    def test_detect_chinese(self) -> None:
        detector = LanguageDetector()
        lang = detector.detect("这是一句中文测试句子。")
        assert lang == "zh-cn" or lang == "zh"

    def test_detect_german(self) -> None:
        detector = LanguageDetector()
        lang = detector.detect("Dies ist ein deutscher Testsatz.")
        assert lang == "de"

    def test_detect_empty_text(self) -> None:
        detector = LanguageDetector()
        assert detector.detect("") == "unknown"
        assert detector.detect("   ") == "unknown"
        assert detector.detect(None) == "unknown"  # type: ignore[arg-type]

    def test_detect_short_text(self) -> None:
        detector = LanguageDetector()
        lang = detector.detect("Hello world, this is a test.")
        assert lang == "en"

    def test_detect_with_confidence_english(self) -> None:
        detector = LanguageDetector()
        lang, conf = detector.detect_with_confidence(
            "The quick brown fox jumps over the lazy dog."
        )
        assert lang == "en"
        assert conf > 0.5

    def test_detect_with_confidence_empty(self) -> None:
        detector = LanguageDetector()
        assert detector.detect_with_confidence("") == ("unknown", 0.0)

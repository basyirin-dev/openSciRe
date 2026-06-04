"""Tests for MultilingualEmbedder.

These tests mock sentence_transformers at sys.modules level to avoid
downloading models or requiring the package to be installed.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock sentence_transformers and torch at module level before importing the SUT
sys.modules["sentence_transformers"] = MagicMock()
sys.modules["torch"] = MagicMock()

from openscire.references.multilingual.embedding import MultilingualEmbedder  # noqa: E402


class TestMultilingualEmbedder:
    def test_unsupported_model(self) -> None:
        with pytest.raises(ValueError, match="Unsupported model"):
            MultilingualEmbedder(model_name="nonexistent")

    def test_supported_models_listed(self) -> None:
        assert "labse" in MultilingualEmbedder.SUPPORTED_MODELS
        assert "mE5-large" in MultilingualEmbedder.SUPPORTED_MODELS
        assert "bge-m3" in MultilingualEmbedder.SUPPORTED_MODELS

    def test_model_languages(self) -> None:
        embedder = MultilingualEmbedder()
        assert embedder.model_languages == 109

    def test_similarity(self) -> None:
        a = [1.0, 0.0, 0.0]
        b = [1.0, 0.0, 0.0]
        assert MultilingualEmbedder.similarity(a, b) == pytest.approx(1.0)

    def test_similarity_orthogonal(self) -> None:
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert MultilingualEmbedder.similarity(a, b) == pytest.approx(0.0)

    def test_similarity_zero_vector(self) -> None:
        a = [0.0, 0.0]
        b = [1.0, 0.0]
        assert MultilingualEmbedder.similarity(a, b) == 0.0

    def test_similarity_negative(self) -> None:
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert MultilingualEmbedder.similarity(a, b) == pytest.approx(-1.0)

    @patch("sentence_transformers.SentenceTransformer")
    def test_encode(self, mock_st: MagicMock) -> None:
        mock_model = MagicMock()
        mock_model.encode.return_value = [[0.1, 0.2], [0.3, 0.4]]
        mock_model.get_sentence_embedding_dimension.return_value = 2
        mock_st.return_value = mock_model

        embedder = MultilingualEmbedder(model_name="labse")
        embedder._model = mock_model
        vecs = embedder.encode(["hello", "world"])
        assert len(vecs) == 2
        assert len(vecs[0]) == 2

    @patch("sentence_transformers.SentenceTransformer")
    def test_encode_empty(self, mock_st: MagicMock) -> None:
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 2
        mock_st.return_value = mock_model

        embedder = MultilingualEmbedder(model_name="labse")
        embedder._model = mock_model
        assert embedder.encode([]) == []

    @patch("sentence_transformers.SentenceTransformer")
    def test_encode_query(self, mock_st: MagicMock) -> None:
        mock_model = MagicMock()
        mock_model.encode.return_value = [[0.5, 0.5]]
        mock_model.get_sentence_embedding_dimension.return_value = 2
        mock_st.return_value = mock_model

        embedder = MultilingualEmbedder(model_name="labse")
        embedder._model = mock_model
        vec = embedder.encode_query("test query")
        assert len(vec) == 2

    @patch("sentence_transformers.SentenceTransformer")
    def test_embedding_dimension(self, mock_st: MagicMock) -> None:
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 768
        mock_st.return_value = mock_model

        embedder = MultilingualEmbedder(model_name="labse")
        embedder._model = mock_model
        assert embedder.embedding_dimension == 768

    @patch("sentence_transformers.SentenceTransformer")
    def test_cross_lingual_retrieve(self, mock_st: MagicMock) -> None:
        mock_model = MagicMock()
        mock_model.encode.return_value = [
            [1.0, 0.0],
            [0.0, 1.0],
            [0.9, 0.1],
        ]
        mock_model.get_sentence_embedding_dimension.return_value = 2
        mock_st.return_value = mock_model

        embedder = MultilingualEmbedder(model_name="labse")
        embedder._model = mock_model
        candidates = [
            ("hello", {"id": 1}),
            ("bonjour", {"id": 2}),
            ("hola", {"id": 3}),
        ]
        results = embedder.cross_lingual_retrieve("hello", candidates, top_k=2)
        assert len(results) == 2
        assert results[0][0]["id"] == 1  # most similar to "hello"

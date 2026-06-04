import tempfile
from pathlib import Path

import pytest

faiss = pytest.importorskip("faiss")

from openscire.references.indexing.backends.faiss_backend import FaissBackend  # noqa: E402


class TestFaissBackend:
    def test_add_and_search(self):
        backend = FaissBackend(dimension=4)
        backend.add(
            ["doc1", "doc2", "doc3"],
            [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]],
            [{"id": "doc1"}, {"id": "doc2"}, {"id": "doc3"}],
        )
        results = backend.search([1.0, 0.0, 0.0, 0.0], top_k=2)
        assert len(results) == 2
        assert results[0][0] == "doc1"
        assert results[0][1] > 0.99

    def test_count(self):
        backend = FaissBackend(dimension=4)
        assert backend.count() == 0
        backend.add(
            ["doc1"],
            [[1.0, 0.0, 0.0, 0.0]],
        )
        assert backend.count() == 1

    def test_delete(self):
        backend = FaissBackend(dimension=4)
        backend.add(
            ["doc1", "doc2"],
            [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]],
        )
        assert backend.count() == 2
        backend.delete(["doc1"])
        assert backend.count() == 1
        results = backend.search([1.0, 0.0, 0.0, 0.0], top_k=5)
        assert len(results) <= 1

    def test_save_and_load(self):
        backend = FaissBackend(dimension=4)
        backend.add(
            ["doc1", "doc2"],
            [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]],
            [{"title": "Paper 1"}, {"title": "Paper 2"}],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "faiss_index")
            backend.save(path)
            new_backend = FaissBackend(dimension=4)
            new_backend.load(path)
            assert new_backend.count() == 2
            results = new_backend.search([1.0, 0.0, 0.0, 0.0], top_k=1)
            assert len(results) == 1
            assert results[0][0] == "doc1"
            assert results[0][2]["title"] == "Paper 1"

    def test_clear(self):
        backend = FaissBackend(dimension=4)
        backend.add(["doc1"], [[1.0, 0.0, 0.0, 0.0]])
        backend.clear()
        assert backend.count() == 0
        assert backend._id_map == {}

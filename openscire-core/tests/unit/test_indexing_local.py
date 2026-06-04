import tempfile
from pathlib import Path

from openscire.references.indexing.backends.local_backend import LocalBackend


class TestLocalBackend:
    def test_add_and_search(self):
        backend = LocalBackend(dimension=4)
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
        backend = LocalBackend(dimension=4)
        assert backend.count() == 0
        backend.add(["doc1"], [[1.0, 0.0, 0.0, 0.0]])
        assert backend.count() == 1

    def test_delete(self):
        backend = LocalBackend(dimension=4)
        backend.add(
            ["doc1", "doc2"],
            [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]],
        )
        assert backend.count() == 2
        backend.delete(["doc1"])
        assert backend.count() == 1

    def test_save_and_load(self):
        backend = LocalBackend(dimension=4)
        backend.add(
            ["doc1"],
            [[1.0, 0.0, 0.0, 0.0]],
            [{"title": "Paper 1"}],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "local_index")
            backend.save(path)
            new_backend = LocalBackend(dimension=4)
            new_backend.load(path)
            assert new_backend.count() == 1
            results = new_backend.search([1.0, 0.0, 0.0, 0.0], top_k=1)
            assert len(results) == 1
            assert results[0][0] == "doc1"

    def test_clear(self):
        backend = LocalBackend(dimension=4)
        backend.add(["doc1"], [[1.0, 0.0, 0.0, 0.0]])
        backend.clear()
        assert backend.count() == 0

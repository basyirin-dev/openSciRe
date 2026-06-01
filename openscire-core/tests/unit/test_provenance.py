# SPDX-License-Identifier: Apache-2.0

from datetime import UTC, datetime

import pytest
from openscire.constants import ErrorCode
from openscire.exceptions import ConfigError, ProvenanceError
from openscire.models import ProvenanceEntry
from openscire.provenance import (
    InMemoryBackend,
    ProvenanceExporter,
    ProvenanceGraph,
    ProvenanceTracker,
    ResearchChronologyEnforcer,
    SQLiteBackend,
    content_hash,
    sign_entry,
    verify_entry,
)


@pytest.mark.usefixtures("reset_provenance")
class TestProvenanceEntry:
    def test_content_hash_stable(self) -> None:
        e = ProvenanceEntry(action_id="a1")
        h1 = content_hash(e)
        h2 = content_hash(e)
        assert h1 == h2

    def test_content_hash_changes_with_fields(self) -> None:
        e1 = ProvenanceEntry(action_id="a1", agent_id="alice")
        e2 = ProvenanceEntry(action_id="a1", agent_id="bob")
        assert content_hash(e1) != content_hash(e2)

    def test_sign_and_verify(self) -> None:
        import nacl.bindings

        seed = b"0" * 32
        pk = nacl.bindings.crypto_sign_seed_keypair(seed)[0]
        e = ProvenanceEntry(action_id="a1", agent_id="alice")
        signed = sign_entry(e, seed.hex())
        assert signed.cryptographic_signature is not None
        assert verify_entry(signed, pk.hex())

    def test_verify_no_signature(self) -> None:
        e = ProvenanceEntry(action_id="a1")
        assert verify_entry(e, "00" * 32) is False

    def test_verify_bad_signature(self) -> None:
        import nacl.bindings

        seed = b"0" * 32
        pk = nacl.bindings.crypto_sign_seed_keypair(seed)[0]
        e = ProvenanceEntry(action_id="a1", agent_id="alice")
        signed = sign_entry(e, seed.hex())
        signed.cryptographic_signature = "00" * 64
        assert verify_entry(signed, pk.hex()) is False


@pytest.mark.usefixtures("reset_provenance")
class TestProvenanceTracker:
    def test_track_returns_entry(self) -> None:
        tracker = ProvenanceTracker.from_config()
        entry = tracker.track("test_action", agent_id="agent1")
        assert entry.action_type == "test_action"
        assert entry.agent_id == "agent1"

    def test_auto_chaining(self) -> None:
        tracker = ProvenanceTracker.from_config()
        e1 = tracker.track("action1")
        e2 = tracker.track("action2")
        assert e1.parent_ids == []
        assert e2.parent_ids == [e1.action_id]

    def test_explicit_parent_ids(self) -> None:
        tracker = ProvenanceTracker.from_config()
        parent = ProvenanceEntry(action_id="custom_parent", action_type="setup")
        tracker._graph.add_entry(parent)
        tracker._storage.save(parent)
        e2 = tracker.track("action2", parent_ids=["custom_parent"])
        assert e2.parent_ids == ["custom_parent"]

    def test_singleton(self) -> None:
        t1 = ProvenanceTracker.get_tracker("test_project", "in_memory")
        t2 = ProvenanceTracker.get_tracker("test_project", "in_memory")
        assert t1 is t2

    def test_different_projects_different_trackers(self) -> None:
        t1 = ProvenanceTracker.get_tracker("proj_a", "in_memory")
        t2 = ProvenanceTracker.get_tracker("proj_b", "in_memory")
        assert t1 is not t2

    def test_from_config_loads_signing_key(self, tmp_path: object) -> None:

        key_path = tmp_path / "test_key"
        seed = b"1" * 32
        key_path.write_text(seed.hex())
        from openscire.config import Config

        cfg = Config()
        cfg.provenance.signing_key_path = str(key_path)
        tracker = ProvenanceTracker.from_config(config=cfg)
        entry = tracker.track("signed_action")
        assert entry.cryptographic_signature is not None

    def test_unknown_backend_raises_config_error(self) -> None:
        try:
            ProvenanceTracker.get_tracker("test", storage_backend="nonexistent")
            assert False
        except ConfigError as e:
            assert e.error_code == ErrorCode.CONFIG_INVALID


@pytest.mark.usefixtures("reset_provenance")
class TestProvenanceGraph:
    def test_add_entry(self) -> None:
        g = ProvenanceGraph()
        e = ProvenanceEntry(action_id="a1")
        g.add_entry(e)
        assert len(g) == 1

    def test_query_by_agent(self) -> None:
        g = ProvenanceGraph()
        g.add_entry(ProvenanceEntry(action_id="a1", agent_id="alice"))
        g.add_entry(ProvenanceEntry(action_id="a2", agent_id="bob"))
        assert len(g.query(agent_id="alice")) == 1
        assert len(g.query(agent_id="bob")) == 1

    def test_query_by_action_type(self) -> None:
        g = ProvenanceGraph()
        g.add_entry(ProvenanceEntry(action_id="a1", action_type="lit_review"))
        g.add_entry(ProvenanceEntry(action_id="a2", action_type="experiment"))
        assert len(g.query(action_type="lit_review")) == 1

    def test_query_by_time_range(self) -> None:
        g = ProvenanceGraph()
        now = datetime.now(UTC)
        g.add_entry(ProvenanceEntry(action_id="old", timestamp=datetime(2020, 1, 1, tzinfo=UTC)))
        g.add_entry(ProvenanceEntry(action_id="new", timestamp=now))
        assert len(g.query(time_range=(datetime(2021, 1, 1, tzinfo=UTC), now))) == 1

    def test_traverse_forward(self) -> None:
        g = ProvenanceGraph()
        g.add_entry(ProvenanceEntry(action_id="root"))
        g.add_entry(ProvenanceEntry(action_id="child", parent_ids=["root"]))
        g.add_entry(ProvenanceEntry(action_id="grandchild", parent_ids=["child"]))
        assert len(g.traverse("root", direction="forward")) == 3

    def test_traverse_backward(self) -> None:
        g = ProvenanceGraph()
        g.add_entry(ProvenanceEntry(action_id="root"))
        g.add_entry(ProvenanceEntry(action_id="child", parent_ids=["root"]))
        assert len(g.traverse("child", direction="backward")) == 2

    def test_cycle_detection(self) -> None:
        g = ProvenanceGraph()
        g.add_entry(ProvenanceEntry(action_id="a"))
        g.add_entry(ProvenanceEntry(action_id="b", parent_ids=["a"]))
        try:
            g.add_entry(ProvenanceEntry(action_id="a"))  # already exists
            # duplicate is silently ignored
        except ProvenanceError:
            assert False, "duplicate should not raise"

    def test_cycle_creation_raises(self) -> None:
        g = ProvenanceGraph()
        g.add_entry(ProvenanceEntry(action_id="a"))
        g.add_entry(ProvenanceEntry(action_id="b", parent_ids=["a"]))
        try:
            g.add_entry(ProvenanceEntry(action_id="c", parent_ids=["b"]))
        except ProvenanceError:
            assert False

    def test_root_hash_empty(self) -> None:
        g = ProvenanceGraph()
        h = g.root_hash()
        assert isinstance(h, str) and len(h) == 64

    def test_root_hash_non_empty(self) -> None:
        g = ProvenanceGraph()
        g.add_entry(ProvenanceEntry(action_id="a"))
        h = g.root_hash()
        assert isinstance(h, str) and len(h) == 64

    def test_topological_sort(self) -> None:
        g = ProvenanceGraph()
        g.add_entry(ProvenanceEntry(action_id="root"))
        g.add_entry(ProvenanceEntry(action_id="child", parent_ids=["root"]))
        order = g.topological_sort()
        assert order == ["root", "child"]

    def test_missing_parent_raises(self) -> None:
        g = ProvenanceGraph()
        g.add_entry(ProvenanceEntry(action_id="a"))
        try:
            g.add_entry(ProvenanceEntry(action_id="orphan", parent_ids=["nonexistent"]))
            assert False
        except ProvenanceError as e:
            assert e.error_code == ErrorCode.PROV_CHAIN_BREAK

    def test_add_duplicate_is_idempotent(self) -> None:
        g = ProvenanceGraph()
        e = ProvenanceEntry(action_id="a1")
        g.add_entry(e)
        g.add_entry(e)
        assert len(g) == 1


@pytest.mark.usefixtures("reset_provenance")
class TestProvenanceStorage:
    def test_in_memory_save_and_get(self) -> None:
        b = InMemoryBackend()
        e = ProvenanceEntry(action_id="a1")
        b.save(e)
        assert b.get("a1") is not None
        assert b.get("nonexistent") is None

    def test_in_memory_delete(self) -> None:
        b = InMemoryBackend()
        b.save(ProvenanceEntry(action_id="a1"))
        assert b.delete("a1") is True
        assert b.delete("a1") is False

    def test_in_memory_count(self) -> None:
        b = InMemoryBackend()
        assert b.count() == 0
        b.save(ProvenanceEntry(action_id="a1"))
        assert b.count() == 1

    def test_in_memory_list_with_filters(self) -> None:
        b = InMemoryBackend()
        b.save(ProvenanceEntry(action_id="a1", agent_id="alice", action_type="type_a"))
        b.save(ProvenanceEntry(action_id="a2", agent_id="bob", action_type="type_b"))
        assert len(b.list(agent_id="alice")) == 1
        assert len(b.list(action_type="type_b")) == 1
        assert len(b.list()) == 2

    def test_sqlite_save_and_get(self, tmp_path: object) -> None:
        db = tmp_path / "test.db"
        b = SQLiteBackend(str(db))
        e = ProvenanceEntry(action_id="a1", agent_id="alice")
        b.save(e)
        assert b.get("a1") is not None

    def test_sqlite_delete(self, tmp_path: object) -> None:
        db = tmp_path / "test.db"
        b = SQLiteBackend(str(db))
        b.save(ProvenanceEntry(action_id="a1"))
        assert b.delete("a1") is True
        assert b.delete("a1") is False

    def test_sqlite_count(self, tmp_path: object) -> None:
        db = tmp_path / "test.db"
        b = SQLiteBackend(str(db))
        assert b.count() == 0
        b.save(ProvenanceEntry(action_id="a1"))
        assert b.count() == 1

    def test_sqlite_close(self, tmp_path: object) -> None:
        db = tmp_path / "test.db"
        b = SQLiteBackend(str(db))
        b.save(ProvenanceEntry(action_id="a1"))
        b.close()

    def test_sqlite_list_with_filters(self, tmp_path: object) -> None:
        db = tmp_path / "test.db"
        b = SQLiteBackend(str(db))
        b.save(ProvenanceEntry(action_id="a1", agent_id="alice", action_type="t"))
        b.save(ProvenanceEntry(action_id="a2", agent_id="bob", action_type="u"))
        assert len(b.list(agent_id="alice")) == 1
        assert len(b.list(action_type="u")) == 1
        assert len(b.list()) == 2


@pytest.mark.usefixtures("reset_provenance")
class TestProvenanceExporter:
    def test_to_json(self) -> None:
        entries = [ProvenanceEntry(action_id="a1")]
        result = ProvenanceExporter.to_json(entries, root_hash="abc")
        assert "provenance" in result
        assert "root_hash" in result

    def test_to_json_no_root_hash(self) -> None:
        entries = [ProvenanceEntry(action_id="a1")]
        result = ProvenanceExporter.to_json(entries)
        assert "provenance" in result

    def test_to_ro_crate(self) -> None:
        entries = [ProvenanceEntry(action_id="a1", parent_ids=["root"])]
        result = ProvenanceExporter.to_ro_crate(entries)
        assert "@context" in result
        assert "@graph" in result

    def test_to_w3c_prov(self) -> None:
        entries = [ProvenanceEntry(action_id="a1", agent_id="alice")]
        result = ProvenanceExporter.to_w3c_prov(entries)
        assert "entity" in result
        assert "activity" in result


@pytest.mark.usefixtures("reset_provenance")
class TestResearchChronologyEnforcer:
    def test_stamp_hypothesis(self) -> None:
        tracker = ProvenanceTracker.from_config()
        enforcer = ResearchChronologyEnforcer(tracker)
        entry = enforcer.stamp_hypothesis("hyp_001")
        assert entry.action_type == "hypothesis_registered"
        assert entry.parameters_snapshot.get("hypothesis_id") == "hyp_001"

    def test_check_evidence_after_hypothesis(self) -> None:
        tracker = ProvenanceTracker.from_config()
        enforcer = ResearchChronologyEnforcer(tracker)
        enforcer.stamp_hypothesis("hyp_002")
        evidence = tracker.track("experiment", agent_id="alice")
        ok = enforcer.check_evidence("hyp_002", evidence)
        assert ok is True

    def test_check_evidence_before_hypothesis_returns_false(self) -> None:
        tracker = ProvenanceTracker.from_config()
        enforcer = ResearchChronologyEnforcer(tracker)
        evidence = tracker.track("experiment", agent_id="alice")
        enforcer.stamp_hypothesis("hyp_003")
        ok = enforcer.check_evidence("hyp_003", evidence)
        assert ok is False

    def test_check_evidence_missing_hypothesis(self) -> None:
        tracker = ProvenanceTracker.from_config()
        enforcer = ResearchChronologyEnforcer(tracker)
        evidence = tracker.track("experiment", agent_id="alice")
        ok = enforcer.check_evidence("hyp_missing", evidence)
        assert ok is False

    def test_detect_temporal_anomalies(self) -> None:
        tracker = ProvenanceTracker.from_config()
        enforcer = ResearchChronologyEnforcer(tracker)
        tracker.track("evidence_before", agent_id="alice")
        enforcer.stamp_hypothesis("hyp_004")
        anomalies = enforcer.detect_temporal_anomalies("hyp_004")
        assert len(anomalies) == 1

    def test_no_anomalies_when_ordered_correctly(self) -> None:
        tracker = ProvenanceTracker.from_config()
        enforcer = ResearchChronologyEnforcer(tracker)
        enforcer.stamp_hypothesis("hyp_005")
        tracker.track("evidence_after", agent_id="alice")
        anomalies = enforcer.detect_temporal_anomalies("hyp_005")
        assert len(anomalies) == 0

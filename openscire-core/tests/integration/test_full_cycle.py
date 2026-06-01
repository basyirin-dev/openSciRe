# SPDX-License-Identifier: Apache-2.0

"""Integration test: config -> context -> hypothesis -> provenance entry -> export -> verify."""

import json

import pytest
from openscire.config import Config
from openscire.models import Hypothesis, HypothesisStatus, ResearchContext
from openscire.provenance import ProvenanceExporter, ProvenanceTracker, verify_entry
from openscire.serialization import Serializer


@pytest.mark.usefixtures("reset_provenance")
def test_full_cycle() -> None:
    cfg = Config()
    cfg.logging.level = "WARNING"

    tracker = ProvenanceTracker.from_config(config=cfg)
    ctx = ResearchContext(
        research_question="Does molecule X bind to receptor Y?",
        domain="computational_biology",
        project_id="int_test_001",
    )
    tracker.track("context_created", params={"research_question": ctx.research_question})

    hypothesis = Hypothesis(
        claim="Molecule X binds to receptor Y with Kd < 10uM",
        null_hypothesis="Molecule X does not bind to receptor Y",
        falsification_criteria=["Kd > 10uM", "no binding in SPR"],
        domain_tags=["computational_biology", "drug_discovery"],
        status=HypothesisStatus.proposed,
    )
    tracker.track(
        "hypothesis_proposed",
        agent_id="test_agent",
        params=hypothesis.model_dump(mode="python"),
    )
    tracker.track(
        "molecular_docking",
        agent_id="autodock_vina",
        params={"software": "autodock_vina", "exhaustiveness": 8},
        input_hash="receptor_pdb:abc123",
        output_hash="docking_results:def456",
    )
    last_entry = tracker.track("evaluation", agent_id="test_agent")

    assert last_entry.cryptographic_signature is None
    assert len(tracker.graph) == 4

    serialized = Serializer.dumps(hypothesis, format="json")
    deserialized = Serializer.loads(serialized, Hypothesis, format="json")
    assert deserialized.claim == hypothesis.claim

    entries = list(tracker.graph.query())
    json_str = ProvenanceExporter.to_json(entries, root_hash=tracker.graph.root_hash())
    json_output = json.loads(json_str)
    assert "provenance" in json_output
    assert len(json_output["provenance"]) == 4

    for entry in entries:
        if entry.cryptographic_signature is not None:
            assert verify_entry(entry, "") is not None


@pytest.mark.usefixtures("reset_provenance")
def test_signed_full_cycle(tmp_path: object) -> None:
    import nacl.bindings

    key_path = tmp_path / "signing_key"
    seed = b"2" * 32
    key_path.write_text(seed.hex())
    pk, _sk = nacl.bindings.crypto_sign_seed_keypair(seed)

    cfg = Config()
    cfg.provenance.signing_key_path = str(key_path)

    tracker = ProvenanceTracker.from_config(config=cfg)
    tracker.track("action1", agent_id="agent1")
    tracker.track("action2", agent_id="agent1")
    last = tracker.track("action3", agent_id="agent1")

    assert last.cryptographic_signature is not None
    assert verify_entry(last, pk.hex())

    entries = list(tracker.graph.query())
    ro_crate = ProvenanceExporter.to_ro_crate(entries)
    assert "@context" in ro_crate
    assert len(ro_crate["@graph"]) == 3

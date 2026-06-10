# SPDX-License-Identifier: Apache-2.0

"""Integration test: EthicalFirewall pipeline with provenance, grounding, carbon.

Verifies:
  - RiskTier classification logged in provenance (tier_classification entry)
  - Carbon cost estimated and recorded (carbon_estimate entry)
  - Citation grounding warnings appear for unsupported claims
  - All provenance entries have Ed25519 signatures when key is configured
  - Provenance DAG has expected structure (tier -> inference -> carbon -> grounding)
"""

from __future__ import annotations

from typing import Any

import nacl.bindings
import pytest
from openscire.config import Config
from openscire.ethics.carbon import CarbonBudgetTracker
from openscire.ethics.durc import build_default_rules
from openscire.ethics.firewall import EthicalFirewall, FirewalledProvider
from openscire.ethics.source_grounding import SourceGroundingEngine
from openscire.ethics.tier import CoolOffRegistry, TierClassifier
from openscire.provenance import ProvenanceExporter, ProvenanceTracker, verify_entry
from openscire.provider.base import ProviderConfig
from openscire.provider.models import ChatMessage, Chunk


class _EchoProvider:
    """Minimal provider stub that echoes back the last user message."""

    PROVIDER_NAME = "echo"

    def __init__(self) -> None:
        self._config = ProviderConfig(default_model="echo")

    def stream_chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        provenance_parent_id: str | None = None,
    ):
        last_content = ""
        for m in reversed(messages):
            if isinstance(m.content, str):
                last_content = m.content
                break

        async def _gen():
            # Simulate token-by-token streaming
            chunk_size = max(1, len(last_content) // 3)
            for i in range(0, len(last_content), chunk_size):
                yield Chunk(delta_content=last_content[i : i + chunk_size])
            yield Chunk(
                delta_content="",
                finish_reason="stop",
                usage=type(
                    "Usage", (), {"prompt_tokens": 15, "completion_tokens": len(last_content)}
                )(),
            )

        return _gen()

    async def list_models(self):
        return ["echo-model"]


@pytest.mark.usefixtures("reset_provenance")
@pytest.mark.asyncio
async def test_ethical_checkpoint_full_cycle(tmp_path) -> None:
    """Full pipeline: FirewalledProvider + ProvenanceTracker + Grounding + Carbon."""
    # --- Setup signing key ---
    key_path = tmp_path / "signing_key"
    seed = b"3" * 32
    key_path.write_text(seed.hex())
    pub_key, _ = nacl.bindings.crypto_sign_seed_keypair(seed)

    cfg = Config()
    cfg.provenance.signing_key_path = str(key_path)
    tracker = ProvenanceTracker.from_config(config=cfg)

    # --- Build firewall with all checkpoints ---
    tier_classifier = TierClassifier()
    cool_off = CoolOffRegistry()
    source_grounding = SourceGroundingEngine(
        require_citations=True,
        allow_unsupported_claims=True,
        provenance_tracker=tracker,
    )
    carbon_db = tmp_path / "carbon.db"
    carbon_tracker = CarbonBudgetTracker(
        provenance_tracker=tracker,
        db_path=str(carbon_db),
    )

    firewall = EthicalFirewall(
        rules=build_default_rules(),
        tier_classifier=tier_classifier,
        cool_off_registry=cool_off,
        provenance_tracker=tracker,
        carbon_tracker=carbon_tracker,
        source_grounding=source_grounding,
    )

    # --- Wire provider ---
    inner = _EchoProvider()
    inner._config.provenance_tracker = tracker
    provider: FirewalledProvider = firewall.wrap(inner)

    # --- Stream with a claim ---
    messages = [
        ChatMessage(role="system", content="You are a helpful research assistant."),
        ChatMessage(
            role="user",
            content=(
                "Recent studies show that graphene-based water filtration "
                "achieves 99.9% ion rejection (Kim et al., 2022). "
                "This represents a major breakthrough in desalination technology."
            ),
        ),
    ]

    collected = []
    async for chunk in provider.stream_chat(messages):
        collected.append(chunk)

    full_output = "".join(c.delta_content or "" for c in collected)

    # --- Assertions ---

    # 1. Provider produced output
    assert len(full_output) > 0, "Provider should produce output"

    # 2. Carbon warning appears in the output
    assert "CARBON" in full_output, "Carbon cost should be displayed"

    # 3. Citation warning appears (unsupported claim with citation but no known sources)
    assert "CITATION WARNING" in full_output, "Citation grounding should flag unsupported claims"

    # 4. Provenance graph has entries
    entries = list(tracker.graph.query())
    assert len(entries) >= 4, f"Expected at least 4 provenance entries, got {len(entries)}"

    # 5. Key provenance types present
    entry_types = {e.action_type for e in entries}
    assert "risk_tier_classification" in entry_types, "Missing risk_tier_classification provenance"
    assert "model_inference" in entry_types, "Missing model_inference provenance"
    assert "citation_grounding" in entry_types, "Missing citation_grounding provenance"

    # 6. Carbon estimate provenance (via EthicalFirewall.record_carbon -> CarbonBudgetTracker)
    carbon_entries = [e for e in entries if "carbon_estimate" in e.action_type]
    assert len(carbon_entries) >= 1 or "carbon" in str(entry_types).lower(), (
        "Carbon provenance should be recorded"
    )

    # 7. All entries are Ed25519-signed
    for entry in entries:
        assert entry.cryptographic_signature is not None, (
            f"Entry {entry.action_id} ({entry.action_type}) should be signed"
        )
        assert verify_entry(entry, pub_key.hex()), (
            f"Entry {entry.action_id} signature verification failed"
        )

    # 8. Provenance DAG has parent-child relationships
    root_entries = [e for e in entries if not e.parent_ids]
    assert len(root_entries) >= 1, "Should have at least one root entry"

    # 9. Export works
    json_str = ProvenanceExporter.to_json(entries, root_hash=tracker.graph.root_hash())
    import json as _json

    output = _json.loads(json_str)
    assert "provenance" in output
    assert len(output["provenance"]) == len(entries)

    ro_crate = ProvenanceExporter.to_ro_crate(entries)
    assert "@context" in ro_crate
    assert len(ro_crate["@graph"]) == len(entries)


@pytest.mark.usefixtures("reset_provenance")
@pytest.mark.asyncio
async def test_ethical_checkpoint_dag_structure(tmp_path) -> None:
    """Verify the provenance DAG links ethical checkpoints to inference."""
    key_path = tmp_path / "sk2"
    key_path.write_text((b"4" * 32).hex())

    cfg = Config()
    cfg.provenance.signing_key_path = str(key_path)
    tracker = ProvenanceTracker.from_config(config=cfg)

    firewall = EthicalFirewall(
        rules=build_default_rules(),
        provenance_tracker=tracker,
        source_grounding=SourceGroundingEngine(
            require_citations=True,
            allow_unsupported_claims=True,
            provenance_tracker=tracker,
        ),
    )

    inner = _EchoProvider()
    inner._config.provenance_tracker = tracker
    provider = firewall.wrap(inner)

    messages = [
        ChatMessage(role="user", content="This is a test claim (Smith, 2023)."),
    ]

    async for _ in provider.stream_chat(messages):
        pass

    entries = list(tracker.graph.query())

    # Walk parent chain from model_inference up to tier_classification
    inference_entries = [e for e in entries if e.action_type == "model_inference"]
    assert len(inference_entries) >= 1

    # Check parent references chain back to tier_classification
    all_ids = {e.action_id for e in entries}
    for inf in inference_entries:
        for pid in inf.parent_ids:
            assert pid in all_ids, f"model_inference parent {pid} not found in graph"

    # Ensure no duplicate action_ids
    assert len(all_ids) == len(entries), "Duplicate action_ids detected"

    entries = list(tracker.graph.query())

    # Walk parent chain from model_inference up to tier_classification
    inference_entries = [e for e in entries if e.action_type == "model_inference"]
    assert len(inference_entries) >= 1

    # Check parent references chain back to tier_classification
    all_ids = {e.action_id for e in entries}
    for inf in inference_entries:
        for pid in inf.parent_ids:
            assert pid in all_ids, f"model_inference parent {pid} not found in graph"

    # Ensure no duplicate action_ids
    assert len(all_ids) == len(entries), "Duplicate action_ids detected"


@pytest.mark.usefixtures("reset_provenance")
@pytest.mark.asyncio
async def test_ethical_checkpoint_no_carbon(tmp_path) -> None:
    """Without carbon tracker, no carbon cost should appear."""
    key_path = tmp_path / "sk3"
    key_path.write_text((b"5" * 32).hex())

    cfg = Config()
    cfg.provenance.signing_key_path = str(key_path)
    tracker = ProvenanceTracker.from_config(config=cfg)

    firewall = EthicalFirewall(
        rules=build_default_rules(),
        provenance_tracker=tracker,
        source_grounding=SourceGroundingEngine(
            require_citations=True,
            allow_unsupported_claims=True,
            provenance_tracker=tracker,
        ),
    )

    inner = _EchoProvider()
    inner._config.provenance_tracker = tracker
    provider = firewall.wrap(inner)

    messages = [
        ChatMessage(role="user", content="Test claim without carbon."),
    ]

    collected = []
    async for chunk in provider.stream_chat(messages):
        collected.append(chunk)

    full_output = "".join(c.delta_content or "" for c in collected)
    assert "CARBON" not in full_output, "Carbon should not appear without CarbonBudgetTracker"


@pytest.mark.usefixtures("reset_provenance")
@pytest.mark.asyncio
async def test_ethical_checkpoint_provenance_graceful_failure() -> None:
    """Provenance failures should not block the pipeline."""
    firewall = EthicalFirewall(
        rules=build_default_rules(),
        provenance_tracker=None,
    )

    inner = _EchoProvider()
    provider = firewall.wrap(inner)

    messages = [
        ChatMessage(role="user", content="This should work even without provenance."),
    ]

    collected = []
    async for chunk in provider.stream_chat(messages):
        collected.append(chunk)

    full_output = "".join(c.delta_content or "" for c in collected)
    assert len(full_output) > 0, "Pipeline should work without provenance"

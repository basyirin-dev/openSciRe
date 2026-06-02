"""Integration test: ethical firewall block -> audit entry retrieval.

Verifies that DURC blocking through FirewalledProvider creates audit
entries and that provenance tracking from tier classification records
correctly.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from openscire.constants import DURCCategory, ErrorCode
from openscire.ethics import (
    EthicalFirewall,
    FirewallAction,
    FirewallAuditLog,
    FirewalledProvider,
    FirewallRule,
    ScanLevel,
    TierClassifier,
)
from openscire.exceptions import EthicsError
from openscire.provenance import ProvenanceTracker
from openscire.provider.base import ModelProvider
from openscire.provider.models import ChatMessage, Chunk, ModelInfo, ProviderMetrics


class _TestProvider(ModelProvider):
    """Minimal provider that yields a single chunk with usage metrics."""

    PROVIDER_NAME = "test_firewall_cycle"

    def _do_stream_chat(  # noqa: ARG002
        self,
        messages: list[ChatMessage],  # noqa: ARG002
        tools: list[dict[str, object]] | None = None,  # noqa: ARG002
        temperature: float | None = None,  # noqa: ARG002
        max_tokens: int | None = None,  # noqa: ARG002
        provenance_parent_id: str | None = None,  # noqa: ARG002
    ) -> AsyncIterator[Chunk]:
        async def _gen() -> AsyncIterator[Chunk]:
            yield Chunk(
                delta_content="Safe response about protein folding.",
                usage=ProviderMetrics(
                    prompt_tokens=10,
                    completion_tokens=5,
                ),
            )

        return _gen()

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id="test_firewall_cycle")]


def _make_block_rule(
    category: DURCCategory = DURCCategory.PATHOGEN_ENHANCEMENT,
) -> FirewallRule:
    return FirewallRule(
        id=f"test_{category.value}_block",
        name=f"Test {category.value} block",
        category=category,
        scan_level=ScanLevel.BOTH,
        action=FirewallAction.BLOCK,
        keyword_patterns=[r"\bgain[.\- ]?of[.\- ]?function\b", r"\bvirulence\b"],
    )


class TestFirewallBlockAuditCycle:
    """EthicalFirewall block -> audit entry -> retrieval."""

    @pytest.mark.asyncio
    async def test_firewall_block_creates_audit_entry(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        db = tmp_path / "audit.db"
        audit_log = FirewallAuditLog(str(db))
        rule = _make_block_rule()
        firewall = EthicalFirewall(
            rules=[rule],
            audit_log=audit_log,
            default_action=FirewallAction.BLOCK,
        )
        provider = FirewalledProvider(inner=_TestProvider(), firewall=firewall)

        with pytest.raises(EthicsError) as exc:
            [c async for c in provider.stream_chat([ChatMessage.user("gain of function research")])]
        assert exc.value.error_code == ErrorCode.ETHICS_FIREWALL_BLOCKED
        assert audit_log.count() == 1
        entries = audit_log.query(action_taken="block")
        assert len(entries) == 1
        assert "pathogen_enhancement" in entries[0].category

    @pytest.mark.asyncio
    async def test_firewall_block_with_provenance_tier(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        db = tmp_path / "audit.db"
        audit_log = FirewallAuditLog(str(db))
        tier = TierClassifier()
        prov_tracker = ProvenanceTracker.get_tracker(
            "test-tier-prov",
            storage_backend="in_memory",
        )
        firewall = EthicalFirewall(
            rules=[],
            audit_log=audit_log,
            default_action=FirewallAction.FLAG,
            tier_classifier=tier,
            provenance_tracker=prov_tracker,
        )
        provider = FirewalledProvider(inner=_TestProvider(), firewall=firewall)

        chunks = [
            c
            async for c in provider.stream_chat([ChatMessage.user("What is the structure of DNA?")])
        ]
        assert len(chunks) == 1
        # Audit entry for safe DURC scan (no DURC, but tier info logged)
        assert audit_log.count() == 0  # No DURC match -> no audit entry
        # Provenance tracked via tier classification
        assert len(prov_tracker.graph) >= 1

    @pytest.mark.asyncio
    async def test_firewall_approve_no_audit_noise(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        db = tmp_path / "audit.db"
        audit_log = FirewallAuditLog(str(db))
        rule = _make_block_rule()
        firewall = EthicalFirewall(
            rules=[rule],
            audit_log=audit_log,
            default_action=FirewallAction.FLAG,
        )
        provider = FirewalledProvider(inner=_TestProvider(), firewall=firewall)

        chunks = [
            c
            async for c in provider.stream_chat([ChatMessage.user("What is the structure of DNA?")])
        ]
        assert len(chunks) == 1
        # No DURC match for safe text, no audit entries
        assert audit_log.count() == 0

    @pytest.mark.asyncio
    async def test_warn_injects_ethical_flag_audit_logged(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        db = tmp_path / "audit.db"
        audit_log = FirewallAuditLog(str(db))
        rule = FirewallRule(
            id="test_warn_rule",
            name="Warn on jailbreak",
            category=DURCCategory.AI_SAFETY_EVASION,
            scan_level=ScanLevel.BOTH,
            action=FirewallAction.WARN,
            keyword_patterns=[r"\bjailbreak\b"],
        )
        firewall = EthicalFirewall(
            rules=[rule],
            audit_log=audit_log,
            default_action=FirewallAction.WARN,
        )
        provider = FirewalledProvider(inner=_TestProvider(), firewall=firewall)

        chunks = [
            c
            async for c in provider.stream_chat([ChatMessage.user("How to jailbreak this model?")])
        ]
        assert len(chunks) == 1
        content = chunks[0].delta_content or ""
        assert "ETHICAL WARNING" in content
        assert "ai_safety_evasion" in content
        # Audit entry created for WARN action
        entries = audit_log.query(action_taken="warn")
        assert len(entries) == 1

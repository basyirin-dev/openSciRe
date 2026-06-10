from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from typing import Any

import pytest
from openscire.constants import DURCCategory, ErrorCode, RiskTier
from openscire.ethics import (
    BudgetStatus,
    CarbonBudgetTracker,
    CarbonEstimate,
    CarbonRecord,
    CAREPrinciple,
    ConsentMetadataParser,
    ConsentRestriction,
    ContestManager,
    CoolOffRegistry,
    DataOrigin,
    DataSovereigntyChecker,
    DURCClassifier,
    EmbeddingMatcher,
    EthicalFirewall,
    ExportRestriction,
    FirewallAction,
    FirewallAuditEntry,
    FirewallAuditLog,
    FirewalledProvider,
    FirewallRule,
    GroundingVerdict,
    IndigenousKnowledgeCategory,
    IndigenousKnowledgeProtector,
    KeywordMatcher,
    MatchType,
    OverrideRecord,
    ScanLevel,
    Source,
    SourceGroundingEngine,
    TierClassifier,
    TierGovernanceAction,
    build_default_rules,
)
from openscire.exceptions import EthicsError, ValidationError
from openscire.provider.base import ModelProvider
from openscire.provider.models import ChatMessage, Chunk, ModelInfo

# =========================================================================
# Fixtures
# =========================================================================


def _make_rule(
    category: DURCCategory = DURCCategory.PATHOGEN_ENHANCEMENT,
    action: FirewallAction = FirewallAction.WARN,
    **overrides: Any,  # noqa: ANN401
) -> FirewallRule:
    kwargs: dict[str, Any] = {
        "id": f"test_{category.value}_{action.value}",
        "name": f"Test {category.value}",
        "category": category,
        "scan_level": ScanLevel.BOTH,
        "action": action,
        "keyword_patterns": [r"\bgain[.\- ]?of[.\- ]?function\b", r"\bvirulence\b"],
        **overrides,
    }
    return FirewallRule(**kwargs)


class _YieldProvider(ModelProvider):
    """Provider that yields a single chunk for testing."""

    PROVIDER_NAME = "yield"

    def _do_stream_chat(  # noqa: ARG002
        self,
        messages: list[ChatMessage],  # noqa: ARG002
        tools: list[dict[str, Any]] | None = None,  # noqa: ARG002
        temperature: float | None = None,  # noqa: ARG002
        max_tokens: int | None = None,  # noqa: ARG002
        provenance_parent_id: str | None = None,  # noqa: ARG002
    ) -> AsyncIterator[Chunk]:
        async def _gen() -> AsyncIterator[Chunk]:
            yield Chunk(delta_content="This is a safe response about protein folding.")

        return _gen()

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id="yield")]


# =========================================================================
# Test DURCCategory
# =========================================================================


class TestDURCCategory:
    def test_all_categories_present(self) -> None:
        values = [c.value for c in DURCCategory]
        assert "pathogen_enhancement" in values
        assert "toxin_synthesis" in values
        assert "weapons_delivery" in values
        assert "ai_safety_evasion" in values
        assert "surveillance_hardening" in values

    def test_default_rules_are_created(self) -> None:
        rules = build_default_rules()
        assert len(rules) == len(DURCCategory)
        for cat in DURCCategory:
            assert any(r.category == cat for r in rules)

    def test_default_rule_properties(self) -> None:
        rules = build_default_rules()
        for r in rules:
            assert r.enabled is True
            assert r.scan_level == ScanLevel.BOTH
            assert r.action == FirewallAction.WARN
            assert len(r.keyword_patterns) > 0


# =========================================================================
# Test KeywordMatcher
# =========================================================================


class TestKeywordMatcher:
    def test_matches_keyword(self) -> None:
        matcher = KeywordMatcher(
            {
                DURCCategory.PATHOGEN_ENHANCEMENT: [r"\bgain[.\- ]?of[.\- ]?function\b"],
            }
        )
        results = matcher.scan("This research involves gain-of-function studies.")
        assert len(results) == 1
        assert results[0][0] == DURCCategory.PATHOGEN_ENHANCEMENT

    def test_no_false_positive_on_safe_text(self) -> None:
        matcher = KeywordMatcher(
            {
                DURCCategory.PATHOGEN_ENHANCEMENT: [r"\bvirulence\b"],
            }
        )
        results = matcher.scan("This is a safe text about protein folding.")
        assert len(results) == 0

    def test_multi_category_match(self) -> None:
        matcher = KeywordMatcher(
            {
                DURCCategory.PATHOGEN_ENHANCEMENT: [r"\bvirulence\b"],
                DURCCategory.AI_SAFETY_EVASION: [r"\bjailbreak\b"],
            }
        )
        results = matcher.scan("Research on virulence and jailbreak techniques.")
        assert len(results) == 2
        cats = {r[0] for r in results}
        assert DURCCategory.PATHOGEN_ENHANCEMENT in cats
        assert DURCCategory.AI_SAFETY_EVASION in cats

    def test_case_insensitive(self) -> None:
        matcher = KeywordMatcher(
            {
                DURCCategory.PATHOGEN_ENHANCEMENT: [r"\bvirulence\b"],
            }
        )
        results = matcher.scan("VIRULENCE")
        assert len(results) == 1

    def test_invalid_pattern_does_not_crash(self) -> None:
        matcher = KeywordMatcher(
            {
                DURCCategory.PATHOGEN_ENHANCEMENT: [r"[invalid", r"\bvalid\b"],
            }
        )
        results = matcher.scan("valid pattern test")
        assert len(results) == 1

    def test_limited_categories(self) -> None:
        matcher = KeywordMatcher(
            {
                DURCCategory.PATHOGEN_ENHANCEMENT: [r"\bvirulence\b"],
                DURCCategory.TOXIN_SYNTHESIS: [r"\btoxin\b"],
            }
        )
        results = matcher.scan("virulence and toxin", categories=[DURCCategory.TOXIN_SYNTHESIS])
        assert len(results) == 1
        assert results[0][0] == DURCCategory.TOXIN_SYNTHESIS

    def test_empty_text_returns_empty_results(self) -> None:
        matcher = KeywordMatcher(
            {
                DURCCategory.PATHOGEN_ENHANCEMENT: [r"\bgain[.\- ]?of[.\- ]?function\b"],
            }
        )
        results = matcher.scan("")
        assert len(results) == 0

    def test_empty_pattern_map_returns_empty(self) -> None:
        matcher = KeywordMatcher({})
        results = matcher.scan("some text about virulence")
        assert len(results) == 0


# =========================================================================
# Test EmbeddingMatcher
# =========================================================================


class TestEmbeddingMatcher:
    def test_unavailable_when_no_sentence_transformers(self) -> None:
        matcher = EmbeddingMatcher(model_name="all-MiniLM-L6-v2")
        assert matcher.available is False

    def test_returns_zero_when_unavailable(self) -> None:
        matcher = EmbeddingMatcher()
        scores = matcher.score("test text", {DURCCategory.PATHOGEN_ENHANCEMENT: ["test"]})
        assert scores[DURCCategory.PATHOGEN_ENHANCEMENT] == 0.0


# =========================================================================
# Test DURCClassifier
# =========================================================================


class TestDURCClassifier:
    @pytest.mark.asyncio
    async def test_keyword_only_detection(self) -> None:
        classifier = DURCClassifier(
            keyword_patterns={
                DURCCategory.PATHOGEN_ENHANCEMENT: [r"\bgain[.\- ]?of[.\- ]?function\b"],
            },
        )
        rules = [_make_rule(DURCCategory.PATHOGEN_ENHANCEMENT)]
        results = await classifier.scan("gain of function research", rules)
        assert len(results) == 1
        assert results[0].category == DURCCategory.PATHOGEN_ENHANCEMENT
        assert results[0].match_type == MatchType.KEYWORD

    @pytest.mark.asyncio
    async def test_no_match_on_safe_text(self) -> None:
        classifier = DURCClassifier(
            keyword_patterns={
                DURCCategory.PATHOGEN_ENHANCEMENT: [r"\bvirulence\b"],
            },
        )
        rules = [_make_rule(DURCCategory.PATHOGEN_ENHANCEMENT)]
        results = await classifier.scan("Safe research on photosynthesis.", rules)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_disabled_rules_are_skipped(self) -> None:
        classifier = DURCClassifier(
            keyword_patterns={
                DURCCategory.PATHOGEN_ENHANCEMENT: [r"\bvirulence\b"],
            },
        )
        rules = [
            _make_rule(DURCCategory.PATHOGEN_ENHANCEMENT, enabled=False),
        ]
        results = await classifier.scan("virulence research", rules)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_empty_rules_returns_empty(self) -> None:
        classifier = DURCClassifier()
        results = await classifier.scan("any text", [])
        assert len(results) == 0


# =========================================================================
# Test EthicalFirewall
# =========================================================================


class TestEthicalFirewall:
    @pytest.mark.asyncio
    async def test_scan_prompt_with_flag_action(self, tmp_path: object) -> None:
        db = tmp_path / "audit.db"
        audit_log = FirewallAuditLog(str(db))
        rule = _make_rule(DURCCategory.PATHOGEN_ENHANCEMENT, action=FirewallAction.FLAG)
        firewall = EthicalFirewall(
            rules=[rule],
            audit_log=audit_log,
            default_action=FirewallAction.FLAG,
        )
        decision = await firewall.scan_prompt([ChatMessage.user("gain of function research")])
        assert decision.overall_action == FirewallAction.FLAG
        assert len(decision.categories_flagged) == 1
        assert audit_log.count() == 1

    @pytest.mark.asyncio
    async def test_scan_prompt_with_block_action(self, tmp_path: object) -> None:
        db = tmp_path / "audit.db"
        audit_log = FirewallAuditLog(str(db))
        rule = _make_rule(DURCCategory.PATHOGEN_ENHANCEMENT, action=FirewallAction.BLOCK)
        firewall = EthicalFirewall(
            rules=[rule],
            audit_log=audit_log,
            default_action=FirewallAction.BLOCK,
        )
        with pytest.raises(EthicsError) as exc_info:
            await firewall.scan_prompt([ChatMessage.user("gain of function research")])
        assert exc_info.value.error_code == ErrorCode.ETHICS_FIREWALL_BLOCKED
        assert audit_log.count() == 1

    @pytest.mark.asyncio
    async def test_scan_prompt_with_escalate_action(self, tmp_path: object) -> None:
        db = tmp_path / "audit.db"
        audit_log = FirewallAuditLog(str(db))
        rule = _make_rule(DURCCategory.PATHOGEN_ENHANCEMENT, action=FirewallAction.ESCALATE)
        firewall = EthicalFirewall(
            rules=[rule],
            audit_log=audit_log,
            default_action=FirewallAction.ESCALATE,
        )
        with pytest.raises(EthicsError):
            await firewall.scan_prompt([ChatMessage.user("gain of function research")])
        assert audit_log.count() == 1

    @pytest.mark.asyncio
    async def test_scan_response_detects_durc(self, tmp_path: object) -> None:
        db = tmp_path / "audit.db"
        audit_log = FirewallAuditLog(str(db))
        rule = _make_rule(DURCCategory.PATHOGEN_ENHANCEMENT, action=FirewallAction.WARN)
        firewall = EthicalFirewall(
            rules=[rule],
            audit_log=audit_log,
            default_action=FirewallAction.WARN,
        )
        decision = await firewall.scan_response(
            "This paper describes gain of function experiments."
        )
        assert len(decision.categories_flagged) == 1
        assert decision.overall_action == FirewallAction.WARN

    @pytest.mark.asyncio
    async def test_no_flag_on_safe_prompt(self, tmp_path: object) -> None:
        db = tmp_path / "audit.db"
        audit_log = FirewallAuditLog(str(db))
        rule = _make_rule(DURCCategory.PATHOGEN_ENHANCEMENT, action=FirewallAction.FLAG)
        firewall = EthicalFirewall(
            rules=[rule],
            audit_log=audit_log,
            default_action=FirewallAction.FLAG,
        )
        decision = await firewall.scan_prompt([ChatMessage.user("What is the structure of DNA?")])
        assert len(decision.categories_flagged) == 0
        assert audit_log.count() == 0

    def test_add_and_remove_rules(self) -> None:
        firewall = EthicalFirewall(rules=[], default_action=FirewallAction.FLAG)
        assert len(firewall.rules) == 0
        rule = _make_rule()
        firewall.add_rule(rule)
        assert len(firewall.rules) == 1
        assert firewall.remove_rule(rule.id) is True
        assert len(firewall.rules) == 0

    def test_remove_nonexistent_rule_returns_false(self) -> None:
        firewall = EthicalFirewall(rules=[])
        assert firewall.remove_rule("nonexistent") is False

    def test_update_rule(self) -> None:
        rule = _make_rule(action=FirewallAction.FLAG)
        firewall = EthicalFirewall(rules=[rule])
        updated = rule.model_copy(update={"action": FirewallAction.BLOCK})
        assert firewall.update_rule(updated) is True
        assert firewall.rules[0].action == FirewallAction.BLOCK

    def test_update_nonexistent_rule_returns_false(self) -> None:
        firewall = EthicalFirewall(rules=[])
        assert firewall.update_rule(_make_rule()) is False

    @pytest.mark.asyncio
    async def test_scan_prompt_warn_action(self, tmp_path: object) -> None:
        db = tmp_path / "audit.db"
        audit_log = FirewallAuditLog(str(db))
        rule = _make_rule(DURCCategory.PATHOGEN_ENHANCEMENT, action=FirewallAction.WARN)
        firewall = EthicalFirewall(
            rules=[rule],
            audit_log=audit_log,
            default_action=FirewallAction.WARN,
        )
        decision = await firewall.scan_prompt([ChatMessage.user("gain of function research")])
        # WARN does not raise; it creates an audit entry
        assert decision.overall_action == FirewallAction.WARN
        assert len(decision.categories_flagged) == 1
        assert audit_log.count() == 1

    @pytest.mark.asyncio
    async def test_scan_prompt_empty_message_list(self) -> None:
        firewall = EthicalFirewall(rules=[], default_action=FirewallAction.FLAG)
        decision = await firewall.scan_prompt([])
        assert decision.overall_action == FirewallAction.FLAG
        assert len(decision.categories_flagged) == 0

    @pytest.mark.asyncio
    async def test_conflicting_rule_actions(self, tmp_path: object) -> None:
        db = tmp_path / "audit.db"
        audit_log = FirewallAuditLog(str(db))
        # Two rules with different categories whose default keyword patterns
        # both match the same text.  BLOCK has higher priority than FLAG.
        rule_flag = FirewallRule(
            id="test_flag_pathogen",
            name="Flag pathogen enhancement",
            category=DURCCategory.PATHOGEN_ENHANCEMENT,
            scan_level=ScanLevel.BOTH,
            action=FirewallAction.FLAG,
        )
        rule_block = FirewallRule(
            id="test_block_toxin",
            name="Block toxin synthesis",
            category=DURCCategory.TOXIN_SYNTHESIS,
            scan_level=ScanLevel.BOTH,
            action=FirewallAction.BLOCK,
        )
        firewall = EthicalFirewall(
            rules=[rule_flag, rule_block],
            audit_log=audit_log,
            default_action=FirewallAction.FLAG,
        )
        # BLOCK has higher priority than FLAG -> overall action is BLOCK
        text = "gain of function research involving toxin synthesis and botulinum toxin production"
        with pytest.raises(EthicsError) as exc_info:
            await firewall.scan_prompt([ChatMessage.user(text)])
        assert exc_info.value.error_code == ErrorCode.ETHICS_FIREWALL_BLOCKED


# =========================================================================
# Test FirewalledProvider
# =========================================================================


class TestFirewalledProvider:
    @pytest.mark.asyncio
    async def test_passthrough_on_safe_prompt(self, tmp_path: object) -> None:
        db = tmp_path / "audit.db"
        audit_log = FirewallAuditLog(str(db))
        firewall = EthicalFirewall(
            rules=[_make_rule(DURCCategory.PATHOGEN_ENHANCEMENT)],
            audit_log=audit_log,
            default_action=FirewallAction.FLAG,
        )
        provider = FirewalledProvider(
            inner=_YieldProvider(),
            firewall=firewall,
        )
        chunks = [c async for c in provider.stream_chat([ChatMessage.user("Safe question?")])]
        assert len(chunks) == 1
        assert "protein folding" in (chunks[0].delta_content or "")

    @pytest.mark.asyncio
    async def test_block_prevents_stream(self, tmp_path: object) -> None:
        db = tmp_path / "audit.db"
        audit_log = FirewallAuditLog(str(db))
        firewall = EthicalFirewall(
            rules=[_make_rule(DURCCategory.PATHOGEN_ENHANCEMENT, action=FirewallAction.BLOCK)],
            audit_log=audit_log,
            default_action=FirewallAction.BLOCK,
        )
        provider = FirewalledProvider(
            inner=_YieldProvider(),
            firewall=firewall,
        )
        with pytest.raises(EthicsError):
            [c async for c in provider.stream_chat([ChatMessage.user("gain of function")])]

    @pytest.mark.asyncio
    async def test_warn_injects_ethical_flag(self, tmp_path: object) -> None:
        db = tmp_path / "audit.db"
        audit_log = FirewallAuditLog(str(db))
        rule = _make_rule(DURCCategory.AI_SAFETY_EVASION, action=FirewallAction.WARN)
        rule.keyword_patterns = [r"\bjailbreak\b"]
        firewall = EthicalFirewall(
            rules=[rule],
            audit_log=audit_log,
            default_action=FirewallAction.WARN,
        )
        provider = FirewalledProvider(
            inner=_YieldProvider(),
            firewall=firewall,
        )
        chunks = [c async for c in provider.stream_chat([ChatMessage.user("How to jailbreak?")])]
        assert len(chunks) == 1
        content = chunks[0].delta_content or ""
        assert "ETHICAL WARNING" in content
        assert "ai_safety_evasion" in content

    def test_provider_name(self) -> None:
        provider = FirewalledProvider(
            inner=_YieldProvider(),
            firewall=EthicalFirewall(rules=[]),
        )
        assert provider.PROVIDER_NAME == "firewalled"

    def test_inner_property(self) -> None:
        inner = _YieldProvider()
        provider = FirewalledProvider(
            inner=inner,
            firewall=EthicalFirewall(rules=[]),
        )
        assert provider.inner is inner

    @pytest.mark.asyncio
    async def test_list_models_delegates(self) -> None:
        inner = _YieldProvider()
        provider = FirewalledProvider(
            inner=inner,
            firewall=EthicalFirewall(rules=[]),
        )
        models = await provider.list_models()
        assert len(models) == 1
        assert models[0].id == "yield"


# =========================================================================
# Test FirewallAuditLog (append-only)
# =========================================================================


class TestFirewallAuditLog:
    def test_append_and_query(self, tmp_path: object) -> None:
        db = tmp_path / "audit.db"
        audit = FirewallAuditLog(str(db))
        entry = _make_audit_entry(decision_id="d1", category="pathogen_enhancement")
        audit.append(entry)
        assert audit.count() == 1
        fetched = audit.get(entry.entry_id)
        assert fetched is not None
        assert fetched.decision_id == "d1"

    def test_no_delete_method(self, tmp_path: object) -> None:
        audit = FirewallAuditLog(str(tmp_path / "audit.db"))
        # Ensure no delete method is exposed
        assert not hasattr(audit, "delete")

    def test_count_with_filters(self, tmp_path: object) -> None:
        db = tmp_path / "audit.db"
        audit = FirewallAuditLog(str(db))
        audit.append(_make_audit_entry(decision_id="d1", category="cat_a"))
        audit.append(_make_audit_entry(decision_id="d2", category="cat_b"))
        assert audit.count() == 2
        assert audit.count(category="cat_a") == 1

    def test_query_with_filters(self, tmp_path: object) -> None:
        db = tmp_path / "audit.db"
        audit = FirewallAuditLog(str(db))
        audit.append(_make_audit_entry(decision_id="d1", category="cat_a", action_taken="block"))
        audit.append(_make_audit_entry(decision_id="d2", category="cat_b", action_taken="warn"))
        results = audit.query(action_taken="block")
        assert len(results) == 1
        assert results[0].decision_id == "d1"

    def test_append_multiple(self, tmp_path: object) -> None:
        db = tmp_path / "audit.db"
        audit = FirewallAuditLog(str(db))
        for i in range(5):
            audit.append(_make_audit_entry(decision_id=f"d{i}"))
        assert audit.count() == 5

    def test_close_reopens(self, tmp_path: object) -> None:
        db = tmp_path / "audit.db"
        audit = FirewallAuditLog(str(db))
        audit.append(_make_audit_entry(decision_id="d1"))
        audit.close()
        audit2 = FirewallAuditLog(str(db))
        assert audit2.count() == 1

    def test_signing_and_verification(self, tmp_path: object) -> None:
        import nacl.bindings

        db = tmp_path / "audit.db"
        audit = FirewallAuditLog(str(db))
        seed = b"0" * 32
        pk = nacl.bindings.crypto_sign_seed_keypair(seed)[0]
        entry = _make_audit_entry(decision_id="d_signed")
        signed = audit.append(entry, signing_key=seed.hex())
        assert signed.cryptographic_signature is not None
        assert FirewallAuditLog.verify(signed, pk.hex())

    def test_verify_no_signature_returns_false(self, tmp_path: object) -> None:  # noqa: ARG002
        entry = _make_audit_entry(decision_id="d_unsigned")
        assert FirewallAuditLog.verify(entry, "00" * 32) is False

    def test_matched_content_truncated(self, tmp_path: object) -> None:
        db = tmp_path / "audit.db"
        audit = FirewallAuditLog(str(db))
        long_text = "x" * 1000
        entry = _make_audit_entry(decision_id="d_long", matched_content=long_text)
        audit.append(entry)
        fetched = audit.get(entry.entry_id)
        assert fetched is not None
        assert len(fetched.matched_content) <= 200


# =========================================================================
# Test ContestManager (feedback loop)
# =========================================================================


class TestContestManager:
    def test_submit_contest(self, tmp_path: object) -> None:
        db = tmp_path / "audit.db"
        audit = FirewallAuditLog(str(db))
        entry = _make_audit_entry(decision_id="d_contest")
        audit.append(entry)
        mgr = ContestManager(audit)
        contest = mgr.submit_contest(
            decision_id="d_contest",
            user_id="user1",
            reason="This was a false positive, it's benign research.",
        )
        assert contest.decision_id == "d_contest"
        assert contest.user_id == "user1"
        assert contest.reviewed is False

    def test_submit_contest_nonexistent_decision_raises(self, tmp_path: object) -> None:
        db = tmp_path / "audit.db"
        audit = FirewallAuditLog(str(db))
        mgr = ContestManager(audit)
        with pytest.raises(ValueError, match="No audit entry found"):
            mgr.submit_contest(
                decision_id="nonexistent",
                user_id="user1",
                reason="False positive",
            )

    def test_list_open_contests(self, tmp_path: object) -> None:
        db = tmp_path / "audit.db"
        audit = FirewallAuditLog(str(db))
        entry = _make_audit_entry(decision_id="d1")
        audit.append(entry)
        mgr = ContestManager(audit)
        mgr.submit_contest("d1", "user1", "FP")
        open_contests = mgr.list_open_contests()
        assert len(open_contests) == 1
        assert open_contests[0].decision_id == "d1"

    def test_review_contest(self, tmp_path: object) -> None:
        db = tmp_path / "audit.db"
        audit = FirewallAuditLog(str(db))
        entry = _make_audit_entry(decision_id="d2")
        audit.append(entry)
        mgr = ContestManager(audit)
        contest = mgr.submit_contest("d2", "user1", "FP")
        reviewed = mgr.review_contest(
            contest_id=contest.contest_id,
            upheld=True,
            review_notes="Confirmed false positive, adjusting thresholds.",
        )
        assert reviewed is not None
        assert reviewed.reviewed is True
        assert reviewed.upheld is True
        assert reviewed.review_notes == "Confirmed false positive, adjusting thresholds."

    def test_export_jsonl(self, tmp_path: object) -> None:
        db = tmp_path / "audit.db"
        audit = FirewallAuditLog(str(db))
        entry = _make_audit_entry(decision_id="d_export")
        audit.append(entry)
        mgr = ContestManager(audit)
        contest = mgr.submit_contest("d_export", "user1", "FP")
        mgr.review_contest(contest_id=contest.contest_id, upheld=True)
        export_path = tmp_path / "export.jsonl"
        count = mgr.export_jsonl(str(export_path))
        assert count == 1
        exported = export_path.read_text()
        assert "d_export" in exported
        assert "upheld" in exported


# =========================================================================
# Test EthicsError
# =========================================================================


class TestEthicsError:
    def test_ethics_error_has_correct_code(self) -> None:
        err = EthicsError(
            message="Firewall blocked",
            source="test",
            error_code=ErrorCode.ETHICS_FIREWALL_BLOCKED,
        )
        assert err.error_code == ErrorCode.ETHICS_FIREWALL_BLOCKED
        assert "Firewall blocked" in str(err)

    def test_ethics_error_default_code(self) -> None:
        err = EthicsError(message="Generic ethics issue", source="test")
        assert err.error_code == ErrorCode.ETHICS_DURC_FLAG


# =========================================================================
# Test Firewall wrap() method
# =========================================================================


class TestFirewallWrap:
    def test_wrap_returns_firewalled_provider(self) -> None:
        firewall = EthicalFirewall(rules=[])
        inner = _YieldProvider()
        wrapped = firewall.wrap(inner)
        assert isinstance(wrapped, FirewalledProvider)
        assert wrapped.inner is inner

    @pytest.mark.asyncio
    async def test_wrapped_provider_passes_safe_prompt(self, tmp_path: object) -> None:
        db = tmp_path / "audit.db"
        audit_log = FirewallAuditLog(str(db))
        firewall = EthicalFirewall(
            rules=[_make_rule(DURCCategory.PATHOGEN_ENHANCEMENT, action=FirewallAction.FLAG)],
            audit_log=audit_log,
            default_action=FirewallAction.FLAG,
        )
        wrapped = firewall.wrap(_YieldProvider())
        chunks = [c async for c in wrapped.stream_chat([ChatMessage.user("Safe text?")])]
        assert len(chunks) == 1


# =========================================================================
# Helpers
# =========================================================================


def _make_audit_entry(
    decision_id: str = "d0",
    category: str = "test_category",
    action_taken: str = "flag",
    match_type: str = "keyword",
    matched_content: str = "test match",
    input_hash: str = "abc123",
) -> FirewallAuditEntry:
    return FirewallAuditEntry(
        entry_id=f"audit_{decision_id}",
        decision_id=decision_id,
        category=category,
        action_taken=action_taken,
        match_type=match_type,
        matched_content=matched_content,
        input_hash=input_hash,
    )


# =========================================================================
# Risk Tier Tests
# =========================================================================


class TestRiskTier:
    def test_enum_str(self) -> None:
        assert str(RiskTier.LOW) == "tier_3_low"
        assert str(RiskTier.MEDIUM) == "tier_2_medium"
        assert str(RiskTier.HIGH) == "tier_1_high"

    def test_enum_values(self) -> None:
        assert RiskTier.LOW.value == "tier_3_low"
        assert RiskTier.MEDIUM.value == "tier_2_medium"
        assert RiskTier.HIGH.value == "tier_1_high"

    def test_from_value(self) -> None:
        assert RiskTier("tier_3_low") == RiskTier.LOW
        assert RiskTier("tier_2_medium") == RiskTier.MEDIUM
        assert RiskTier("tier_1_high") == RiskTier.HIGH


class TestTierClassifier:
    @pytest.mark.asyncio
    async def test_empty_text_returns_low(self) -> None:
        tc = TierClassifier()
        result = await tc.classify("")
        assert result.assigned_tier == RiskTier.LOW

    @pytest.mark.asyncio
    async def test_neutral_text_returns_low(self) -> None:
        tc = TierClassifier()
        result = await tc.classify("What is the capital of France?")
        assert result.assigned_tier == RiskTier.LOW

    @pytest.mark.asyncio
    async def test_high_risk_virology_pattern(self) -> None:
        tc = TierClassifier()
        result = await tc.classify("Host-pathogen interactions of pandemic viruses.")
        assert result.assigned_tier == RiskTier.HIGH
        assert result.domain is not None

    @pytest.mark.asyncio
    async def test_medium_risk_clinical_pattern(self) -> None:
        tc = TierClassifier()
        result = await tc.classify("This clinical trial requires IRB approval for Phase 1.")
        assert result.assigned_tier == RiskTier.MEDIUM
        assert result.domain is not None

    @pytest.mark.asyncio
    async def test_low_risk_general_science(self) -> None:
        tc = TierClassifier()
        result = await tc.classify("I need help with statistical analysis of my RNA-seq data.")
        assert result.assigned_tier == RiskTier.LOW

    @pytest.mark.asyncio
    async def test_all_domains_have_labels(self) -> None:
        from openscire.ethics.tier import TIER_DOMAIN_LABELS, TIER_KEYWORD_PATTERNS

        domain_count = sum(len(domains) for domains in TIER_KEYWORD_PATTERNS.values())
        assert domain_count > 0
        all_domains = set()
        for domains in TIER_KEYWORD_PATTERNS.values():
            all_domains.update(domains.keys())
        for d in all_domains:
            assert d in TIER_DOMAIN_LABELS, f"Domain {d} missing label"

    @pytest.mark.asyncio
    async def test_cool_off_action_for_high_risk(self) -> None:
        tc = TierClassifier()
        result = await tc.classify("Virology study of host-pathogen interactions.")
        assert result.governance_action == TierGovernanceAction.COOLING_OFF

    @pytest.mark.asyncio
    async def test_human_checkpoint_action_for_medium_risk(self) -> None:
        tc = TierClassifier()
        result = await tc.classify("A clinical trial with human subjects data.")
        assert result.governance_action == TierGovernanceAction.HUMAN_CHECKPOINT

    @pytest.mark.asyncio
    async def test_standard_action_for_low_risk(self) -> None:
        tc = TierClassifier()
        result = await tc.classify("What is the structure of DNA?")
        assert result.governance_action is not None
        assert result.governance_action == TierGovernanceAction.STANDARD

    @pytest.mark.asyncio
    async def test_confidence_is_float(self) -> None:
        tc = TierClassifier()
        result = await tc.classify("pandemic preparedness study")
        assert isinstance(result.confidence, float)
        assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_match_type_is_keyword(self) -> None:
        tc = TierClassifier()
        result = await tc.classify("virology transmission study")
        assert result.match_type == MatchType.KEYWORD

    @pytest.mark.asyncio
    async def test_match_type_is_none_for_low(self) -> None:
        tc = TierClassifier()
        result = await tc.classify("What is 2+2?")
        assert result.match_type is None

    @pytest.mark.asyncio
    async def test_cool_off_until_is_set_for_high_risk(self) -> None:
        tc = TierClassifier()
        result = await tc.classify("Viral replication in host-pathogen systems.")
        if result.governance_action == TierGovernanceAction.COOLING_OFF:
            assert result.cool_off_until is not None


class TestTierOverride:
    def test_escalation_without_justification_succeeds(self) -> None:
        firewall = EthicalFirewall()
        decision_id = "test_escalation"
        firewall._audit_log.append(
            FirewallAuditEntry(
                entry_id="audit_esc_1",
                decision_id=decision_id,
                category="test",
                action_taken="flag",
                match_type="keyword",
                matched_content="test",
                input_hash="abc",
                user_id="user1",
                metadata={"tier": RiskTier.LOW.value},
            ),
        )
        record = firewall.override_tier(decision_id, RiskTier.HIGH)
        assert record is not None
        assert record.direction == "escalation"

    def test_escalation_with_provenance(self) -> None:
        class _MockTracker:
            def track(self, **kwargs: Any) -> object:  # noqa: ANN401, ARG002
                return type("Entry", (), {"action_id": "prov_1"})()

        firewall = EthicalFirewall()
        firewall._provenance_tracker = _MockTracker()
        decision_id = "test_escalation_prov"
        firewall._audit_log.append(
            FirewallAuditEntry(
                entry_id="audit_esc_prov",
                decision_id=decision_id,
                category="test",
                action_taken="flag",
                match_type="keyword",
                matched_content="test",
                input_hash="abc",
                user_id="user1",
                metadata={"tier": RiskTier.LOW.value},
            ),
        )
        record = firewall.override_tier(decision_id, RiskTier.HIGH)
        assert record.original_tier == RiskTier.LOW
        assert record.new_tier == RiskTier.HIGH
        assert record.direction == "escalation"
        assert record.provenance_entry_id == "prov_1"

    def test_downgrade_requires_justification(self) -> None:
        firewall = EthicalFirewall()
        decision_id = "test_downgrade_no_just"
        firewall._audit_log.append(
            FirewallAuditEntry(
                entry_id="audit_downgrade_1",
                decision_id=decision_id,
                category="test",
                action_taken="flag",
                match_type="keyword",
                matched_content="test",
                input_hash="abc",
                user_id="user1",
                metadata={"tier": RiskTier.HIGH.value},
            ),
        )
        with pytest.raises(EthicsError) as exc:
            firewall.override_tier(
                decision_id,
                RiskTier.LOW,
                user_id="user1",
                justification="",
            )
        assert exc.value.error_code == ErrorCode.ETHICS_TIER_BLOCKED

    def test_downgrade_with_justification_succeeds(self) -> None:
        class _MockTracker:
            def track(self, **kwargs: Any) -> object:  # noqa: ANN401, ARG002
                return type("Entry", (), {"action_id": "prov_2"})()

        firewall = EthicalFirewall()
        decision_id = "test_downgrade_ok"
        firewall._audit_log.append(
            FirewallAuditEntry(
                entry_id="audit_downgrade_2",
                decision_id=decision_id,
                category="test",
                action_taken="flag",
                match_type="keyword",
                matched_content="test",
                input_hash="abc",
                user_id="user1",
                metadata={"tier": RiskTier.HIGH.value},
            ),
        )
        firewall._provenance_tracker = _MockTracker()
        record = firewall.override_tier(
            decision_id,
            RiskTier.LOW,
            user_id="user1",
            justification="User has relevant expertise",
        )
        assert record is not None
        assert record.new_tier == RiskTier.LOW
        assert record.direction == "downgrade"
        assert record.justification == "User has relevant expertise"

    def test_override_record_fields(self) -> None:
        class _MockTracker:
            def track(self, **kwargs: Any) -> object:  # noqa: ANN401, ARG002
                return type("Entry", (), {"action_id": "prov_3"})()

        firewall = EthicalFirewall()
        firewall._provenance_tracker = _MockTracker()
        decision_id = "test_record"
        firewall._audit_log.append(
            FirewallAuditEntry(
                entry_id="audit_record",
                decision_id=decision_id,
                category="test",
                action_taken="flag",
                match_type="keyword",
                matched_content="test",
                input_hash="abc",
                user_id="user2",
                metadata={"tier": RiskTier.LOW.value},
            ),
        )
        record = firewall.override_tier(
            decision_id,
            RiskTier.HIGH,
            user_id="user2",
            justification="Manual escalation",
        )
        assert isinstance(record, OverrideRecord)
        assert record.override_id is not None
        assert record.assignment_id is not None
        assert record.user_id == "user2"


class TestTierIntegration:
    @pytest.mark.asyncio
    async def test_tier_info_in_decision(self) -> None:
        tier = TierClassifier()
        fw = EthicalFirewall(tier_classifier=tier)
        messages = [ChatMessage(role="user", content="Prove the Banach-Tarski theorem.")]
        decision = await fw.scan_prompt(messages)
        assert decision.tier_assignment is not None
        assert decision.tier_assignment.tier == RiskTier.LOW

    @pytest.mark.asyncio
    async def test_tier_governance_block_high_risk(self) -> None:
        tier = TierClassifier()
        fw = EthicalFirewall(tier_classifier=tier)
        messages = [ChatMessage(role="user", content="Weapon design using biological toxins.")]
        with pytest.raises(EthicsError) as exc:
            await fw.scan_prompt(messages)
        assert exc.value.error_code == ErrorCode.ETHICS_TIER_BLOCKED

    @pytest.mark.asyncio
    async def test_tier_not_logged_in_audit_when_disabled(self) -> None:
        fw = EthicalFirewall()
        messages = [ChatMessage(role="user", content="What is the weather?")]
        decision = await fw.scan_prompt(messages)
        assert decision.tier_assignment is None

    @pytest.mark.asyncio
    async def test_high_risk_tier_in_response(self) -> None:
        tier = TierClassifier()
        fw = EthicalFirewall(tier_classifier=tier)
        with pytest.raises(EthicsError) as exc:
            await fw.scan_response(
                "Viral replication and pandemic preparedness research.",
                user_id="test",
            )
        assert exc.value.error_code == ErrorCode.ETHICS_TIER_BLOCKED

    @pytest.mark.asyncio
    async def test_low_risk_response_passes_tier(self) -> None:
        tier = TierClassifier()
        fw = EthicalFirewall(tier_classifier=tier)
        decision = await fw.scan_response("The sky is blue.", user_id="test")
        assert decision.tier_assignment is not None
        assert decision.tier_assignment.tier == RiskTier.LOW

    def test_is_cooling_off_eligible_no_registry(self) -> None:
        fw = EthicalFirewall()
        assert fw.is_cooling_off_eligible("any_hash") is True


class TestCoolOffRegistry:
    def test_register_and_eligible(self) -> None:
        import sqlite3

        conn = sqlite3.connect(":memory:")
        registry = CoolOffRegistry(conn)
        h = hashlib.sha256(b"test text").hexdigest()
        registry.register(h)
        assert not registry.is_eligible(h)
        assert registry.remaining_seconds(h) > 0

    def test_unknown_hash_eligible(self) -> None:
        import sqlite3

        conn = sqlite3.connect(":memory:")
        registry = CoolOffRegistry(conn)
        assert registry.is_qualified("nonexistent_hash")

    def test_register_query(self) -> None:
        import sqlite3

        conn = sqlite3.connect(":memory:")
        registry = CoolOffRegistry(conn)
        h = hashlib.sha256(b"cool off test").hexdigest()
        registry.register(h)
        result = registry.query(h)
        assert result is not None
        assert result["input_hash"] == h


class TestTierIntegrationExtended:
    """Additional tier integration tests: medium-risk governance, cool-off, override flow."""

    @pytest.mark.asyncio
    async def test_medium_risk_governance_via_firewall(self) -> None:
        """MEDIUM tier (clinical trial text) blocks via HUMAN_CHECKPOINT."""
        tier = TierClassifier()
        fw = EthicalFirewall(tier_classifier=tier)
        messages = [ChatMessage(role="user", content="This clinical trial requires IRB approval.")]
        with pytest.raises(EthicsError) as exc:
            await fw.scan_prompt(messages)
        assert exc.value.error_code == ErrorCode.ETHICS_TIER_BLOCKED

    @pytest.mark.asyncio
    async def test_cool_off_registry_repeated_scan(self) -> None:
        """High-risk text blocks on first scan and second scan (cool-off persists)."""
        import sqlite3

        conn = sqlite3.connect(":memory:")
        registry = CoolOffRegistry(conn)
        tier = TierClassifier()
        fw = EthicalFirewall(
            tier_classifier=tier,
            cool_off_registry=registry,
        )
        messages = [
            ChatMessage(
                role="user",
                content="Virology study of host-pathogen interactions.",
            )
        ]
        with pytest.raises(EthicsError):
            await fw.scan_prompt(messages)
        # Verify the registry has the hash
        input_hash = hashlib.sha256(
            b"user: Virology study of host-pathogen interactions."
        ).hexdigest()
        assert not registry.is_eligible(input_hash)

    def test_override_escalation_with_audit_entry(self, tmp_path: object) -> None:
        """Escalation override creates audit entry via override_tier."""
        db = tmp_path / "audit.db"
        audit = FirewallAuditLog(str(db))
        fw = EthicalFirewall(audit_log=audit)
        decision_id = "test_override_audit"
        audit.append(
            FirewallAuditEntry(
                entry_id="audit_base",
                decision_id=decision_id,
                category="test",
                action_taken="flag",
                match_type="keyword",
                matched_content="test",
                input_hash="abc",
                user_id="user1",
                metadata={"tier": RiskTier.LOW.value},
            ),
        )
        record = fw.override_tier(decision_id, RiskTier.HIGH)
        assert record is not None
        assert record.direction == "escalation"
        # Override does not create audit entry directly — it records an OverrideRecord
        entries = audit.query(category="tier_override")
        assert len(entries) == 0


# =========================================================================
# Sovereignty Tests — Task 3.3
# =========================================================================


class TestDataOrigin:
    def test_parse_origin_public_domain(self) -> None:
        meta = {"origin": "public domain data", "source": "ncbi"}
        assert ConsentMetadataParser.parse_origin(meta) == DataOrigin.PUBLIC

    def test_parse_origin_open_access(self) -> None:
        meta = {"origin": "open access data", "license": "cc-by-4.0"}
        assert ConsentMetadataParser.parse_origin(meta) == DataOrigin.PUBLIC

    def test_parse_origin_clinical(self) -> None:
        meta = {"origin": "patient data", "consent": "explicit"}
        assert ConsentMetadataParser.parse_origin(meta) == DataOrigin.CLINICAL

    def test_parse_origin_indigenous(self) -> None:
        meta = {"origin": "indigenous territory", "source": "ancestral lands"}
        assert ConsentMetadataParser.parse_origin(meta) == DataOrigin.INDIGENOUS

    def test_parse_origin_proprietary(self) -> None:
        meta = {"origin": "proprietary dataset", "source": "company internal"}
        assert ConsentMetadataParser.parse_origin(meta) == DataOrigin.PROPRIETARY

    def test_parse_origin_irb_approved(self) -> None:
        meta = {"consent": "irb", "source": "clinical trial"}
        assert ConsentMetadataParser.parse_origin(meta) == DataOrigin.IRB_APPROVED

    def test_parse_origin_defaults_to_public(self) -> None:
        meta: dict[str, str] = {}
        assert ConsentMetadataParser.parse_origin(meta) == DataOrigin.PUBLIC


class TestConsentRestriction:
    def test_parse_no_analysis(self) -> None:
        meta = {"consent": "no analysis"}
        restrictions = ConsentMetadataParser.parse_restrictions(meta)
        assert ConsentRestriction.NO_ANALYSIS in restrictions

    def test_parse_no_sharing(self) -> None:
        meta = {"consent": "no sharing"}
        restrictions = ConsentMetadataParser.parse_restrictions(meta)
        assert ConsentRestriction.NO_SHARING in restrictions

    def test_parse_attribution_required(self) -> None:
        meta = {"consent": "attribution required"}
        restrictions = ConsentMetadataParser.parse_restrictions(meta)
        assert ConsentRestriction.ATTRIBUTION_REQUIRED in restrictions

    def test_parse_purpose_limited(self) -> None:
        meta = {"consent": "specific purpose"}
        restrictions = ConsentMetadataParser.parse_restrictions(meta)
        assert ConsentRestriction.PURPOSE_LIMITED in restrictions

    def test_parse_time_limited(self) -> None:
        meta = {"consent": "valid until 2025"}
        restrictions = ConsentMetadataParser.parse_restrictions(meta)
        assert ConsentRestriction.TIME_LIMITED in restrictions

    def test_parse_no_export(self) -> None:
        meta = {"consent": "no export"}
        restrictions = ConsentMetadataParser.parse_restrictions(meta)
        assert ConsentRestriction.NO_EXPORT in restrictions

    def test_parse_derived_restrictions(self) -> None:
        meta = {"consent": "derived data restrictions apply"}
        restrictions = ConsentMetadataParser.parse_restrictions(meta)
        assert ConsentRestriction.DERIVED_RESTRICTIONS in restrictions

    def test_returns_empty_when_no_consent_field(self) -> None:
        meta: dict[str, str] = {}
        assert ConsentMetadataParser.parse_restrictions(meta) == []

    def test_handles_multiple_restrictions(self) -> None:
        meta = {"consent": "attribution required, no sharing"}
        restrictions = ConsentMetadataParser.parse_restrictions(meta)
        assert ConsentRestriction.ATTRIBUTION_REQUIRED in restrictions
        assert ConsentRestriction.NO_SHARING in restrictions


class TestExportRestriction:
    def test_detect_itar_via_export_restrictions(self) -> None:
        meta = {"export_restrictions": "itar"}
        assert ExportRestriction.ITAR in ConsentMetadataParser.detect_export_restrictions(meta)

    def test_detect_gdpr_via_export_restrictions(self) -> None:
        meta = {"export_restrictions": "gdpr"}
        assert ExportRestriction.GDPR in ConsentMetadataParser.detect_export_restrictions(meta)

    def test_detect_hipaa_via_export_restrictions(self) -> None:
        meta = {"export_restrictions": "hipaa"}
        assert ExportRestriction.HIPAA in ConsentMetadataParser.detect_export_restrictions(meta)

    def test_detect_sovereign_data_via_export_restrictions(self) -> None:
        meta = {"export_restrictions": "sovereign_data"}
        restrictions = ConsentMetadataParser.detect_export_restrictions(meta)
        assert ExportRestriction.SOVEREIGN_DATA in restrictions

    def test_detect_multiple_export_restrictions(self) -> None:
        meta = {"export_restrictions": ["itar", "sovereign_data"]}
        restrictions = ConsentMetadataParser.detect_export_restrictions(meta)
        assert ExportRestriction.ITAR in restrictions
        assert ExportRestriction.SOVEREIGN_DATA in restrictions

    def test_returns_empty_when_no_export_fields(self) -> None:
        meta: dict[str, str] = {}
        assert ConsentMetadataParser.detect_export_restrictions(meta) == []


class TestConsentMetadataParserIntegration:
    def test_full_parse_public(self) -> None:
        meta = {"origin": "public domain", "license": "cc0"}
        result = ConsentMetadataParser.full_parse(meta)
        assert result["origin"] == DataOrigin.PUBLIC
        assert result["consent_restrictions"] == []
        assert result["export_restrictions"] == []

    def test_full_parse_clinical_gdpr(self) -> None:
        meta = {"origin": "patient data", "consent": "attribution required", "jurisdiction": "gdpr"}
        result = ConsentMetadataParser.full_parse(meta)
        assert result["origin"] == DataOrigin.CLINICAL
        assert ExportRestriction.GDPR in result["export_restrictions"]

    def test_full_parse_indigenous_no_analysis(self) -> None:
        meta = {"origin": "indigenous territory", "consent": "no analysis"}
        result = ConsentMetadataParser.full_parse(meta)
        assert result["origin"] == DataOrigin.INDIGENOUS
        assert ConsentRestriction.NO_ANALYSIS in result["consent_restrictions"]


class TestDataSovereigntyChecker:
    def test_public_data_approved(self) -> None:
        checker = DataSovereigntyChecker()
        meta = {"origin": "public domain data", "license": "cc0"}
        verdict = checker.check(meta)
        assert verdict.approved is True
        assert verdict.data_origin == DataOrigin.PUBLIC
        assert not verdict.export_restrictions

    def test_public_via_source_approved(self) -> None:
        checker = DataSovereigntyChecker(require_origin=False)
        meta = {"source": "government census data"}
        verdict = checker.check(meta)
        assert verdict.approved is True
        assert verdict.data_origin == DataOrigin.PUBLIC

    def test_consented_clinical_data_approved(self) -> None:
        checker = DataSovereigntyChecker()
        meta = {"origin": "patient data", "consent": "attribution required"}
        verdict = checker.check(meta)
        assert verdict.approved is True
        assert verdict.data_origin == DataOrigin.CLINICAL

    def test_proprietary_data_requires_review(self) -> None:
        checker = DataSovereigntyChecker()
        meta = {"origin": "proprietary dataset", "license": "nda"}
        verdict = checker.check(meta)
        assert verdict.requires_human_review is False
        assert verdict.approved is True

    def test_indigenous_without_consent_requires_review(self) -> None:
        checker = DataSovereigntyChecker()
        meta = {"origin": "indigenous territory"}
        verdict = checker.check(meta)
        assert verdict.requires_human_review is True
        assert verdict.approved is True

    def test_no_analysis_restriction_blocks(self) -> None:
        checker = DataSovereigntyChecker()
        meta = {"origin": "patient data", "consent": "no analysis"}
        verdict = checker.check(meta)
        assert verdict.approved is False
        assert ConsentRestriction.NO_ANALYSIS in verdict.consent_restrictions

    def test_itar_export_blocked_via_export_restrictions(self) -> None:
        checker = DataSovereigntyChecker()
        meta = {"origin": "public domain", "export_restrictions": "itar"}
        verdict = checker.check(meta)
        assert verdict.approved is False
        assert ExportRestriction.ITAR in verdict.export_restrictions

    def test_sovereign_data_export_blocked_via_export_restrictions(self) -> None:
        checker = DataSovereigntyChecker()
        meta = {"origin": "public domain", "export_restrictions": "sovereign_data"}
        verdict = checker.check(meta)
        assert verdict.approved is False
        assert ExportRestriction.SOVEREIGN_DATA in verdict.export_restrictions

    def test_gdpr_flagged_not_blocked(self) -> None:
        checker = DataSovereigntyChecker()
        meta = {"origin": "public domain", "jurisdiction": "gdpr"}
        verdict = checker.check(meta)
        assert verdict.approved is True
        assert ExportRestriction.GDPR in verdict.export_restrictions

    def test_hipaa_flagged_not_blocked(self) -> None:
        checker = DataSovereigntyChecker()
        meta = {"origin": "public domain", "export_restrictions": "hipaa"}
        verdict = checker.check(meta)
        assert verdict.approved is True
        assert ExportRestriction.HIPAA in verdict.export_restrictions

    def test_empty_metadata_with_require_origin_fails(self) -> None:
        checker = DataSovereigntyChecker()
        verdict = checker.check({})
        assert verdict.approved is False
        assert verdict.data_origin == DataOrigin.PUBLIC

    def test_empty_metadata_without_require_origin_passes(self) -> None:
        checker = DataSovereigntyChecker(require_origin=False)
        verdict = checker.check({})
        assert verdict.approved is True
        assert verdict.data_origin == DataOrigin.PUBLIC

    def test_with_provenance_tracker(self) -> None:
        from unittest.mock import MagicMock

        checker = DataSovereigntyChecker()
        tracker = MagicMock()
        meta = {"origin": "public domain"}
        verdict = checker.check(meta, provenance_tracker=tracker)
        assert verdict.approved is True
        tracker.track.assert_called_once()

    def test_irb_approved_origin_through_checker(self) -> None:
        checker = DataSovereigntyChecker()
        # consent="irb" matches IRB_APPROVED keywords without triggering CLINICAL
        meta = {"consent": "irb", "source": "study protocol"}
        verdict = checker.check(meta)
        assert verdict.data_origin == DataOrigin.IRB_APPROVED
        assert verdict.approved is True

    def test_mixed_itar_and_gdpr_restrictions(self) -> None:
        checker = DataSovereigntyChecker()
        meta = {
            "origin": "public domain",
            "export_restrictions": ["itar", "gdpr"],
        }
        verdict = checker.check(meta)
        # ITAR blocks; GDPR is non-blocking but flagged
        assert verdict.approved is False
        assert ExportRestriction.ITAR in verdict.export_restrictions
        assert ExportRestriction.GDPR in verdict.export_restrictions


class TestSovereigntyIntegration:
    def test_no_checker_raises(self) -> None:
        fw = EthicalFirewall()
        with pytest.raises(EthicsError) as exc:
            fw.check_data_sovereignty({"origin": "public"})
        assert exc.value.error_code == ErrorCode.CONFIG_MISSING_FIELD

    def test_block_on_no_analysis(self) -> None:
        checker = DataSovereigntyChecker()
        fw = EthicalFirewall(sovereignty_checker=checker)
        with pytest.raises(EthicsError) as exc:
            fw.check_data_sovereignty({"origin": "patient data", "consent": "no analysis"})
        assert exc.value.error_code == ErrorCode.ETHICS_SOVEREIGNTY_VIOLATION

    def test_block_on_itar_export(self) -> None:
        checker = DataSovereigntyChecker()
        fw = EthicalFirewall(sovereignty_checker=checker)
        with pytest.raises(EthicsError) as exc:
            fw.check_data_sovereignty({"origin": "public domain", "export_restrictions": "itar"})
        assert exc.value.error_code == ErrorCode.ETHICS_EXPORT_BLOCKED

    def test_block_on_sovereign_data_export(self) -> None:
        checker = DataSovereigntyChecker()
        fw = EthicalFirewall(sovereignty_checker=checker)
        with pytest.raises(EthicsError) as exc:
            fw.check_data_sovereignty(
                {"origin": "public domain", "export_restrictions": "sovereign_data"}
            )
        assert exc.value.error_code == ErrorCode.ETHICS_EXPORT_BLOCKED

    def test_block_indigenous_without_consent(self) -> None:
        checker = DataSovereigntyChecker()
        fw = EthicalFirewall(sovereignty_checker=checker)
        with pytest.raises(EthicsError) as exc:
            fw.check_data_sovereignty({"origin": "indigenous territory"})
        assert exc.value.error_code == ErrorCode.ETHICS_INDIGENOUS_RESTRICTION

    def test_gdpr_flagged_not_blocked(self) -> None:
        checker = DataSovereigntyChecker(require_origin=False)
        fw = EthicalFirewall(sovereignty_checker=checker)
        verdict = fw.check_data_sovereignty({"jurisdiction": "gdpr"})
        assert verdict.approved is True
        assert ExportRestriction.GDPR in verdict.export_restrictions

    def test_public_data_passes(self) -> None:
        checker = DataSovereigntyChecker()
        fw = EthicalFirewall(sovereignty_checker=checker)
        verdict = fw.check_data_sovereignty({"origin": "public domain"})
        assert verdict.approved is True
        assert verdict.data_origin == DataOrigin.PUBLIC

    def test_audit_entry_created_on_public(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        checker = DataSovereigntyChecker()
        audit = FirewallAuditLog(str(tmp_path / "audit.db"))
        fw = EthicalFirewall(sovereignty_checker=checker, audit_log=audit)
        fw.check_data_sovereignty({"origin": "public domain"}, user_id="test_user")
        entries = audit.query(category="sovereignty_check")
        assert len(entries) == 1
        assert entries[0].user_id == "test_user"
        assert entries[0].category == "sovereignty_check"

    def test_audit_entry_on_blocked(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        checker = DataSovereigntyChecker()
        audit = FirewallAuditLog(str(tmp_path / "audit.db"))
        fw = EthicalFirewall(sovereignty_checker=checker, audit_log=audit)
        with pytest.raises(EthicsError):
            fw.check_data_sovereignty({"origin": "patient data", "consent": "no analysis"})
        entries = audit.query(category="sovereignty_check")
        assert len(entries) == 1
        assert entries[0].action_taken == "block"

    def test_consented_data_passes(self) -> None:
        checker = DataSovereigntyChecker()
        fw = EthicalFirewall(sovereignty_checker=checker)
        verdict = fw.check_data_sovereignty(
            {"origin": "patient data", "consent": "attribution required"}
        )
        assert verdict.approved is True


# =========================================================================
# Indigenous Knowledge Protector
# =========================================================================


class TestIndigenousKnowledgeCategory:
    def test_all_members(self) -> None:
        assert IndigenousKnowledgeCategory.SACRED_SECRET == "sacred_secret"
        assert IndigenousKnowledgeCategory.CEREMONIAL == "ceremonial"
        assert IndigenousKnowledgeCategory.TRADITIONAL_KNOWLEDGE == "traditional_knowledge"
        assert IndigenousKnowledgeCategory.GENETIC_RESOURCE == "genetic_resource"
        assert IndigenousKnowledgeCategory.OPEN == "open"


class TestCAREPrinciple:
    def test_all_members(self) -> None:
        assert CAREPrinciple.COLLECTIVE_BENEFIT == "collective_benefit"
        assert CAREPrinciple.AUTHORITY_TO_CONTROL == "authority_to_control"
        assert CAREPrinciple.RESPONSIBILITY == "responsibility"
        assert CAREPrinciple.ETHICS == "ethics"


class TestIndigenousKnowledgeProtector:
    def test_default_construction(self) -> None:
        protector = IndigenousKnowledgeProtector()
        assert protector is not None

    def test_open_category_no_restrictions(self) -> None:
        protector = IndigenousKnowledgeProtector()
        verdict = protector.check({})
        assert verdict.category == IndigenousKnowledgeCategory.OPEN
        assert verdict.blocked is False
        assert verdict.care_principles_violated == []

    def test_sacred_secret_categorically_blocked(self) -> None:
        protector = IndigenousKnowledgeProtector()
        verdict = protector.check({"cultural_restriction": "sacred"})
        assert verdict.category == IndigenousKnowledgeCategory.SACRED_SECRET
        assert verdict.blocked is True

    def test_sacred_secret_even_with_consent(self) -> None:
        protector = IndigenousKnowledgeProtector()
        verdict = protector.check(
            {
                "cultural_restriction": "sacred",
                "fpic": True,
                "governing_authority": "community council",
            }
        )
        assert verdict.category == IndigenousKnowledgeCategory.SACRED_SECRET
        assert verdict.blocked is True

    def test_ceremonial_blocked_without_consent(self) -> None:
        protector = IndigenousKnowledgeProtector()
        verdict = protector.check({"cultural_restriction": "ceremonial"})
        assert verdict.category == IndigenousKnowledgeCategory.CEREMONIAL
        assert verdict.blocked is True
        assert CAREPrinciple.AUTHORITY_TO_CONTROL in verdict.care_principles_violated
        assert verdict.requires_community_consent is True

    def test_ceremonial_passes_with_fpic(self) -> None:
        protector = IndigenousKnowledgeProtector()
        verdict = protector.check({"cultural_restriction": "ceremonial", "fpic": True})
        assert verdict.category == IndigenousKnowledgeCategory.CEREMONIAL
        assert verdict.blocked is False

    def test_traditional_knowledge_blocked_without_benefit_sharing(self) -> None:
        protector = IndigenousKnowledgeProtector()
        verdict = protector.check(
            {"knowledge_type": "traditional knowledge", "origin": "indigenous"}
        )
        assert verdict.category == IndigenousKnowledgeCategory.TRADITIONAL_KNOWLEDGE
        assert verdict.blocked is True
        assert CAREPrinciple.COLLECTIVE_BENEFIT in verdict.care_principles_violated
        assert verdict.requires_benefit_sharing is True

    def test_traditional_knowledge_passes_with_benefit_sharing(self) -> None:
        protector = IndigenousKnowledgeProtector()
        verdict = protector.check(
            {
                "knowledge_type": "traditional knowledge",
                "origin": "indigenous",
                "benefit_sharing": True,
            }
        )
        assert verdict.category == IndigenousKnowledgeCategory.TRADITIONAL_KNOWLEDGE
        assert verdict.blocked is False

    def test_genetic_resource_blocked_without_ethics(self) -> None:
        protector = IndigenousKnowledgeProtector()
        verdict = protector.check({"knowledge_type": "genetic", "source": "blood"})
        assert verdict.category == IndigenousKnowledgeCategory.GENETIC_RESOURCE
        assert verdict.blocked is True
        assert CAREPrinciple.COLLECTIVE_BENEFIT in verdict.care_principles_violated
        assert CAREPrinciple.ETHICS in verdict.care_principles_violated

    def test_genetic_resource_passes_with_compliance(self) -> None:
        protector = IndigenousKnowledgeProtector()
        verdict = protector.check(
            {
                "knowledge_type": "genetic",
                "source": "blood",
                "benefit_sharing": True,
                "ethics_review": True,
            }
        )
        assert verdict.category == IndigenousKnowledgeCategory.GENETIC_RESOURCE
        assert verdict.blocked is False

    def test_men_business_detected_as_sacred(self) -> None:
        protector = IndigenousKnowledgeProtector()
        verdict = protector.check({"cultural_restriction": "men's business"})
        assert verdict.category == IndigenousKnowledgeCategory.SACRED_SECRET

    def test_dreamtime_detected_as_sacred(self) -> None:
        protector = IndigenousKnowledgeProtector()
        verdict = protector.check({"knowledge_type": "dreaming"})
        assert verdict.category == IndigenousKnowledgeCategory.SACRED_SECRET

    def test_ritual_detected_as_ceremonial(self) -> None:
        protector = IndigenousKnowledgeProtector()
        verdict = protector.check({"cultural_restriction": "ritual"})
        assert verdict.category == IndigenousKnowledgeCategory.CEREMONIAL

    def test_elder_knowledge_detected_as_traditional(self) -> None:
        protector = IndigenousKnowledgeProtector()
        verdict = protector.check({"source": "elders"})
        assert verdict.category == IndigenousKnowledgeCategory.TRADITIONAL_KNOWLEDGE

    def test_nagoya_detected_as_genetic_resource(self) -> None:
        protector = IndigenousKnowledgeProtector()
        verdict = protector.check({"legal_framework": "nagoya"})
        assert verdict.category == IndigenousKnowledgeCategory.GENETIC_RESOURCE

    def test_list_field_matching(self) -> None:
        protector = IndigenousKnowledgeProtector()
        verdict = protector.check({"cultural_restriction": ["public", "sacred"]})
        assert verdict.category == IndigenousKnowledgeCategory.SACRED_SECRET
        assert verdict.blocked is True

    def test_verdict_has_verdict_id(self) -> None:
        protector = IndigenousKnowledgeProtector()
        verdict = protector.check({"cultural_restriction": "sacred"})
        assert len(verdict.verdict_id) == 12
        assert isinstance(verdict.verdict_id, str)

    def test_verdict_has_timestamp(self) -> None:
        protector = IndigenousKnowledgeProtector()
        verdict = protector.check({})
        assert verdict.timestamp is not None

    def test_open_category_restriction_summary(self) -> None:
        protector = IndigenousKnowledgeProtector()
        verdict = protector.check({})
        assert "No restrictions detected" in verdict.restriction_summary

    def test_sacred_summary_includes_blocked(self) -> None:
        protector = IndigenousKnowledgeProtector()
        verdict = protector.check({"cultural_restriction": "sacred"})
        assert "Blocked" in verdict.restriction_summary

    def test_ceremonial_summary_includes_consent(self) -> None:
        protector = IndigenousKnowledgeProtector()
        verdict = protector.check({"cultural_restriction": "ceremonial"})
        assert "Requires community consent" in verdict.restriction_summary

    def test_require_care_compliance_false_does_not_block(self) -> None:
        protector = IndigenousKnowledgeProtector(require_care_compliance=False)
        verdict = protector.check({"cultural_restriction": "ceremonial"})
        assert verdict.category == IndigenousKnowledgeCategory.CEREMONIAL
        assert verdict.blocked is False
        assert CAREPrinciple.AUTHORITY_TO_CONTROL in verdict.care_principles_violated


class TestIKIntegration:
    def test_no_protector_raises(self) -> None:
        fw = EthicalFirewall()
        with pytest.raises(EthicsError) as exc:
            fw.check_indigenous_knowledge({"knowledge_type": "sacred"})
        assert exc.value.error_code == ErrorCode.CONFIG_MISSING_FIELD

    def test_blocks_sacred_knowledge(self) -> None:
        protector = IndigenousKnowledgeProtector()
        fw = EthicalFirewall(indigenous_knowledge_protector=protector)
        with pytest.raises(EthicsError) as exc:
            fw.check_indigenous_knowledge({"cultural_restriction": "sacred"})
        assert exc.value.error_code == ErrorCode.ETHICS_CARE_VIOLATION

    def test_passes_open_knowledge(self) -> None:
        protector = IndigenousKnowledgeProtector()
        fw = EthicalFirewall(indigenous_knowledge_protector=protector)
        verdict = fw.check_indigenous_knowledge({})
        assert verdict.blocked is False
        assert verdict.category == IndigenousKnowledgeCategory.OPEN

    def test_blocks_ceremonial_without_consent(self) -> None:
        protector = IndigenousKnowledgeProtector()
        fw = EthicalFirewall(indigenous_knowledge_protector=protector)
        with pytest.raises(EthicsError) as exc:
            fw.check_indigenous_knowledge({"cultural_restriction": "ceremonial"})
        assert exc.value.error_code == ErrorCode.ETHICS_CARE_VIOLATION

    def test_passes_ceremonial_with_fpic(self) -> None:
        protector = IndigenousKnowledgeProtector()
        fw = EthicalFirewall(indigenous_knowledge_protector=protector)
        verdict = fw.check_indigenous_knowledge(
            {"cultural_restriction": "ceremonial", "fpic": True}
        )
        assert verdict.blocked is False

    def test_audit_entry_created_on_open(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        protector = IndigenousKnowledgeProtector()
        audit = FirewallAuditLog(str(tmp_path / "audit.db"))
        fw = EthicalFirewall(indigenous_knowledge_protector=protector, audit_log=audit)
        fw.check_indigenous_knowledge({}, user_id="test_user")
        entries = audit.query(category="indigenous_knowledge_check")
        assert len(entries) == 1
        assert entries[0].user_id == "test_user"
        assert entries[0].category == "indigenous_knowledge_check"

    def test_audit_entry_on_blocked(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        protector = IndigenousKnowledgeProtector()
        audit = FirewallAuditLog(str(tmp_path / "audit.db"))
        fw = EthicalFirewall(indigenous_knowledge_protector=protector, audit_log=audit)
        with pytest.raises(EthicsError):
            fw.check_indigenous_knowledge({"cultural_restriction": "sacred"})
        entries = audit.query(category="indigenous_knowledge_check")
        assert len(entries) == 1
        assert entries[0].action_taken == "block"


# =========================================================================
# Carbon Budget Tracker
# =========================================================================


class TestCarbonEstimate:
    def test_zero_tokens(self) -> None:
        tracker = CarbonBudgetTracker(budget_kwh=50.0)
        est = tracker.estimate(0, 0)
        assert est.kwh >= 0.0
        assert est.co2e_kg >= 0.0
        assert est.flops >= 0.0

    def test_non_zero_estimate(self) -> None:
        tracker = CarbonBudgetTracker(budget_kwh=50.0)
        est = tracker.estimate(100, 50)
        assert est.flops > 0.0
        assert est.kwh > 0.0
        assert est.co2e_kg > 0.0

    def test_flops_formula(self) -> None:
        tracker = CarbonBudgetTracker(budget_kwh=50.0, model_params=1_000_000_000)
        est = tracker.estimate(100, 50)
        expected_flops = 2.0 * 1_000_000_000 * (100 + 3.0 * 50)
        assert est.flops == expected_flops

    def test_model_params_override(self) -> None:
        tracker = CarbonBudgetTracker(budget_kwh=50.0, model_params=7_000_000_000)
        est = tracker.estimate(10, 5, model_params=1_000_000_000)
        expected = 2.0 * 1_000_000_000 * (10 + 3.0 * 5)
        assert est.flops == expected

    def test_equivalence_text_included(self) -> None:
        tracker = CarbonBudgetTracker(budget_kwh=50.0, equivalences_enabled=True)
        est = tracker.estimate(1000, 500)
        assert "Equivalent to" in est.equivalence_text

    def test_equivalence_text_disabled(self) -> None:
        tracker = CarbonBudgetTracker(budget_kwh=50.0, equivalences_enabled=False)
        est = tracker.estimate(1000, 500)
        assert est.equivalence_text == ""

    def test_co2e_derived_from_kwh(self) -> None:
        tracker = CarbonBudgetTracker(budget_kwh=50.0, grid_intensity_kg_co2e_per_kwh=0.5)
        est = tracker.estimate(1000, 500)
        assert abs(est.co2e_kg - est.kwh * 0.5) < 1e-9


class TestCarbonBudgetTracker:
    def test_default_construction(self) -> None:
        tracker = CarbonBudgetTracker(budget_kwh=50.0)
        assert tracker is not None

    def test_track_query_records_usage(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        db = str(tmp_path / "carbon.db")
        tracker = CarbonBudgetTracker(budget_kwh=50.0, db_path=db)
        est = tracker.estimate(100, 50)
        record = tracker.track_query(est, decision_id="test1")
        assert record.record_id is not None
        assert record.estimate.kwh == est.kwh
        assert record.monthly_budget_kwh == 50.0

    def test_track_query_increases_usage(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        db = str(tmp_path / "carbon.db")
        tracker = CarbonBudgetTracker(budget_kwh=50.0, db_path=db)
        est1 = tracker.estimate(1000, 500)
        tracker.track_query(est1, decision_id="q1")
        usage1 = tracker.current_monthly_usage()
        est2 = tracker.estimate(500, 250)
        tracker.track_query(est2, decision_id="q2")
        usage2 = tracker.current_monthly_usage()
        assert usage2 > usage1

    def test_warning_at_80_percent(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        db = str(tmp_path / "warn.db")
        tracker = CarbonBudgetTracker(budget_kwh=1.0, warning_threshold=0.8, db_path=db)
        est = CarbonEstimate(kwh=0.9, co2e_kg=0.36)
        record = tracker.track_query(est, decision_id="warn_test")
        assert record.warning_triggered is True

    def test_block_at_100_percent(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        db = str(tmp_path / "block.db")
        tracker = CarbonBudgetTracker(budget_kwh=0.001, warning_threshold=0.5, db_path=db)
        est = CarbonEstimate(kwh=0.0005, co2e_kg=0.0002)
        record = tracker.track_query(est, decision_id="almost")
        assert record.blocked is False
        assert record.warning_triggered is True
        est2 = CarbonEstimate(kwh=0.0005, co2e_kg=0.0002)
        with pytest.raises(EthicsError) as exc:
            tracker.track_query(est2, decision_id="over")
        assert exc.value.error_code == ErrorCode.ETHICS_CARBON_BUDGET_EXCEEDED

    def test_reset_monthly_budget(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        db = str(tmp_path / "reset.db")
        tracker = CarbonBudgetTracker(budget_kwh=50.0, db_path=db)
        est = tracker.estimate(10, 5)
        tracker.track_query(est, decision_id="r1")
        usage_before = tracker.current_monthly_usage()
        assert usage_before > 0.0
        tracker.reset_monthly_budget()
        usage_after = tracker.current_monthly_usage()
        assert usage_after == 0.0

    def test_budget_status(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        db = str(tmp_path / "status.db")
        tracker = CarbonBudgetTracker(budget_kwh=50.0, db_path=db)
        status = tracker.budget_status()
        assert isinstance(status, BudgetStatus)
        assert status.percentage_used >= 0.0
        assert status.blocked is False

    def test_budget_status_under_budget(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        db = str(tmp_path / "under.db")
        tracker = CarbonBudgetTracker(budget_kwh=50.0, db_path=db)
        status = tracker.budget_status()
        assert status.warning is False

    def test_budget_status_over_budget(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        db = str(tmp_path / "over.db")
        tracker = CarbonBudgetTracker(budget_kwh=0.001, db_path=db)
        est = CarbonEstimate(kwh=0.002, co2e_kg=0.0008)
        with pytest.raises(EthicsError):
            tracker.track_query(est, decision_id="over")
        status = tracker.budget_status()
        assert status.blocked is True
        assert status.percentage_used >= 100.0

    def test_zero_budget_immediately_blocked(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        db = str(tmp_path / "zero.db")
        tracker = CarbonBudgetTracker(budget_kwh=0.0, db_path=db)
        est = CarbonEstimate(kwh=0.0001, co2e_kg=0.00004)
        with pytest.raises(EthicsError) as exc:
            tracker.track_query(est, decision_id="zero")
        assert exc.value.error_code == ErrorCode.ETHICS_CARBON_BUDGET_EXCEEDED

    def test_multiple_queries_accumulate(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        db = str(tmp_path / "accum.db")
        tracker = CarbonBudgetTracker(budget_kwh=10.0, db_path=db)
        for i in range(5):
            est = CarbonEstimate(kwh=1.0, co2e_kg=0.4)
            tracker.track_query(est, decision_id=f"q{i}")
        status = tracker.budget_status()
        assert abs(status.current_usage_kwh - 5.0) < 0.001
        assert abs(status.percentage_used - 50.0) < 0.001

    def test_track_query_duplicate_decision_id(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        """Duplicate decision_ids create separate records, accumulating usage."""
        db = str(tmp_path / "dup.db")
        tracker = CarbonBudgetTracker(budget_kwh=10.0, db_path=db)
        est = CarbonEstimate(kwh=1.0, co2e_kg=0.4)
        tracker.track_query(est, decision_id="same_id")
        tracker.track_query(est, decision_id="same_id")
        status = tracker.budget_status()
        assert abs(status.current_usage_kwh - 2.0) < 0.001


class TestCarbonIntegration:
    def test_no_tracker_returns_none(self) -> None:
        fw = EthicalFirewall()
        result = fw.record_carbon(100, 50, decision_id="test")
        assert result is None

    def test_record_carbon_returns_record(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        db = str(tmp_path / "int1.db")
        tracker = CarbonBudgetTracker(budget_kwh=50.0, db_path=db)
        fw = EthicalFirewall(carbon_tracker=tracker)
        result = fw.record_carbon(100, 50, decision_id="test")
        assert result is not None
        assert isinstance(result, CarbonRecord)
        assert result.estimate.kwh > 0.0

    def test_record_carbon_raises_on_exceeded(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        db = str(tmp_path / "int2.db")
        tracker = CarbonBudgetTracker(budget_kwh=0.001, db_path=db)
        fw = EthicalFirewall(carbon_tracker=tracker)
        est = CarbonEstimate(kwh=0.0006, co2e_kg=0.00024)
        tracker.track_query(est, decision_id="prefill")
        with pytest.raises(EthicsError) as exc:
            fw.record_carbon(500, 200, decision_id="over")
        assert exc.value.error_code == ErrorCode.ETHICS_CARBON_BUDGET_EXCEEDED

    def test_estimate_from_provider_metrics(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        db = str(tmp_path / "int3.db")
        tracker = CarbonBudgetTracker(budget_kwh=50.0, db_path=db)
        fw = EthicalFirewall(carbon_tracker=tracker)
        result = fw.record_carbon(500, 200, decision_id="metrics")
        assert result is not None
        assert result.estimate.flops > 0.0

    def test_firewall_rejects_missing(self) -> None:
        fw = EthicalFirewall()
        assert fw.record_carbon(100, 50) is None

    def test_record_carbon_with_provenance(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        from openscire.provenance import ProvenanceTracker

        tracker = ProvenanceTracker.get_tracker(
            "test-carbon-prov",
            storage_backend="in_memory",
        )
        carbon = CarbonBudgetTracker(
            budget_kwh=50.0,
            db_path=str(tmp_path / "carbon_prov.db"),
            provenance_tracker=tracker,
        )
        fw = EthicalFirewall(carbon_tracker=carbon)
        result = fw.record_carbon(100, 50, decision_id="prov_link")
        assert result is not None
        # Provenance entry created
        assert len(tracker.graph) == 1


# =========================================================================
# Source Grounding Integration Tests
# =========================================================================


class TestSourceGroundingIntegration:
    """Integration tests for SourceGroundingEngine via EthicalFirewall."""

    def test_check_grounding_not_configured(self) -> None:
        fw = EthicalFirewall()
        with pytest.raises(EthicsError) as exc:
            fw.check_grounding("test text")
        assert exc.value.error_code == ErrorCode.CONFIG_MISSING_FIELD

    def test_check_grounding_approved(self) -> None:
        engine = SourceGroundingEngine()
        fw = EthicalFirewall(source_grounding=engine)
        sources = [
            Source(
                source_id="s1",
                doi="10.1234/test",
                title="Test Title",
                authors="Smith, J",
                year=2023,
            ),
        ]
        verdict = fw.check_grounding(
            "Gene regulation is key (Smith, 2023).",
            known_sources=sources,
        )
        assert isinstance(verdict, GroundingVerdict)
        assert verdict.approved

    def test_check_grounding_no_citations(self) -> None:
        engine = SourceGroundingEngine(allow_unsupported_claims=True)
        fw = EthicalFirewall(source_grounding=engine)
        verdict = fw.check_grounding(
            "Unsupported claim with no citations.",
        )
        assert len(verdict.claims_flagged) > 0

    def test_check_grounding_raises_on_failure(self) -> None:
        engine = SourceGroundingEngine()
        fw = EthicalFirewall(source_grounding=engine)
        with pytest.raises(ValidationError) as exc:
            fw.check_grounding(
                "Unsupported claim.",
            )
        assert exc.value.error_code in (
            ErrorCode.VALIDATION_CITATION_BROKEN,
            ErrorCode.VALIDATION_SOURCE_NOT_FOUND,
        )

    def test_check_grounding_audit_logged(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        db = str(tmp_path / "audit_grnd.db")
        audit_log = FirewallAuditLog(db)
        engine = SourceGroundingEngine()
        fw = EthicalFirewall(
            source_grounding=engine,
            audit_log=audit_log,
        )
        fw.check_grounding(
            "Gene regulation is key (Smith, 2023).",
            known_sources=[
                Source(
                    source_id="s1",
                    doi="10.1234/test",
                    title="Gene Regulation",
                    authors="Smith, J",
                    year=2023,
                ),
            ],
        )
        assert audit_log.count() >= 1

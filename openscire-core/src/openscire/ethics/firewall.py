from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from openscire.constants import ErrorCode, RiskTier
from openscire.exceptions import EthicsError
from openscire.logging import get_logger
from openscire.provider.base import ModelProvider, ProviderConfig
from openscire.provider.models import ChatMessage, Chunk, ProviderMetrics

from .audit import FirewallAuditLog
from .carbon import CarbonBudgetTracker, CarbonRecord
from .classifier import DURCClassifier
from .durc import DEFAULT_KEYWORD_PATTERNS, EMBEDDING_SEEDS, build_default_rules
from .indigenous_knowledge import (
    IndigenousKnowledgeProtector,
    IndigenousKnowledgeVerdict,
)
from .models import (
    ConsentRestriction,
    DURCResult,
    EthicsDecision,
    ExportRestriction,
    FirewallAction,
    FirewallAuditEntry,
    FirewallRule,
    GroundingVerdict,
    OverrideRecord,
    ScanLevel,
    Source,
    SovereigntyVerdict,
    TierAssignment,
    TierGovernanceAction,
)
from .source_grounding import SourceGroundingEngine
from .sovereignty import DataSovereigntyChecker
from .tier import CoolOffRegistry, TierClassifier

logger = get_logger("openscire.ethics.firewall")


class EthicalFirewall:
    """Configurable ethical firewall with DURC detection, tier classification,
    and policy enforcement.

    Scans prompt and response text against a configurable rule set using
    keyword, embedding, and LLM-based classifiers.  Enforces per-rule
    actions (flag, warn, block, escalate) and differential speed governance
    (tier-based cooling-off and human checkpoints).  Records all decisions
    to an append-only audit log.
    """

    def __init__(
        self,
        rules: list[FirewallRule] | None = None,
        audit_log: FirewallAuditLog | None = None,
        classifier: DURCClassifier | None = None,
        default_action: FirewallAction = FirewallAction.WARN,
        audit_signing_key: str | None = None,
        tier_classifier: TierClassifier | None = None,
        cool_off_registry: CoolOffRegistry | None = None,
        provenance_tracker: Any = None,  # noqa: ANN401
        sovereignty_checker: DataSovereigntyChecker | None = None,
        indigenous_knowledge_protector: IndigenousKnowledgeProtector | None = None,
        carbon_tracker: CarbonBudgetTracker | None = None,
        source_grounding: SourceGroundingEngine | None = None,
    ) -> None:
        self._rules = rules if rules is not None else build_default_rules()
        self._audit_log = audit_log or FirewallAuditLog()
        self._classifier = classifier or DURCClassifier(
            keyword_patterns=DEFAULT_KEYWORD_PATTERNS,
            embedding_seeds=EMBEDDING_SEEDS,
        )
        self._default_action = default_action
        self._audit_signing_key = audit_signing_key
        self._tier_classifier = tier_classifier
        self._cool_off_registry = cool_off_registry
        self._provenance_tracker = provenance_tracker
        self._sovereignty_checker = sovereignty_checker
        self._indigenous_knowledge_protector = indigenous_knowledge_protector
        self._carbon_tracker = carbon_tracker
        self._source_grounding = source_grounding

    @property
    def rules(self) -> list[FirewallRule]:
        return list(self._rules)

    @property
    def audit_log(self) -> FirewallAuditLog:
        return self._audit_log

    def wrap(self, provider: ModelProvider) -> FirewalledProvider:
        """Wrap a ModelProvider with this firewall.

        Returns a FirewalledProvider that intercepts stream_chat() to
        scan prompts and responses.
        """
        return FirewalledProvider(inner=provider, firewall=self)

    async def scan_prompt(
        self,
        messages: list[ChatMessage],
        user_id: str = "",
    ) -> EthicsDecision:
        """Scan incoming prompt messages for DURC content and risk tier.

        Args:
            messages: The conversation messages to scan.
            user_id: Optional user identifier for audit trail.

        Returns:
            An EthicsDecision with all triggered results, tier assignment,
            and overall action.

        Raises:
            EthicsError: If any rule triggers a BLOCK or ESCALATE action,
                or if tier governance (cooling-off / human checkpoint)
                prevents execution.
        """
        text = _messages_to_text(messages)
        input_hash = hashlib.sha256(text.encode()).hexdigest()
        text_snippet = text[:500]

        # 1. DURC scan
        durc_results = await self._classifier.scan(text, self._rules, self._default_action)

        # 2. Tier classification
        tier_result = None
        tier_assignment = None
        if self._tier_classifier is not None:
            tier_result = await self._tier_classifier.classify(
                text, provenance_tracker=self._provenance_tracker
            )
            tier_assignment = TierAssignment(
                assignment_id=str(uuid.uuid4()),
                tier=tier_result.assigned_tier,
                domain=tier_result.domain,
                confidence=tier_result.confidence,
                match_type=tier_result.match_type,
                governance_action=tier_result.governance_action,
            )

        # 3. Build decision
        decision = self._build_decision(
            scan_level=ScanLevel.PROMPT,
            results=durc_results,
            input_hash=input_hash,
            text_snippet=text_snippet,
            tier_assignment=tier_assignment,
        )

        # 4. Audit DURC results
        self._audit_decision(decision, durc_results, user_id)

        # 5. Check DURC enforcement
        if decision.overall_action in (FirewallAction.BLOCK, FirewallAction.ESCALATE):
            cats = [r.category.value for r in durc_results]
            raise EthicsError(
                message=f"Firewall blocked: DURC detected in prompt [{', '.join(cats)}]",
                source="firewall.scan_prompt",
                error_code=ErrorCode.ETHICS_FIREWALL_BLOCKED,
            )

        # 6. Check tier governance enforcement
        if tier_result is not None:
            self._enforce_tier_governance(tier_result, input_hash, decision)

        return decision

    async def scan_response(
        self,
        text: str,
        user_id: str = "",
    ) -> EthicsDecision:
        """Scan an LLM response for DURC content and risk tier.

        Args:
            text: The response text to scan.
            user_id: Optional user identifier for audit trail.

        Returns:
            An EthicsDecision with all triggered results.

        Raises:
            EthicsError: If any rule triggers a BLOCK or ESCALATE action,
                or if tier governance prevents execution.
        """
        input_hash = hashlib.sha256(text.encode()).hexdigest()
        text_snippet = text[:500]

        durc_results = await self._classifier.scan(text, self._rules, self._default_action)

        tier_result = None
        tier_assignment = None
        if self._tier_classifier is not None:
            tier_result = await self._tier_classifier.classify(
                text, provenance_tracker=self._provenance_tracker
            )
            tier_assignment = TierAssignment(
                assignment_id=str(uuid.uuid4()),
                tier=tier_result.assigned_tier,
                domain=tier_result.domain,
                confidence=tier_result.confidence,
                match_type=tier_result.match_type,
                governance_action=tier_result.governance_action,
            )

        decision = self._build_decision(
            scan_level=ScanLevel.RESPONSE,
            results=durc_results,
            input_hash=input_hash,
            text_snippet=text_snippet,
            tier_assignment=tier_assignment,
        )

        self._audit_decision(decision, durc_results, user_id)

        if decision.overall_action in (FirewallAction.BLOCK, FirewallAction.ESCALATE):
            cats = [r.category.value for r in durc_results]
            raise EthicsError(
                message=f"Firewall blocked: DURC detected in response [{', '.join(cats)}]",
                source="firewall.scan_response",
                error_code=ErrorCode.ETHICS_FIREWALL_BLOCKED,
            )

        if tier_result is not None:
            self._enforce_tier_governance(tier_result, input_hash, decision)

        return decision

    def _enforce_tier_governance(
        self,
        tier_result: Any,  # noqa: ANN401
        input_hash: str,
        decision: EthicsDecision,
    ) -> None:
        """Enforce tier-based governance actions (cooling-off / human checkpoint).

        Args:
            tier_result: The TierResult from classification.
            input_hash: Hash of the scanned text.
            decision: The EthicsDecision being built.

        Raises:
            EthicsError: If governance prevents execution.
        """
        if tier_result.governance_action == TierGovernanceAction.COOLING_OFF:
            decision.governance_blocked = True
            if self._cool_off_registry is not None:
                self._cool_off_registry.register(input_hash)
                if self._cool_off_registry.is_eligible(input_hash):
                    return  # cooling-off period has elapsed
                remaining = self._cool_off_registry.remaining_seconds(input_hash)
            else:
                coff = tier_result.cool_off_hours
                remaining = coff * 3600 if coff else 86400
            raise EthicsError(
                message=(
                    f"Tier 1 (High Risk): 24-hour cooling-off period required. "
                    f"Domain: {tier_result.domain_label}. "
                    f"Time remaining: {remaining / 3600:.1f} hours. "
                ),
                source="firewall._enforce_tier_governance",
                error_code=ErrorCode.ETHICS_TIER_BLOCKED,
            )
        if tier_result.governance_action == TierGovernanceAction.HUMAN_CHECKPOINT:
            decision.governance_blocked = True
            raise EthicsError(
                message=(
                    f"Tier 2 (Medium Risk): Human confirmation required before processing. "
                    f"Domain: {tier_result.domain_label}. "
                    f"This query cannot proceed autonomously."
                ),
                source="firewall._enforce_tier_governance",
                error_code=ErrorCode.ETHICS_TIER_BLOCKED,
            )

    def override_tier(
        self,
        decision_id: str,
        new_tier: RiskTier,
        user_id: str = "",
        justification: str = "",
    ) -> OverrideRecord | None:
        """Manually override the tier for a previous decision.

        Escalation (raising the tier) is allowed without justification.
        Downgrade (lowering the tier) requires a non-empty justification.

        Args:
            decision_id: The decision to override.
            new_tier: The new risk tier to assign.
            user_id: Identifier of the user performing the override.
            justification: Reason for the override (required for downgrades).

        Returns:
            The OverrideRecord if the override was applied, or None if
            the decision was not found.

        Raises:
            EthicsError: If the downgrade lacks justification.
        """
        audit_entries = self._audit_log.query(decision_id=decision_id, limit=1)
        if not audit_entries:
            return None
        entry = audit_entries[0]
        md = entry.metadata
        raw_tier = md.get("tier", RiskTier.LOW.value)
        try:
            original_tier = RiskTier(raw_tier)
        except ValueError:
            original_tier = RiskTier.LOW
        assignment_id = str(uuid.uuid4())

        if _is_downgrade(original_tier, new_tier) and not justification.strip():
            raise EthicsError(
                message="Cannot downgrade tier without providing a justification.",
                source="firewall.override_tier",
                error_code=ErrorCode.ETHICS_TIER_BLOCKED,
            )

        direction = "downgrade" if _is_downgrade(original_tier, new_tier) else "escalation"

        record = OverrideRecord(
            override_id=str(uuid.uuid4()),
            assignment_id=assignment_id,
            original_tier=original_tier,
            new_tier=new_tier,
            direction=direction,
            justification=justification,
            user_id=user_id,
        )

        if self._provenance_tracker is not None:
            try:
                entry = self._provenance_tracker.track(
                    action_type="risk_tier_override",
                    params={
                        "decision_id": decision_id,
                        "original_tier": original_tier.value,
                        "new_tier": new_tier.value,
                        "direction": direction,
                        "justification": justification,
                    },
                )
                record.provenance_entry_id = getattr(entry, "action_id", None)
            except Exception:
                logger.warning("Failed to track tier override provenance", exc_info=True)

        logger.info(
            "Tier override recorded",
            decision_id=decision_id,
            direction=direction,
            user_id=user_id,
        )
        return record

    def is_cooling_off_eligible(self, input_hash: str) -> bool:
        """Check if a query has completed its cooling-off period."""
        if self._cool_off_registry is None:
            return True
        return self._cool_off_registry.is_eligible(input_hash)

    def check_data_sovereignty(
        self,
        metadata: dict[str, Any],
        user_id: str = "",
    ) -> SovereigntyVerdict:
        """Evaluate data provenance and enforce sovereignty constraints.

        Args:
            metadata: Structured dict with data origin, consent, and
                export restriction information.
            user_id: Optional user identifier for audit trail.

        Returns:
            A SovereigntyVerdict with origin, restrictions, and export flags.

        Raises:
            EthicsError: If sovereignty constraints block analysis or export.
        """
        src = "firewall.check_data_sovereignty"

        if self._sovereignty_checker is None:
            raise EthicsError(
                message="Data sovereignty checker is not configured.",
                source=src,
                error_code=ErrorCode.CONFIG_MISSING_FIELD,
            )

        verdict = self._sovereignty_checker.check(
            metadata, provenance_tracker=self._provenance_tracker
        )

        self._audit_log.append(
            FirewallAuditEntry(
                entry_id=str(uuid.uuid4()),
                decision_id=verdict.verdict_id,
                category="sovereignty_check",
                action_taken="block" if not verdict.approved else "flag",
                match_type="keyword",
                matched_content=verdict.restriction_summary[:200],
                input_hash=hashlib.sha256(str(metadata).encode()).hexdigest(),
                user_id=user_id,
                metadata={
                    "data_origin": verdict.data_origin.value,
                    "consent_restrictions": [r.value for r in verdict.consent_restrictions],
                    "export_restrictions": [e.value for e in verdict.export_restrictions],
                    "approved": verdict.approved,
                    "requires_human_review": verdict.requires_human_review,
                },
            )
        )

        self._enforce_data_sovereignty(verdict)
        return verdict

    def _enforce_data_sovereignty(
        self,
        verdict: SovereigntyVerdict,
    ) -> None:
        """Enforce sovereignty verdict, raising EthicsError for violations.

        Enforcement matrix:
            NO_ANALYSIS restriction    -> ETHICS_SOVEREIGNTY_VIOLATION
            Indigenous w/o consent     -> ETHICS_INDIGENOUS_RESTRICTION
            ITAR / SOVEREIGN_DATA      -> ETHICS_EXPORT_BLOCKED
            GDPE / HIPAA               -> warning (no block)
        """
        src = "firewall._enforce_data_sovereignty"

        if ConsentRestriction.NO_ANALYSIS in verdict.consent_restrictions:
            raise EthicsError(
                message=(
                    f"Data sovereignty violation: analysis blocked by consent terms. "
                    f"{verdict.restriction_summary}"
                ),
                source=src,
                error_code=ErrorCode.ETHICS_SOVEREIGNTY_VIOLATION,
            )

        blocking_exports = {ExportRestriction.ITAR, ExportRestriction.SOVEREIGN_DATA}
        if set(verdict.export_restrictions) & blocking_exports:
            blocked_names = [e.value for e in verdict.export_restrictions if e in blocking_exports]
            raise EthicsError(
                message=(
                    f"Export restricted: {', '.join(blocked_names)} "
                    f"prevents cross-border data transfer."
                ),
                source=src,
                error_code=ErrorCode.ETHICS_EXPORT_BLOCKED,
            )

        if not verdict.approved:
            raise EthicsError(
                message=f"Data sovereignty violation: {verdict.restriction_summary}",
                source=src,
                error_code=ErrorCode.ETHICS_SOVEREIGNTY_VIOLATION,
            )

        if verdict.requires_human_review:
            raise EthicsError(
                message=(
                    f"Indigenous data restriction: human review required before processing. "
                    f"{verdict.restriction_summary}"
                ),
                source=src,
                error_code=ErrorCode.ETHICS_INDIGENOUS_RESTRICTION,
            )

    def check_indigenous_knowledge(
        self,
        metadata: dict[str, Any],
        user_id: str = "",
    ) -> IndigenousKnowledgeVerdict:
        """Evaluate indigenous knowledge protections for a metadata context.

        Args:
            metadata: Structured dict with cultural restriction markers.
            user_id: Optional user identifier for audit trail.

        Returns:
            An IndigenousKnowledgeVerdict with category, blocking status,
            and CARE principle violations.

        Raises:
            EthicsError: If CARE principle violations block processing.
        """
        src = "firewall.check_indigenous_knowledge"

        if self._indigenous_knowledge_protector is None:
            raise EthicsError(
                message="Indigenous knowledge protector is not configured.",
                source=src,
                error_code=ErrorCode.CONFIG_MISSING_FIELD,
            )

        verdict = self._indigenous_knowledge_protector.check(
            metadata, provenance_tracker=self._provenance_tracker
        )

        self._audit_log.append(
            FirewallAuditEntry(
                entry_id=str(uuid.uuid4()),
                decision_id=verdict.verdict_id,
                category="indigenous_knowledge_check",
                action_taken="block" if verdict.blocked else "flag",
                match_type="keyword",
                matched_content=verdict.restriction_summary[:200],
                input_hash=hashlib.sha256(str(metadata).encode()).hexdigest(),
                user_id=user_id,
                metadata={
                    "category": verdict.category.value,
                    "blocked": verdict.blocked,
                    "care_principles_violated": [p.value for p in verdict.care_principles_violated],
                    "requires_community_consent": verdict.requires_community_consent,
                    "requires_benefit_sharing": verdict.requires_benefit_sharing,
                    "requires_ethics_review": verdict.requires_ethics_review,
                },
            )
        )

        self._enforce_indigenous_knowledge(verdict)
        return verdict

    def _enforce_indigenous_knowledge(
        self,
        verdict: IndigenousKnowledgeVerdict,
    ) -> None:
        """Enforce indigenous knowledge verdict, raising EthicsError for violations.

        Enforcement matrix:
            Blocked (categorically restricted or CARE violation)
                -> ETHICS_CARE_VIOLATION
        """
        src = "firewall._enforce_indigenous_knowledge"

        if not verdict.blocked:
            return

        violated_names = [p.value for p in verdict.care_principles_violated]
        detail = f"CARE violation: {', '.join(violated_names)}" if violated_names else ""
        raise EthicsError(
            message=(
                f"Indigenous knowledge restriction: processing blocked. "
                f"{verdict.restriction_summary} {detail}"
            ).strip(),
            source=src,
            error_code=ErrorCode.ETHICS_CARE_VIOLATION,
        )

    def record_carbon(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        decision_id: str = "",
    ) -> CarbonRecord | None:
        """Estimate and record carbon cost for a completed query.

        Args:
            prompt_tokens: Number of input tokens.
            completion_tokens: Number of output tokens.
            decision_id: The firewall decision ID for linking.

        Returns:
            A CarbonRecord if carbon tracking is enabled, None otherwise.

        Raises:
            EthicsError: If the monthly carbon budget is exceeded.
        """
        if self._carbon_tracker is None:
            return None
        estimate = self._carbon_tracker.estimate(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        return self._carbon_tracker.track_query(
            estimate=estimate,
            decision_id=decision_id,
        )

    def check_grounding(
        self,
        text: str,
        known_sources: list[Source] | None = None,
        user_id: str = "",
    ) -> GroundingVerdict:
        """Validate that generated text is grounded in verifiable sources.

        Delegates to SourceGroundingEngine if configured.

        Args:
            text: Generated text to validate.
            known_sources: Sources from retrieved literature.
            user_id: Optional user identifier for audit trail.

        Returns:
            A GroundingVerdict with approval status and per-claim flags.

        Raises:
            ValidationError: If source grounding fails and unsupported
                claims are not allowed.
        """
        src = "firewall.check_grounding"

        if self._source_grounding is None:
            raise EthicsError(
                message="Source grounding engine is not configured.",
                source=src,
                error_code=ErrorCode.CONFIG_MISSING_FIELD,
            )

        verdict = self._source_grounding.enforce_citations(
            text=text,
            known_sources=known_sources or [],
        )

        self._audit_log.append(
            FirewallAuditEntry(
                entry_id=str(uuid.uuid4()),
                decision_id=uuid.uuid4().hex[:12],
                category="source_grounding",
                action_taken="block" if not verdict.approved else "flag",
                match_type="keyword",
                matched_content=(
                    f"{len(verdict.claims_flagged)} unsupported claims"
                    if verdict.claims_flagged
                    else "all claims supported"
                ),
                input_hash=hashlib.sha256(text.encode()).hexdigest(),
                user_id=user_id,
                metadata={
                    "n_claims_flagged": len(verdict.claims_flagged),
                    "n_citations_verified": len(verdict.citations_verified),
                    "overall_support": verdict.overall_support.value,
                    "approved": verdict.approved,
                },
            )
        )

        if not verdict.approved:
            self._source_grounding.raise_if_unsupported(verdict)

        return verdict

    def _build_decision(
        self,
        scan_level: ScanLevel,
        results: list[DURCResult],
        input_hash: str,
        text_snippet: str,
        tier_assignment: TierAssignment | None = None,
    ) -> EthicsDecision:
        overall = self._default_action
        if results:
            worst = max(results, key=lambda r: _action_priority(r.action_taken))
            overall = worst.action_taken

        return EthicsDecision(
            decision_id=str(uuid.uuid4()),
            scan_timestamp=datetime.now(UTC),
            scan_level=scan_level,
            categories_flagged=results,
            overall_action=overall,
            input_hash=input_hash,
            text_snippet=text_snippet,
            tier_assignment=tier_assignment,
        )

    def _audit_decision(
        self,
        decision: EthicsDecision,
        results: list[DURCResult],
        user_id: str,
    ) -> None:
        tier_meta = {}
        if decision.tier_assignment is not None:
            tier_meta["tier"] = decision.tier_assignment.tier.value
            tier_meta["tier_domain"] = decision.tier_assignment.domain or ""
            tier_meta["tier_confidence"] = decision.tier_assignment.confidence
            tier_meta["tier_match_type"] = decision.tier_assignment.match_type
            tier_meta["tier_governance_action"] = (
                decision.tier_assignment.governance_action.value
                if decision.tier_assignment.governance_action
                else ""
            )
        for r in results:
            entry = FirewallAuditEntry(
                entry_id=str(uuid.uuid4()),
                timestamp=datetime.now(UTC),
                decision_id=decision.decision_id,
                category=r.category.value,
                action_taken=r.action_taken.value,
                match_type=r.match_type.value,
                matched_content=r.matched_text,
                input_hash=decision.input_hash,
                user_id=user_id,
                metadata={
                    "rule_id": r.rule_id,
                    "confidence": r.confidence,
                    "scan_level": decision.scan_level.value,
                    **tier_meta,
                },
            )
            self._audit_log.append(entry, signing_key=self._audit_signing_key)

    def add_rule(self, rule: FirewallRule) -> None:
        self._rules.append(rule)

    def remove_rule(self, rule_id: str) -> bool:
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.id != rule_id]
        return len(self._rules) < before

    def update_rule(self, rule: FirewallRule) -> bool:
        for i, r in enumerate(self._rules):
            if r.id == rule.id:
                self._rules[i] = rule
                return True
        return False


class FirewalledProvider(ModelProvider):
    """A ModelProvider wrapper that intercepts stream_chat with firewall scanning.

    Before LLM inference, the prompt is scanned.  After streaming completes,
    the full response is scanned.  If any rule triggers BLOCK or ESCALATE,
    an EthicsError is raised.  WARN action injects ethical flags into the
    Chunk stream.
    """

    PROVIDER_NAME = "firewalled"

    def __init__(
        self,
        inner: ModelProvider,
        firewall: EthicalFirewall,
        user_id: str = "",
    ) -> None:
        config = getattr(inner, "_config", ProviderConfig())
        super().__init__(config)
        if not self._config.provenance_tracker and firewall._provenance_tracker:
            self._config.provenance_tracker = firewall._provenance_tracker
        self._inner = inner
        self._firewall = firewall
        self._user_id = user_id

    @property
    def inner(self) -> ModelProvider:
        return self._inner

    def _do_stream_chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        provenance_parent_id: str | None = None,
    ) -> AsyncIterator[Chunk]:
        return self._firewalled_stream(
            messages, tools, temperature, max_tokens, provenance_parent_id
        )

    async def _firewalled_stream(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        provenance_parent_id: str | None = None,
    ) -> AsyncIterator[Chunk]:
        # --- Sovereignty / Indigenous Knowledge checks on input ---
        if self._firewall._sovereignty_checker is not None:
            try:
                self._firewall.check_data_sovereignty(
                    {"source": "user_input", "messages": str(len(messages))},
                    user_id=self._user_id,
                )
            except Exception:
                logger.warning("Sovereignty check skipped (no metadata)", exc_info=True)
        if self._firewall._indigenous_knowledge_protector is not None:
            try:
                self._firewall.check_indigenous_knowledge(
                    {"source": "user_input"},
                    user_id=self._user_id,
                )
            except Exception:
                logger.warning("Indigenous knowledge check skipped (no metadata)", exc_info=True)

        # --- Scan prompt ---
        prompt_decision = await self._firewall.scan_prompt(messages, user_id=self._user_id)

        ethical_flag: DURCResult | None = None
        if prompt_decision.categories_flagged:
            worst = max(
                prompt_decision.categories_flagged,
                key=lambda r: _action_priority(r.action_taken),
            )
            if worst.action_taken == FirewallAction.WARN:
                ethical_flag = worst
            # BLOCK/ESCALATE already raised by scan_prompt

        # --- Stream from inner provider ---
        full_response = ""
        last_usage: ProviderMetrics | None = None
        try:
            async for chunk in self._inner.stream_chat(
                messages,
                tools,
                temperature,
                max_tokens,
                provenance_parent_id=provenance_parent_id,
            ):
                if chunk.delta_content:
                    full_response += chunk.delta_content
                if chunk.usage is not None:
                    last_usage = chunk.usage
                # Inject ethical warning into chunk stream
                if ethical_flag is not None and chunk.delta_content:
                    chunk = _inject_ethical_flag(chunk, ethical_flag)
                    ethical_flag = None  # inject once
                yield chunk
        except Exception:
            raise

        # --- Scan response ---
        if full_response:
            try:
                await self._firewall.scan_response(full_response, user_id=self._user_id)
            except EthicsError:
                raise

            # --- Grounding check ---
            if self._firewall._source_grounding is not None:
                try:
                    grounding = self._firewall.check_grounding(
                        full_response,
                        user_id=self._user_id,
                    )
                except Exception:
                    logger.warning("Grounding check failed", exc_info=True)
                    grounding = None
                if grounding is not None and grounding.claims_flagged:
                    yield Chunk(
                        delta_content=(
                            "\n\n[CITATION WARNING: "
                            f"{len(grounding.claims_flagged)} unsupported claim(s) detected. "
                            "Verify citations before final output.]"
                        )
                    )

        # --- Carbon tracking ---
        carbon_record = None
        if last_usage is not None:
            try:
                carbon_record = self._firewall.record_carbon(
                    prompt_tokens=last_usage.prompt_tokens,
                    completion_tokens=last_usage.completion_tokens,
                    decision_id=prompt_decision.decision_id,
                )
            except EthicsError:
                raise

        # --- Carbon cost display ---
        if carbon_record is not None and carbon_record.estimate.co2e_kg > 0:
            eq = carbon_record.estimate.equivalence_text or ""
            yield Chunk(
                delta_content=(
                    f"\n\n[CARBON: ~{carbon_record.estimate.co2e_kg:.3f} kg CO₂e | "
                    f"{carbon_record.monthly_usage_kwh:.2f}/{carbon_record.monthly_budget_kwh} kWh "
                    f"({carbon_record.percentage_used:.1f}%) used this month. "
                    f"{eq}]"
                )
            )

    async def list_models(self) -> list[Any]:  # noqa: ANN401
        return await self._inner.list_models()


def _messages_to_text(messages: list[ChatMessage]) -> str:
    parts: list[str] = []
    for m in messages:
        if isinstance(m.content, str):
            parts.append(f"{m.role}: {m.content}")
        elif isinstance(m.content, list):
            for part in m.content:
                if hasattr(part, "text"):
                    parts.append(f"{m.role}: {part.text}")
    return "\n".join(parts)


def _action_priority(action: FirewallAction) -> int:
    priorities = {
        FirewallAction.FLAG: 0,
        FirewallAction.WARN: 1,
        FirewallAction.BLOCK: 2,
        FirewallAction.ESCALATE: 3,
    }
    return priorities.get(action, 0)


def _is_downgrade(
    original: RiskTier,
    new: RiskTier,
) -> bool:
    """Check if a tier change is a downgrade (lower risk)."""
    order = {RiskTier.HIGH: 0, RiskTier.MEDIUM: 1, RiskTier.LOW: 2}
    return order.get(new, 2) > order.get(original, 0)


def _inject_ethical_flag(chunk: Chunk, result: DURCResult) -> Chunk:
    flag_text = (
        f"\n\n[ETHICAL WARNING: This content matched DURC category "
        f"'{result.category.value}' (confidence: {result.confidence:.2f}). "
        f"Review your output carefully.]"
    )
    return Chunk(
        delta_content=(chunk.delta_content or "") + flag_text,
        finish_reason=chunk.finish_reason,
        usage=chunk.usage,
        tool_calls=chunk.tool_calls,
        provider_metrics=chunk.provider_metrics,
        thinking=chunk.thinking,
        fallback_info=chunk.fallback_info,
    )

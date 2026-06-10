# SPDX-License-Identifier: Apache-2.0

"""Ethics Agent — multi-agent ethical review gate.

Routes hypotheses and research directions through the Phase 3 ethics
infrastructure: EthicalFirewall, TierClassifier, DURCClassifier,
DataSovereigntyChecker, IndigenousKnowledgeProtector, and
CarbonBudgetTracker. Produces a structured EthicsReport and
escalates Tier 1/2 issues via the AgentBus.

Design constraint: the EthicsAgent receives the hypothesis and
experimental design but NOT the literature, preventing citation
authority bias in ethical classification.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from openscire.agent.bus import AgentBus
from openscire.agent.models import (
    AgentMessage,
    EscalatePayload,
    FlagPayload,
    MessageType,
    QueryPayload,
    ResponsePayload,
    ResultPayload,
    TaskPayload,
)
from openscire.constants import RiskTier

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Local models
# ---------------------------------------------------------------------------


class EthicsReport:
    """Structured output from the EthicsAgent pipeline.

    Serialized via ``model_dict()`` for bus compatibility (ResultPayload
    requires a plain dict).
    """

    def __init__(
        self,
        hypothesis: str = "",
        tier_result: dict[str, Any] | None = None,
        durc_flags: list[dict[str, Any]] | None = None,
        sovereignty_verdicts: list[dict[str, Any]] | None = None,
        indigenous_verdicts: list[dict[str, Any]] | None = None,
        carbon_estimate: dict[str, Any] | None = None,
        recommendations: list[str] | None = None,
        overall_action: str = "pass",
        escalated: bool = False,
        firewall_decision: dict[str, Any] | None = None,
    ) -> None:
        self.report_id = str(uuid4())
        self.hypothesis = hypothesis
        self.tier_result = tier_result or {}
        self.durc_flags = durc_flags or []
        self.sovereignty_verdicts = sovereignty_verdicts or []
        self.indigenous_verdicts = indigenous_verdicts or []
        self.carbon_estimate = carbon_estimate or {}
        self.recommendations = recommendations or []
        self.overall_action = overall_action
        self.escalated = escalated
        self.firewall_decision = firewall_decision or {}
        self.timestamp = datetime.now(UTC).isoformat()

    def model_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "hypothesis": self.hypothesis,
            "tier_result": self.tier_result,
            "durc_flags": self.durc_flags,
            "sovereignty_verdicts": self.sovereignty_verdicts,
            "indigenous_verdicts": self.indigenous_verdicts,
            "carbon_estimate": self.carbon_estimate,
            "recommendations": self.recommendations,
            "overall_action": self.overall_action,
            "escalated": self.escalated,
            "firewall_decision": self.firewall_decision,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class EthicsAgent:
    """Ethical review gate for the multi-agent research pipeline.

    Orchestrates the Phase 3 ethics infrastructure against a hypothesis
    or research direction:

    1. Scan via EthicalFirewall (DURC + tier in one call)
    2. Classify risk tier
    3. Flag dual-use patterns
    4. Check data sovereignty + indigenous knowledge
    5. Estimate carbon cost
    6. Build structured report
    7. Escalate Tier 1/2 issues

    LLM-optional: all steps degrade gracefully when injected
    components are unavailable.
    """

    def __init__(
        self,
        agent_id: str = "ethics_review",
        bus: AgentBus | None = None,
        provenance_tracker: Any = None,  # noqa: ANN401
        firewall: Any = None,  # noqa: ANN401
        tier_classifier: Any = None,  # noqa: ANN401
        durc_classifier: Any = None,  # noqa: ANN401
        sovereignty_checker: Any = None,  # noqa: ANN401
        indigenous_protector: Any = None,  # noqa: ANN401
        carbon_tracker: Any = None,  # noqa: ANN401
        audit_log: Any = None,  # noqa: ANN401
        config: dict[str, Any] | None = None,
    ) -> None:
        self._agent_id = agent_id
        self._bus = bus or AgentBus.get_bus("ethics_review")
        self._provenance = provenance_tracker
        self._firewall = firewall
        self._tier_classifier = tier_classifier
        self._durc_classifier = durc_classifier
        self._sovereignty_checker = sovereignty_checker
        self._indigenous_protector = indigenous_protector
        self._carbon_tracker = carbon_tracker
        self._audit_log = audit_log
        self._config = config or {}

        self._sub = self._bus.subscribe(
            agent_id,
            {MessageType.task, MessageType.query},
            self.handle_message,
        )

    # ── Message handling ──────────────────────────────────────────────

    async def handle_message(self, message: AgentMessage) -> None:
        if message.message_type == MessageType.task:
            await self._handle_task(message)
        elif message.message_type == MessageType.query:
            await self._handle_query(message)

    async def _handle_task(self, message: AgentMessage) -> None:
        try:
            payload = TaskPayload.model_validate(message.payload)
            params = dict(payload.parameters or {})

            hypothesis = params.get("hypothesis", "") or payload.description
            data_sources = params.get("data_sources", [])
            prompt_tokens = params.get("prompt_tokens", 500)
            completion_tokens = params.get("completion_tokens", 200)
            model_params = params.get("model_params", 7_000_000_000)

            result = await self.execute_ethics_review(
                hypothesis=hypothesis,
                data_sources=data_sources,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model_params=model_params,
            )
            self._bus.publish(
                AgentMessage(
                    sender=self._agent_id,
                    recipient=message.sender,
                    message_type=MessageType.result,
                    payload=ResultPayload(
                        task_description=payload.description,
                        output=result,
                        success=True,
                    ).model_dump(),
                    thread_id=message.thread_id,
                    provenance_parent_id=message.message_id,
                )
            )
        except Exception as exc:
            logger.exception("Ethics task failed")
            desc = ""
            try:
                desc = TaskPayload.model_validate(message.payload).description
            except Exception:  # noqa: BLE001
                desc = "unknown"
            self._bus.publish(
                AgentMessage(
                    sender=self._agent_id,
                    recipient=message.sender or "supervisor",
                    message_type=MessageType.result,
                    payload=ResultPayload(
                        task_description=desc,
                        output={},
                        success=False,
                        error=str(exc),
                    ).model_dump(),
                    thread_id=message.thread_id,
                    provenance_parent_id=message.message_id,
                )
            )

    async def _handle_query(self, message: AgentMessage) -> None:
        payload = QueryPayload.model_validate(message.payload)
        self._bus.publish(
            AgentMessage(
                sender=self._agent_id,
                recipient=message.sender,
                message_type=MessageType.response,
                payload=ResponsePayload(
                    content=f"EthicsAgent received: {payload.question}",
                    confidence=0.5,
                    citations=[],
                ).model_dump(),
                thread_id=message.thread_id,
            )
        )

    # ── Pipeline ──────────────────────────────────────────────────────

    async def execute_ethics_review(
        self,
        hypothesis: str,
        data_sources: list[dict[str, Any]] | None = None,
        prompt_tokens: int = 500,
        completion_tokens: int = 200,
        model_params: int = 7_000_000_000,
    ) -> dict[str, Any]:
        """Run the full ethics review pipeline.

        Returns a serializable dict suitable for ``ResultPayload.output``.
        """
        if not hypothesis:
            raise ValueError("hypothesis is required for ethics review")

        data_sources = data_sources or []

        # 1. Firewall scan (DURC + tier combined)
        firewall_decision = self._scan_firewall(hypothesis)

        # 2. Tier classification (standalone, for report)
        tier_result = self._classify_tier(hypothesis)

        # 3. DURC flagging (standalone, for report)
        durc_flags = await self._flag_dual_use(hypothesis)

        # 4. Sovereignty + indigenous checks per data source
        sovereignty_verdicts, indigenous_verdicts = self._check_sovereignty(
            data_sources,
        )

        # 5. Carbon estimation
        carbon_estimate = self._estimate_carbon(
            prompt_tokens,
            completion_tokens,
            model_params,
        )

        # 6. Build report
        report = self._build_report(
            hypothesis=hypothesis,
            firewall_decision=firewall_decision,
            tier_result=tier_result,
            durc_flags=durc_flags,
            sovereignty_verdicts=sovereignty_verdicts,
            indigenous_verdicts=indigenous_verdicts,
            carbon_estimate=carbon_estimate,
        )

        # 7. Escalate if Tier 1/2
        self._escalate_if_needed(report)

        return report.model_dict()

    # ── Pipeline steps ────────────────────────────────────────────────

    def _scan_firewall(self, hypothesis: str) -> dict[str, Any]:
        """Step 1: Scan via EthicalFirewall.

        Catches EthicsError (BLOCK/ESCALATE/tier governance) and maps
        it to a report-safe EthicsDecision dict.
        """
        if self._firewall is None:
            return {
                "overall_action": "flag",
                "categories_flagged": [],
                "governance_blocked": False,
            }

        try:
            from openscire.provider.models import ChatMessage

            messages = [ChatMessage(role="user", content=hypothesis)]
            decision = self._firewall.scan_prompt(
                messages,
                user_id="ethics_agent",
            )
            return {
                "decision_id": decision.decision_id,
                "overall_action": decision.overall_action.value
                if hasattr(decision.overall_action, "value")
                else str(decision.overall_action),
                "categories_flagged": [
                    {
                        "category": c.category.value
                        if hasattr(c.category, "value")
                        else str(c.category),
                        "confidence": c.confidence,
                        "action_taken": c.action_taken.value
                        if hasattr(c.action_taken, "value")
                        else str(c.action_taken),
                    }
                    for c in decision.categories_flagged
                ],
                "governance_blocked": decision.governance_blocked,
            }
        except Exception as exc:
            # Catch EthicsError (and any other firewall exception) and
            # map to a report-safe dict instead of propagating.
            logger.warning("EthicsError from firewall: %s", exc)
            error_code = getattr(exc, "error_code", "")
            return {
                "overall_action": "block",
                "categories_flagged": [],
                "governance_blocked": True,
                "error": str(exc),
                "error_code": error_code,
            }

    def _classify_tier(self, hypothesis: str) -> dict[str, Any]:
        """Step 2: Classify the research context into a risk tier."""
        if self._tier_classifier is None:
            return {
                "assigned_tier": RiskTier.LOW.value,
                "domain": "unknown",
                "confidence": 0.0,
                "governance_action": "standard",
            }

        try:
            result = self._tier_classifier.classify(
                hypothesis,
                self._provenance,
            )
            return {
                "assigned_tier": result.assigned_tier.value
                if hasattr(result.assigned_tier, "value")
                else str(result.assigned_tier),
                "domain": result.domain,
                "domain_label": result.domain_label,
                "confidence": result.confidence,
                "governance_action": result.governance_action.value
                if hasattr(result.governance_action, "value")
                else str(result.governance_action),
            }
        except Exception:
            logger.exception("Tier classification failed")
            return {
                "assigned_tier": RiskTier.LOW.value,
                "domain": "classification_error",
                "confidence": 0.0,
                "governance_action": "standard",
            }

    async def _flag_dual_use(self, hypothesis: str) -> list[dict[str, Any]]:
        """Step 3: Scan for DURC patterns."""
        if self._durc_classifier is None:
            return []

        try:
            from openscire.ethics.durc import build_default_rules

            rules = build_default_rules()
            results = await self._durc_classifier.scan(
                hypothesis,
                rules,
                "warn",
            )
            return [
                {
                    "category": r.category.value
                    if hasattr(r.category, "value")
                    else str(r.category),
                    "confidence": r.confidence,
                    "action_taken": r.action_taken.value
                    if hasattr(r.action_taken, "value")
                    else str(r.action_taken),
                    "triggered": r.triggered,
                }
                for r in results
                if r.triggered
            ]
        except Exception:
            logger.exception("DURC scanning failed")
            return []

    def _check_sovereignty(
        self,
        data_sources: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Step 4: Check data sovereignty and indigenous knowledge."""
        sovereignty_verdicts: list[dict[str, Any]] = []
        indigenous_verdicts: list[dict[str, Any]] = []

        for source in data_sources:
            if self._sovereignty_checker is not None:
                try:
                    verdict = self._sovereignty_checker.check(
                        source,
                        self._provenance,
                    )
                    sovereignty_verdicts.append(
                        {
                            "data_origin": verdict.data_origin.value
                            if hasattr(verdict.data_origin, "value")
                            else str(verdict.data_origin),
                            "approved": verdict.approved,
                            "requires_human_review": verdict.requires_human_review,
                            "consent_restrictions": [
                                r.value if hasattr(r, "value") else str(r)
                                for r in verdict.consent_restrictions
                            ],
                            "export_restrictions": [
                                r.value if hasattr(r, "value") else str(r)
                                for r in verdict.export_restrictions
                            ],
                        }
                    )
                except Exception:
                    logger.exception("Sovereignty check failed")
                    sovereignty_verdicts.append(
                        {
                            "data_origin": "check_error",
                            "approved": False,
                            "requires_human_review": True,
                        }
                    )

            if self._indigenous_protector is not None:
                try:
                    ikv = self._indigenous_protector.check(
                        source,
                        self._provenance,
                    )
                    indigenous_verdicts.append(
                        {
                            "category": ikv.category.value
                            if hasattr(ikv.category, "value")
                            else str(ikv.category),
                            "blocked": ikv.blocked,
                            "care_principles_violated": [
                                p.value if hasattr(p, "value") else str(p)
                                for p in ikv.care_principles_violated
                            ],
                            "requires_community_consent": ikv.requires_community_consent,
                            "requires_benefit_sharing": ikv.requires_benefit_sharing,
                        }
                    )
                except Exception:
                    logger.exception("Indigenous knowledge check failed")
                    indigenous_verdicts.append(
                        {
                            "category": "check_error",
                            "blocked": False,
                        }
                    )

        return sovereignty_verdicts, indigenous_verdicts

    def _estimate_carbon(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model_params: int,
    ) -> dict[str, Any]:
        """Step 5: Estimate carbon cost of proposed work."""
        if self._carbon_tracker is None:
            return {
                "flops": 0.0,
                "kwh": 0.0,
                "co2e_kg": 0.0,
                "equivalence_text": "",
            }

        try:
            estimate = self._carbon_tracker.estimate(
                prompt_tokens,
                completion_tokens,
                model_params,
            )
            return {
                "flops": estimate.flops,
                "kwh": estimate.kwh,
                "co2e_kg": estimate.co2e_kg,
                "equivalence_text": estimate.equivalence_text,
            }
        except Exception:
            logger.exception("Carbon estimation failed")
            return {
                "flops": 0.0,
                "kwh": 0.0,
                "co2e_kg": 0.0,
                "equivalence_text": "estimation_failed",
            }

    def _build_report(
        self,
        hypothesis: str,
        firewall_decision: dict[str, Any],
        tier_result: dict[str, Any],
        durc_flags: list[dict[str, Any]],
        sovereignty_verdicts: list[dict[str, Any]],
        indigenous_verdicts: list[dict[str, Any]],
        carbon_estimate: dict[str, Any],
    ) -> EthicsReport:
        """Step 6: Assemble the EthicsReport with recommendations."""
        recommendations: list[str] = []
        overall_action = "pass"

        # Tier-based recommendations
        tier = tier_result.get("assigned_tier", RiskTier.LOW.value)
        if tier == RiskTier.HIGH.value:
            recommendations.append(
                "Tier 1 (HIGH RISK): Mandatory 24-hour cooling-off period required.",
            )
            overall_action = "escalate"
        elif tier == RiskTier.MEDIUM.value:
            recommendations.append(
                "Tier 2 (MEDIUM RISK): Human checkpoint required before proceeding.",
            )
            overall_action = "flag"

        # DURC recommendations
        if durc_flags:
            recommendations.append(
                f"DURC concerns detected in {len(durc_flags)} category(ies). Review required.",
            )
            if overall_action != "escalate":
                overall_action = "flag"

        # Sovereignty recommendations
        blocked_sources = [v for v in sovereignty_verdicts if not v.get("approved", True)]
        if blocked_sources:
            recommendations.append(
                f"{len(blocked_sources)} data source(s) failed sovereignty check.",
            )
            overall_action = "flag"

        # Indigenous knowledge recommendations
        blocked_indigenous = [v for v in indigenous_verdicts if v.get("blocked", False)]
        if blocked_indigenous:
            recommendations.append(
                f"{len(blocked_indigenous)} source(s) blocked by indigenous knowledge protection.",
            )
            overall_action = "escalate"

        # Carbon recommendations
        if carbon_estimate.get("kwh", 0) > 0:
            recommendations.append(
                f"Estimated carbon cost: {carbon_estimate['co2e_kg']:.4f} kg CO2e "
                f"({carbon_estimate['kwh']:.4f} kWh).",
            )

        # Firewall error
        if firewall_decision.get("error"):
            recommendations.append(
                f"Firewall reported: {firewall_decision['error']}",
            )

        return EthicsReport(
            hypothesis=hypothesis,
            tier_result=tier_result,
            durc_flags=durc_flags,
            sovereignty_verdicts=sovereignty_verdicts,
            indigenous_verdicts=indigenous_verdicts,
            carbon_estimate=carbon_estimate,
            recommendations=recommendations,
            overall_action=overall_action,
            firewall_decision=firewall_decision,
        )

    def _escalate_if_needed(self, report: EthicsReport) -> None:
        """Step 7: Publish FlagPayload + EscalatePayload for Tier 1/2."""
        tier = report.tier_result.get("assigned_tier", RiskTier.LOW.value)
        governance = report.tier_result.get(
            "governance_action",
            "standard",
        )

        if tier == RiskTier.HIGH.value or governance == "cooling_off":
            severity = "critical"
        elif tier == RiskTier.MEDIUM.value or governance == "human_checkpoint":
            severity = "high"
        else:
            # Tier 3 — no escalation
            return

        report.escalated = True

        # Flag
        self._bus.publish(
            AgentMessage(
                sender=self._agent_id,
                recipient="supervisor",
                message_type=MessageType.flag,
                payload=FlagPayload(
                    reason=f"Ethics {tier} risk tier",
                    severity=severity,
                    target_message_id=report.report_id,
                ).model_dump(),
            )
        )

        # Escalate
        self._bus.publish(
            AgentMessage(
                sender=self._agent_id,
                recipient="supervisor",
                message_type=MessageType.escalate,
                payload=EscalatePayload(
                    issue=f"Tier {tier} ethics escalation",
                    target_agent="human",
                    context=report.model_dict(),
                ).model_dump(),
            )
        )

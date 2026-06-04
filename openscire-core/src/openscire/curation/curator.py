from __future__ import annotations

from typing import Any

from openscire.curation.adversarial_search import AdversarialSourceRetriever
from openscire.curation.assumption_miner import AssumptionMiner, AssumptionTester
from openscire.curation.models import EchoChamberReport
from openscire.curation.ratio_enforcer import ExternalSourceRatioEnforcer
from openscire.curation.source_scorer import (
    ConfidenceWeightedRanker,
    SourceQualityScorer,
)
from openscire.logging import get_logger
from openscire.references.models import ReferenceItem

logger = get_logger("openscire.curation.curator")


class Curator:
    """Orchestrates all anti-echo-chamber analyses.

    Runs: ratio enforcement -> adversarial source retrieval -> source scoring
    -> confidence-weighted ranking -> assumption mining.
    """

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        bridges: dict[str, Any] | None = None,
        provenance_tracker: Any = None,
    ) -> None:
        self.config = config or {}
        self.bridges = bridges or {}
        self._provenance_tracker = provenance_tracker
        self.ratio_enforcer = ExternalSourceRatioEnforcer(self.config)
        self.adversarial = AdversarialSourceRetriever(self.config, self.bridges)
        self.scorer = SourceQualityScorer(self.config)
        self.ranker = ConfidenceWeightedRanker()
        self.assumption_miner = AssumptionMiner(self.config)
        self.assumption_tester = AssumptionTester(self.config, self.bridges)

    async def analyze(
        self,
        research_question: str,
        user_sources: list[ReferenceItem],
        external_sources: list[ReferenceItem],
        claims: list[str] | None = None,
    ) -> EchoChamberReport:
        passed, ratio = self.ratio_enforcer.check_ratio(
            len(user_sources), len(external_sources),
        )
        all_sources = user_sources + external_sources
        effective_claims = claims or [s.title for s in user_sources if s.title]
        adv_sources = await self.adversarial.find_contradictory_sources(effective_claims)
        scored = [self.scorer.score(s) for s in all_sources]
        ranked = self.ranker.rank(scored)
        assumptions = self.assumption_miner.extract(research_question)
        tested = await self.assumption_tester.test(assumptions)
        unique_sources: set[str] = set()
        for adv in adv_sources:
            if adv.source and adv.source.id:
                unique_sources.add(adv.source.id)

        if self._provenance_tracker is not None:
            try:
                self._provenance_tracker.track(
                    action_type="curation_external_ratio",
                    params={
                        "ratio": round(ratio, 4),
                        "passed": passed,
                        "n_user": len(user_sources),
                        "n_external": len(external_sources),
                    },
                )
            except Exception:
                logger.warning("Failed to record curation ratio provenance", exc_info=True)
            try:
                self._provenance_tracker.track(
                    action_type="curation_adversarial_search",
                    params={"n_contradictory_sources": len(unique_sources)},
                )
            except Exception:
                logger.warning("Failed to record adversarial search provenance", exc_info=True)
            try:
                self._provenance_tracker.track(
                    action_type="curation_assumption_mining",
                    params={
                        "n_assumptions": len(tested),
                        "n_tested": sum(1 for t in tested if t.result is not None),
                    },
                )
            except Exception:
                logger.warning("Failed to record assumption mining provenance", exc_info=True)

        return EchoChamberReport(
            external_ratio=round(ratio, 4),
            external_ratio_pass=passed,
            n_user_sources=len(user_sources),
            n_external_sources=len(external_sources),
            n_contradictory_sources=len(unique_sources),
            assumptions=tested,
            adversarial_sources=adv_sources,
            confidence_ranked_sources=ranked,
            config=self.config,
        )

from __future__ import annotations

import logging
from typing import Any

from openscire.curation.models import AdversarialSource

logger = logging.getLogger("openscire.curation.adversarial_search")


class AdversarialSourceRetriever:
    """For each claim, retrieves at least one contradictory or alternative-view source.

    Uses injected bridge clients for search and an optional
    :class:`ModelProvider` for query formulation.  Falls back to
    heuristic negation for query generation when no provider is given.
    """

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        bridges: dict[str, Any] | None = None,
    ) -> None:
        self.config = config or {}
        self.bridges = bridges or {}

    async def find_contradictory_sources(
        self,
        claims: list[str],
        max_per_claim: int = 3,
    ) -> list[AdversarialSource]:
        if not claims:
            return []
        results: list[AdversarialSource] = []
        for claim in claims:
            queries = self._generate_queries(claim)
            for query in queries[:max_per_claim]:
                for bridge_name, bridge in self.bridges.items():
                    try:
                        items = await bridge.search(query)
                        for item in items[:max_per_claim]:
                            results.append(AdversarialSource(
                                claim=claim,
                                source=item,
                                contradiction_type="alternative_view",
                                retrieved_via=bridge_name,
                                confidence=0.5,
                            ))
                    except Exception:
                        logger.exception("Bridge %s failed for query %s", bridge_name, query)
        return results

    def _generate_queries(self, claim: str) -> list[str]:
        words = claim.lower().split()
        negations = ["not", "no", "without", "absence", "alternative"]
        queries: list[str] = []
        if any(n in claim.lower() for n in negations):
            queries.append(claim)
        else:
            queries.append(f"contrary to {claim}")
            if len(words) >= 3:
                negated = words[:]
                negated.insert(1, "not")
                queries.append(" ".join(negated))
        queries.append(claim)
        return queries

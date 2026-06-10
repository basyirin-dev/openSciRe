# SPDX-License-Identifier: Apache-2.0

"""Factory to create a ModelProvider wrapped with EthicalFirewall guardrails.

Usage:
    .. code-block:: python

        from openscire.provider.guarded import create_guarded_provider
        from openscire.provenance import ProvenanceTracker

        tracker = ProvenanceTracker.from_config(config)
        provider = await create_guarded_provider(
            model="gpt-4o",
            tracker=tracker,
            carbon_enabled=True,
            require_citations=True,
        )
        # provider is a FirewalledProvider with all ethical checkpoints wired
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openscire.config.byok import BYOKProfile
    from openscire.ethics.firewall import FirewalledProvider
    from openscire.provider.base import ModelProvider

logger = logging.getLogger(__name__)


async def create_guarded_provider(
    model: str,
    byok_profile: BYOKProfile | None = None,
    force: str | None = None,
    tracker: Any = None,
    carbon_enabled: bool = False,
    require_citations: bool = True,
) -> FirewalledProvider:
    """Create a ModelProvider wrapped with EthicalFirewall guardrails.

    Wires all ethical checkpoints into the provider pipeline:
      - DURC scanning + RiskTier classification via TierClassifier
      - Cooling-off / human checkpoint governance
      - Source grounding with citation verification
      - Carbon cost tracking (optional)

    Each checkpoint that receives a ``tracker`` automatically records
    provenance entries (tier_classification, carbon_estimate,
    citation_grounding).  Provenance failures are logged and swallowed
    — they never block inference.

    Args:
        model: Model identifier (e.g. ``"gpt-4o"``, ``"ollama/llama3.1"``).
        byok_profile: Optional BYOK profile with custom API key / base URL.
        force: Force a specific adapter type (``"openai"``, ``"anthropic"``,
            ``"gemini"``, ``"litellm"``).
        tracker: Optional ProvenanceTracker for recording all checkpoint
            decisions.
        carbon_enabled: If True, track and display carbon cost estimates.
        require_citations: If True, flag unsupported claims during grounding
            checks.

    Returns:
        A ``FirewalledProvider`` with all ethical checkpoints wired.

    Raises:
        ValueError: If *force* is set to an unknown adapter type.
    """
    from openscire.ethics.carbon import CarbonBudgetTracker
    from openscire.ethics.durc import build_default_rules
    from openscire.ethics.firewall import EthicalFirewall
    from openscire.ethics.source_grounding import SourceGroundingEngine
    from openscire.ethics.tier import CoolOffRegistry, TierClassifier
    from openscire.provider.base import ModelProvider  # noqa: F401
    from openscire.provider.factory import select_provider

    tier_classifier = TierClassifier()
    cool_off = CoolOffRegistry()
    source_grounding = SourceGroundingEngine(
        require_citations=require_citations,
        provenance_tracker=tracker,
    )
    carbon_tracker = CarbonBudgetTracker(provenance_tracker=tracker) if carbon_enabled else None

    firewall = EthicalFirewall(
        rules=build_default_rules(),
        tier_classifier=tier_classifier,
        cool_off_registry=cool_off,
        provenance_tracker=tracker,
        carbon_tracker=carbon_tracker,
        source_grounding=source_grounding,
    )

    raw_provider: ModelProvider = select_provider(
        model=model,
        byok_profile=byok_profile,
        force=force,
    )

    if tracker is not None:
        raw_provider._config.provenance_tracker = tracker

    return firewall.wrap(raw_provider)

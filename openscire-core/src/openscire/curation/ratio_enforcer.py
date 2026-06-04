from __future__ import annotations

from typing import Any


class ExternalSourceRatioEnforcer:
    """Ensures a minimum ratio of external-to-user-provided sources.

    Config key: ``min_external_ratio`` (default 0.5).
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        self.min_external_ratio = config.get("min_external_ratio", 0.5)

    def check_ratio(
        self,
        user_provided_count: int,
        external_count: int,
    ) -> tuple[bool, float]:
        total = user_provided_count + external_count
        if total == 0:
            return True, 0.0
        ratio = external_count / total
        return ratio >= self.min_external_ratio, ratio

    def get_insufficient_sources(
        self,
        user_sources: list[Any],
        external_sources: list[Any],
    ) -> list[Any]:
        total = len(user_sources) + len(external_sources)
        if total == 0:
            return []
        ratio = len(external_sources) / total
        if ratio >= self.min_external_ratio:
            return []
        needed_ratio = self.min_external_ratio - ratio
        needed = int(needed_ratio * total) + 1
        return user_sources[:needed]

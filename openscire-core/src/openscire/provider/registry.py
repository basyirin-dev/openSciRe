# SPDX-License-Identifier: Apache-2.0

"""Central model registry mapping (provider, model) to ModelInfo with
cached capabilities.

Provides a lazy-populated singleton that fills as providers call
``list_models()`` and a query interface for finding models by capability
or provider.
"""

from __future__ import annotations

from openscire.provider.base import ModelProvider
from openscire.provider.capabilities import CapabilityProbe
from openscire.provider.models import ModelCapabilities, ModelInfo


class ModelRegistry:
    """Central registry mapping (provider, model) to ModelInfo.

    Capabilities are detected lazily on first ``get()`` call if the
    ``ModelInfo`` registered doesn't already carry them.

    Args:
        probe: Optional ``CapabilityProbe`` instance. Creates a default
            one if not provided.
    """

    def __init__(self, probe: CapabilityProbe | None = None) -> None:
        self._entries: dict[tuple[str, str], ModelInfo] = {}
        self._probe = probe or CapabilityProbe()

    async def get(
        self,
        provider_name: str,
        model_id: str,
        provider_instance: ModelProvider | None = None,
    ) -> ModelInfo | None:
        """Get model info with lazy capability detection.

        If the cached ``ModelInfo`` has default (all-False) capabilities,
        this triggers capability detection via the probe. If
        ``provider_instance`` is given, its ``get_capabilities()`` is
        used as the source of truth instead of the probe.

        Args:
            provider_name: Provider name.
            model_id: Model identifier.
            provider_instance: Optional provider instance for live
                capability resolution.

        Returns:
            ``ModelInfo`` with resolved capabilities, or ``None`` if not
            found and no provider instance given.
        """
        key = (provider_name, model_id)
        entry = self._entries.get(key)
        if entry is not None:
            if self._needs_capability_resolution(entry.capabilities):
                caps = await self._resolve_capabilities(
                    provider_name,
                    model_id,
                    provider_instance,
                )
                if caps is not None:
                    entry.capabilities = caps
                    self._entries[key] = entry
            return entry

        if provider_instance is not None:
            caps = await self._resolve_capabilities(
                provider_name,
                model_id,
                provider_instance,
            )
            info = ModelInfo(
                id=model_id,
                name=model_id,
                provider=provider_name,
                capabilities=caps,
            )
            self._entries[key] = info
            return info

        return None

    def register(self, provider_name: str, model_id: str, info: ModelInfo) -> None:
        """Register or update a model entry."""
        self._entries[(provider_name, model_id)] = info

    def register_many(self, provider_name: str, models: list[ModelInfo]) -> None:
        """Batch register from a ``list_models()`` call."""
        for m in models:
            self.register(provider_name, m.id, m)

    def find(
        self,
        *,
        capability: str | None = None,
        provider: str | None = None,
    ) -> list[ModelInfo]:
        """Query models by capability or provider.

        Args:
            capability: Capability flag to filter by (e.g. ``"vision"``,
                ``"tool_use"``, ``"streaming"``, ``"function_calling"``).
            provider: Provider name to filter by.

        Returns:
            Matching ``ModelInfo`` list.
        """
        results: list[ModelInfo] = []
        for entry in self._entries.values():
            if provider is not None and entry.provider != provider:
                continue
            if capability is not None:
                val = getattr(entry.capabilities, capability, None)
                if not val:
                    continue
            results.append(entry)
        return results

    def clear(self) -> None:
        """Clear all entries and probe cache."""
        self._entries.clear()
        self._probe.invalidate()

    def _needs_capability_resolution(self, caps: ModelCapabilities) -> bool:
        return not any([caps.tool_use, caps.vision, caps.function_calling])

    async def _resolve_capabilities(
        self,
        provider_name: str,
        model_id: str,
        provider_instance: ModelProvider | None,
    ) -> ModelCapabilities:
        if provider_instance is not None:
            try:
                return provider_instance.get_capabilities(model_id)
            except Exception:
                pass
        return await self._probe.discover(provider_name, model_id)


_global_registry: ModelRegistry | None = None


def get_global_registry() -> ModelRegistry:
    """Return the singleton global model registry.

    Created lazily on first call. Populated as providers call
    ``list_models()`` across the application.

    Returns:
        The global ``ModelRegistry`` instance.
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ModelRegistry()
    return _global_registry

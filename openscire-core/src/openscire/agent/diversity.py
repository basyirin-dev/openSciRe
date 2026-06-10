# SPDX-License-Identifier: Apache-2.0

"""Agent diversity management for heterogeneous multi-agent research.

Ensures agents use distinct model providers, temperatures, and objective
functions to avoid groupthink and enable robust tournament validation.
"""

from __future__ import annotations

from collections.abc import Sequence

from openscire.models.philosophy import (
    AgentDiversityConfig,
    AgentModelProvider,
    AgentObjective,
)


class DiversityAssignmentError(ValueError):
    """Raised when diversity configuration cannot be assigned."""


class DiversityManager:
    """Assigns distinct model configurations to agent roles.

    Guarantees:
        - No two agents share identical (provider, model, temperature) tuples.
        - Each agent receives a distinct objective function when possible.
        - Falls back gracefully when fewer distinct configs than roles exist.

    Args:
        config: AgentDiversityConfig specifying providers, temperatures, etc.
    """

    def __init__(self, config: AgentDiversityConfig | None = None) -> None:
        self._config = config or AgentDiversityConfig()

    @property
    def config(self) -> AgentDiversityConfig:
        return self._config

    def assign_configs(
        self,
        roles: Sequence[str],
    ) -> dict[str, AgentModelProvider]:
        """Assign a distinct AgentModelProvider to each role.

        The assignment algorithm:
        1. Match roles to explicitly configured providers by role name.
        2. Fill remaining roles with temperature defaults and cycling objectives.
        3. Validate that no two assignments share identical (provider, model, temperature).

        Returns:
            Mapping of role -> AgentModelProvider.

        Raises:
            DiversityAssignmentError: If duplicate configs cannot be avoided.
        """
        assignments: dict[str, AgentModelProvider] = {}
        used_tuples: set[tuple[str, str, float | None]] = set()
        used_objectives: set[str] = set()

        explicit_providers = {p.role: p for p in self._config.providers if p.role}

        objectives = list(AgentObjective)
        obj_index = 0

        for role in roles:
            if role in explicit_providers:
                base = explicit_providers[role]
                if base.temperature is None:
                    base = base.model_copy(update={"temperature": self._temperature_for_role(role)})
            else:
                temp = self._temperature_for_role(role)
                base = AgentModelProvider(
                    role=role,
                    provider="ollama",
                    model_name="llama3.1",
                    temperature=temp,
                    objective_function=AgentObjective.balanced.value,
                )

            config = self._resolve_config(base, used_tuples, used_objectives, objectives, obj_index)
            obj_index = (obj_index + 1) % len(objectives)
            assignments[role] = config

        return assignments

    def validate_heterogeneous(
        self,
        assignments: dict[str, AgentModelProvider],
    ) -> None:
        """Verify no two agents share identical configuration.

        Raises:
            DiversityAssignmentError: If duplicate configurations exist.
        """
        seen: dict[tuple[str, str, float | None], list[str]] = {}
        for role, cfg in assignments.items():
            key = (cfg.provider, cfg.model_name, cfg.temperature)
            if key in seen:
                seen[key].append(role)
            else:
                seen[key] = [role]

        duplicates = {k: v for k, v in seen.items() if len(v) > 1}
        if duplicates:
            msg = "; ".join(
                f"{prov}/{model}@{temp} shared by {', '.join(roles)}"
                for (prov, model, temp), roles in duplicates.items()
            )
            raise DiversityAssignmentError(f"Duplicate agent configurations detected: {msg}")

    def validate_objective_diversity(
        self,
        assignments: dict[str, AgentModelProvider],
    ) -> list[str]:
        """Check objective function diversity across roles.

        Returns:
            List of warnings for roles with duplicated objectives.
        """
        warnings: list[str] = []
        obj_counts: dict[str, list[str]] = {}
        for role, cfg in assignments.items():
            obj = cfg.objective_function or AgentObjective.balanced.value
            if obj in obj_counts:
                obj_counts[obj].append(role)
            else:
                obj_counts[obj] = [role]

        for obj, roles in obj_counts.items():
            if len(roles) > 1:
                warnings.append(f"Objective '{obj}' shared by {', '.join(roles)}")
        return warnings

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    _FALLBACK_TEMPERATURES: list[float] = [0.7, 0.9, 0.3, 0.1, 1.5, 1.2, 0.05, 0.5]
    _FALLBACK_MODELS: list[str] = [
        "llama3.1",
        "llama3.2",
        "mistral",
        "mixtral",
        "gemma2",
        "phi3",
        "qwen2",
        "deepseek",
    ]

    def _resolve_config(
        self,
        base: AgentModelProvider,
        used_tuples: set[tuple[str, str, float | None]],
        used_objectives: set[str],
        objectives: list[AgentObjective],
        obj_index: int,
    ) -> AgentModelProvider:
        """Resolve a config, avoiding duplicates in used_tuples.

        Assigns distinct objective functions by cycling through available
        objectives. If the base config would duplicate an existing
        (provider, model, temp), iterates through fallback strategies:
        alter temperature, then alter model, then alter provider.
        """
        obj_value = objectives[obj_index % len(objectives)].value

        key = (base.provider, base.model_name, base.temperature)
        if key not in used_tuples:
            result = base.model_copy(update={"objective_function": obj_value})
            used_tuples.add(key)
            used_objectives.add(obj_value)
            return result

        for variant in self._config.providers:
            vkey = (variant.provider, variant.model_name, variant.temperature)
            if vkey not in used_tuples and variant.role != base.role:
                result = variant.model_copy(
                    update={"role": base.role, "objective_function": obj_value}
                )
                used_tuples.add(vkey)
                used_objectives.add(obj_value)
                return result

        for alt_temp in self._FALLBACK_TEMPERATURES:
            fallback = base.model_copy(
                update={"temperature": alt_temp, "objective_function": obj_value}
            )
            fkey = (fallback.provider, fallback.model_name, fallback.temperature)
            if fkey not in used_tuples:
                used_tuples.add(fkey)
                used_objectives.add(obj_value)
                return fallback

        for alt_model in self._FALLBACK_MODELS:
            for alt_temp in self._FALLBACK_TEMPERATURES:
                fallback = base.model_copy(
                    update={
                        "model_name": alt_model,
                        "temperature": alt_temp,
                        "objective_function": obj_value,
                    }
                )
                fkey = (fallback.provider, fallback.model_name, fallback.temperature)
                if fkey not in used_tuples:
                    used_tuples.add(fkey)
                    used_objectives.add(obj_value)
                    return fallback

        for alt_provider in ("openai", "anthropic", "google", "ollama"):
            if alt_provider == base.provider:
                continue
            for alt_model in self._FALLBACK_MODELS:
                for alt_temp in self._FALLBACK_TEMPERATURES:
                    fallback = base.model_copy(
                        update={
                            "provider": alt_provider,
                            "model_name": alt_model,
                            "temperature": alt_temp,
                            "objective_function": obj_value,
                        }
                    )
                    fkey = (fallback.provider, fallback.model_name, fallback.temperature)
                    if fkey not in used_tuples:
                        used_tuples.add(fkey)
                        used_objectives.add(obj_value)
                        return fallback

        raise DiversityAssignmentError(
            f"Cannot assign unique config for role '{base.role}' "
            f"with {len(used_tuples)} already assigned"
        )

    def _temperature_for_role(self, role: str) -> float:
        temp_map = {
            "literature_review": self._config.temperature_defaults.literature_review,
            "hypothesis_generation": self._config.temperature_defaults.hypothesis_generation,
            "falsification": self._config.temperature_defaults.falsification,
            "ethics_review": self._config.temperature_defaults.ethics,
            "ethics": self._config.temperature_defaults.ethics,
            "sandbox_execution": self._config.temperature_defaults.sandbox,
        }
        return temp_map.get(role, 0.5)

# SPDX-License-Identifier: Apache-2.0

"""Unit tests for agent diversity management (Task 6.8)."""

from __future__ import annotations

import pytest
from openscire.agent.diversity import DiversityAssignmentError, DiversityManager
from openscire.models.philosophy import (
    AgentDiversityConfig,
    AgentModelProvider,
    AgentObjective,
    AgentTemperatureConfig,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def default_roles() -> list[str]:
    return ["literature_review", "falsification", "ethics_review"]


@pytest.fixture
def explicit_config() -> AgentDiversityConfig:
    return AgentDiversityConfig(
        providers=[
            AgentModelProvider(
                role="literature_review",
                provider="ollama",
                model_name="llama3.1",
                temperature=0.2,
                objective_function=AgentObjective.balanced.value,
            ),
            AgentModelProvider(
                role="falsification",
                provider="openai",
                model_name="gpt-4o",
                temperature=0.8,
                objective_function=AgentObjective.skeptical.value,
            ),
            AgentModelProvider(
                role="ethics_review",
                provider="anthropic",
                model_name="claude-3",
                temperature=0.3,
                objective_function=AgentObjective.supportive.value,
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Test: DiversityManager construction
# ---------------------------------------------------------------------------


class TestDiversityManagerConstruction:
    def test_default_config(self) -> None:
        dm = DiversityManager()
        assert dm.config is not None
        assert dm.config.serendipity_level == 0.4
        assert dm.config.enable_contradiction_driven_exploration is True
        assert len(dm.config.providers) == 3

    def test_explicit_config(self, explicit_config: AgentDiversityConfig) -> None:
        dm = DiversityManager(config=explicit_config)
        assert dm.config is explicit_config
        assert len(dm.config.providers) == 3

    def test_config_property(self) -> None:
        dm = DiversityManager()
        assert dm.config is dm._config


# ---------------------------------------------------------------------------
# Test: assign_configs
# ---------------------------------------------------------------------------


class TestAssignConfigs:
    def test_assigns_all_roles(self, default_roles: list[str]) -> None:
        dm = DiversityManager()
        assignments = dm.assign_configs(default_roles)
        assert set(assignments.keys()) == set(default_roles)
        assert len(assignments) == 3

    def test_each_role_has_unique_tuple(
        self,
        default_roles: list[str],
    ) -> None:
        dm = DiversityManager()
        assignments = dm.assign_configs(default_roles)
        tuples = [(c.provider, c.model_name, c.temperature) for c in assignments.values()]
        assert len(tuples) == len(set(tuples)), (
            f"Duplicate (provider, model, temp) tuples: {tuples}"
        )

    def test_assigns_from_explicit_config(
        self,
        explicit_config: AgentDiversityConfig,
    ) -> None:
        dm = DiversityManager(config=explicit_config)
        roles = ["literature_review", "falsification", "ethics_review"]
        assignments = dm.assign_configs(roles)

        assert assignments["literature_review"].provider == "ollama"
        assert assignments["falsification"].provider == "openai"
        assert assignments["ethics_review"].provider == "anthropic"

        assert assignments["literature_review"].temperature == 0.2
        assert assignments["falsification"].temperature == 0.8
        assert assignments["ethics_review"].temperature == 0.3

    def test_objective_functions_assigned(
        self,
        explicit_config: AgentDiversityConfig,
    ) -> None:
        dm = DiversityManager(config=explicit_config)
        assignments = dm.assign_configs(["literature_review", "falsification", "ethics_review"])
        objectives = {c.objective_function for c in assignments.values()}
        assert AgentObjective.balanced.value in objectives
        assert AgentObjective.skeptical.value in objectives
        assert AgentObjective.supportive.value in objectives

    def test_temperature_defaults_used(
        self,
    ) -> None:
        config = AgentDiversityConfig(
            temperature_defaults=AgentTemperatureConfig(
                literature_review=0.1,
                falsification=0.9,
                ethics=0.5,
            ),
        )
        dm = DiversityManager(config=config)
        assignments = dm.assign_configs(["literature_review", "falsification", "ethics_review"])
        assert assignments["literature_review"].temperature == 0.1
        assert assignments["falsification"].temperature == 0.9
        assert assignments["ethics_review"].temperature == 0.5

    def test_more_roles_than_providers(self) -> None:
        dm = DiversityManager()
        roles = ["a", "b", "c", "d", "e"]
        assignments = dm.assign_configs(roles)
        assert len(assignments) == 5
        assert set(assignments.keys()) == set(roles)

    def test_single_role(self) -> None:
        dm = DiversityManager()
        assignments = dm.assign_configs(["literature_review"])
        assert len(assignments) == 1
        assert "literature_review" in assignments

    def test_empty_roles(self) -> None:
        dm = DiversityManager()
        assignments = dm.assign_configs([])
        assert len(assignments) == 0

    def test_unknown_role_gets_default_temperature(self) -> None:
        dm = DiversityManager()
        assignments = dm.assign_configs(["unknown_role"])
        assert assignments["unknown_role"].temperature is not None


# ---------------------------------------------------------------------------
# Test: validate_heterogeneous
# ---------------------------------------------------------------------------


class TestValidateHeterogeneous:
    def test_passes_unique_configs(self, default_roles: list[str]) -> None:
        dm = DiversityManager()
        assignments = dm.assign_configs(default_roles)
        dm.validate_heterogeneous(assignments)

    def test_raises_on_duplicates(self) -> None:
        dm = DiversityManager()
        assignments = {
            "a": AgentModelProvider(
                role="a",
                provider="ollama",
                model_name="llama3.1",
                temperature=0.2,
            ),
            "b": AgentModelProvider(
                role="b",
                provider="ollama",
                model_name="llama3.1",
                temperature=0.2,
            ),
        }
        with pytest.raises(DiversityAssignmentError, match="Duplicate"):
            dm.validate_heterogeneous(assignments)

    def test_different_providers_pass(self) -> None:
        dm = DiversityManager()
        assignments = {
            "a": AgentModelProvider(
                role="a",
                provider="ollama",
                model_name="llama3.1",
                temperature=0.2,
            ),
            "b": AgentModelProvider(
                role="b",
                provider="openai",
                model_name="gpt-4o",
                temperature=0.2,
            ),
        }
        dm.validate_heterogeneous(assignments)

    def test_different_temperatures_pass(self) -> None:
        dm = DiversityManager()
        assignments = {
            "a": AgentModelProvider(
                role="a",
                provider="ollama",
                model_name="llama3.1",
                temperature=0.2,
            ),
            "b": AgentModelProvider(
                role="b",
                provider="ollama",
                model_name="llama3.1",
                temperature=0.8,
            ),
        }
        dm.validate_heterogeneous(assignments)

    def test_error_message_includes_duplicate_roles(self) -> None:
        dm = DiversityManager()
        assignments = {
            "alice": AgentModelProvider(
                role="alice",
                provider="ollama",
                model_name="llama3.1",
                temperature=0.2,
            ),
            "bob": AgentModelProvider(
                role="bob",
                provider="ollama",
                model_name="llama3.1",
                temperature=0.2,
            ),
        }
        with pytest.raises(DiversityAssignmentError) as exc:
            dm.validate_heterogeneous(assignments)
        assert "alice" in str(exc.value)
        assert "bob" in str(exc.value)


# ---------------------------------------------------------------------------
# Test: validate_objective_diversity
# ---------------------------------------------------------------------------


class TestObjectiveDiversity:
    def test_all_unique_returns_no_warnings(self) -> None:
        dm = DiversityManager()
        assignments = {
            "a": AgentModelProvider(
                role="a",
                provider="ollama",
                objective_function=AgentObjective.balanced.value,
            ),
            "b": AgentModelProvider(
                role="b",
                provider="openai",
                objective_function=AgentObjective.skeptical.value,
            ),
        }
        warnings = dm.validate_objective_diversity(assignments)
        assert len(warnings) == 0

    def test_duplicate_objectives_return_warnings(self) -> None:
        dm = DiversityManager()
        assignments = {
            "a": AgentModelProvider(
                role="a",
                provider="ollama",
                objective_function=AgentObjective.balanced.value,
            ),
            "b": AgentModelProvider(
                role="b",
                provider="openai",
                objective_function=AgentObjective.balanced.value,
            ),
        }
        warnings = dm.validate_objective_diversity(assignments)
        assert len(warnings) == 1
        assert "balanced" in warnings[0]

    def test_mixed_duplicates_return_multiple_warnings(self) -> None:
        dm = DiversityManager()
        assignments = {
            "a": AgentModelProvider(
                role="a",
                objective_function=AgentObjective.balanced.value,
            ),
            "b": AgentModelProvider(
                role="b",
                objective_function=AgentObjective.balanced.value,
            ),
            "c": AgentModelProvider(
                role="c",
                objective_function=AgentObjective.skeptical.value,
            ),
            "d": AgentModelProvider(
                role="d",
                objective_function=AgentObjective.skeptical.value,
            ),
        }
        warnings = dm.validate_objective_diversity(assignments)
        assert len(warnings) == 2

    def test_empty_assignments(self) -> None:
        dm = DiversityManager()
        warnings = dm.validate_objective_diversity({})
        assert len(warnings) == 0


# ---------------------------------------------------------------------------
# Test: full integration — assign + validate
# ---------------------------------------------------------------------------


class TestDiversityIntegration:
    def test_assign_and_validate(self) -> None:
        dm = DiversityManager()
        roles = ["literature_review", "falsification", "ethics_review"]
        assignments = dm.assign_configs(roles)
        dm.validate_heterogeneous(assignments)

    def test_all_objectives_covered(self) -> None:
        dm = DiversityManager()
        roles = ["a", "b", "c", "d", "e"]
        assignments = dm.assign_configs(roles)
        objectives = {c.objective_function for c in assignments.values()}
        assert len(objectives) >= 2

    def test_serendipity_level_in_config(self) -> None:
        config = AgentDiversityConfig(serendipity_level=0.8)
        dm = DiversityManager(config=config)
        assert dm.config.serendipity_level == 0.8

    def test_contradiction_driven_exploration_flag(self) -> None:
        config = AgentDiversityConfig(enable_contradiction_driven_exploration=False)
        dm = DiversityManager(config=config)
        assert dm.config.enable_contradiction_driven_exploration is False

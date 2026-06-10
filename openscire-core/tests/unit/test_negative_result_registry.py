# SPDX-License-Identifier: Apache-2.0

"""Tests for the Negative Result Registry (Task 6.6)."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import pytest
from openscire.negative_results.cross_link import NegativeResultCrossLinker
from openscire.negative_results.export import NegativeResultExporter
from openscire.negative_results.integration import (
    submit_from_falsification,
)
from openscire.negative_results.models import (
    NegativeResult,
    NegativeResultOutcome,
    NegativeResultQuery,
)
from openscire.negative_results.store import RegistryStore

# -- Fixtures ----------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Any) -> RegistryStore:  # noqa: ANN401
    s = RegistryStore(db_path=str(tmp_path / "test_neg_results.db"))
    s.connect()
    yield s
    s.close()


def _make_result(
    hypothesis: str = "CRISPR gene editing may enhance pathogen virulence",
    outcome: NegativeResultOutcome = NegativeResultOutcome.contradictory,
    domain: str = "virology",
    **overrides: Any,  # noqa: ANN401
) -> NegativeResult:
    defaults: dict[str, Any] = {
        "method_used": "falsification_analysis",
        "data_summary": "3 contradicting sources found",
        "confidence": 0.9,
        "reason_for_failure": "Contradictory evidence found",
        "suggestions": [
            "Test in vitro first",
            "Control for off-target effects",
        ],
        "source_references": ["W123456789", "W987654321"],
        "domain_tags": [domain],
        "created_by": "falsification",
    }
    defaults.update(overrides)
    return NegativeResult(
        hypothesis=hypothesis,
        outcome=outcome,
        **defaults,
    )


def _strong_falsification_report(
    hypothesis: str = "CRISPR gene editing may enhance pathogen virulence",
) -> dict[str, Any]:
    return {
        "hypothesis": hypothesis,
        "overall_assessment": "strong",
        "n_contradicting_sources_found": 3,
        "n_confounds_identified": 2,
        "n_alternatives_proposed": 4,
        "n_counter_examples_generated": 5,
        "falsification_search_results": [
            {"source_id": "W123", "title": "Paper A"},
            {"source_id": "W456", "title": "Paper B"},
        ],
        "confounds": [
            {"variable": "cell line", "category": "confounding"},
        ],
        "counter_examples": [
            {"scenario": "Zero dose test"},
        ],
        "alternative_explanations": ["Reverse causation"],
        "methodology_critique": {
            "overall_critique": "Monoculture in cell line used",
            "testability_assessment": "Testable with controls",
            "methodology_distribution": {"virology": 3, "genetics": 2},
        },
        "remaining_uncertainty": "Some edge cases unexplored",
        "suggestions": ["Test in diverse cell lines"],
    }


# -- Model tests -------------------------------------------------------------


class TestNegativeResultModel:
    def test_default_construction(self) -> None:
        r = NegativeResult()
        assert r.result_id
        assert len(r.result_id) == 16
        assert r.outcome == NegativeResultOutcome.inconclusive
        assert r.confidence == 0.0
        assert r.suggestions == []
        assert r.source_references == []
        assert r.ttl_days == 365
        assert r.expires_at is None

    def test_full_construction(self) -> None:
        r = _make_result()
        assert r.hypothesis.startswith("CRISPR")
        assert r.outcome == NegativeResultOutcome.contradictory
        assert r.confidence == 0.9
        assert len(r.suggestions) == 2
        assert len(r.source_references) == 2
        assert r.domain_tags == ["virology"]

    def test_confidence_bounds(self) -> None:
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            NegativeResult(confidence=-0.1)
        with pytest.raises(ValueError, match="less than or equal to 1"):
            NegativeResult(confidence=1.5)

    def test_ttl_days_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="greater than 0"):
            NegativeResult(ttl_days=0)

    def test_outcome_enum_values(self) -> None:
        assert NegativeResultOutcome.null.value == "null"
        assert NegativeResultOutcome.contradictory.value == "contradictory"
        assert NegativeResultOutcome.inconclusive.value == "inconclusive"
        assert NegativeResultOutcome.methodological_failure.value == "methodological_failure"
        assert NegativeResultOutcome.partial.value == "partial"

    # No model_validator test needed — trust Pydantic

    def test_model_dump_roundtrip(self) -> None:
        r1 = _make_result()
        d = r1.model_dump(mode="json")
        r2 = NegativeResult.model_validate(d)
        assert r1.result_id == r2.result_id
        assert r1.outcome == r2.outcome
        assert r1.suggestions == r2.suggestions
        assert r1.domain_tags == r2.domain_tags


class TestNegativeResultQuery:
    def test_default_construction(self) -> None:
        q = NegativeResultQuery()
        assert q.domain is None
        assert q.limit == 50
        assert q.offset == 0

    def test_limit_bounds(self) -> None:
        with pytest.raises(ValueError, match="greater than or equal to 1"):
            NegativeResultQuery(limit=0)
        with pytest.raises(ValueError, match="less than or equal to 500"):
            NegativeResultQuery(limit=501)
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            NegativeResultQuery(offset=-1)


# -- RegistryStore tests -----------------------------------------------------


class TestRegistryStore:
    def test_connect_and_close(self, tmp_path: Any) -> None:  # noqa: ANN401
        s = RegistryStore(db_path=str(tmp_path / "connect.db"))
        assert not s.connected
        s.connect()
        assert s.connected
        s.close()
        assert not s.connected

    def test_raise_when_not_connected(self) -> None:
        s = RegistryStore()
        with pytest.raises(RuntimeError):
            s.list_all()

    def test_submit_and_get(self, store: RegistryStore) -> None:
        r = _make_result()
        rid = store.submit(r)
        assert rid == r.result_id

        loaded = store.get(rid)
        assert loaded is not None
        assert loaded.hypothesis == r.hypothesis
        assert loaded.outcome == r.outcome
        assert loaded.suggestions == r.suggestions
        assert loaded.domain_tags == r.domain_tags

    def test_submit_calculates_expires_at(self, store: RegistryStore) -> None:
        r = _make_result(expires_at=None)
        assert r.expires_at is None
        store.submit(r)
        loaded = store.get(r.result_id)
        assert loaded is not None
        assert loaded.expires_at is not None
        # expires_at should be ~365 days after created_at
        delta = loaded.expires_at - loaded.created_at
        assert delta.days == 365

    def test_get_nonexistent(self, store: RegistryStore) -> None:
        assert store.get("nonexistent") is None

    def test_list_all_empty(self, store: RegistryStore) -> None:
        assert store.list_all() == []

    def test_list_all_ordering(self, store: RegistryStore) -> None:
        r1 = _make_result(hypothesis="A")
        r2 = _make_result(hypothesis="B")
        # Ensure different timestamps
        r1.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        r2.created_at = datetime(2025, 6, 1, tzinfo=UTC)
        store.submit(r1)
        store.submit(r2)
        lst = store.list_all()
        assert len(lst) == 2
        # Most recent first
        assert lst[0].hypothesis == "B"
        assert lst[1].hypothesis == "A"

    def test_list_all_limit_offset(self, store: RegistryStore) -> None:
        for i in range(5):
            r = _make_result(hypothesis=f"H{i}")
            store.submit(r)
        page1 = store.list_all(limit=2, offset=0)
        assert len(page1) == 2
        page2 = store.list_all(limit=2, offset=2)
        assert len(page2) == 2
        # Pages should not overlap
        ids1 = {r.result_id for r in page1}
        ids2 = {r.result_id for r in page2}
        assert ids1 & ids2 == set()

    def test_count(self, store: RegistryStore) -> None:
        assert store.count() == 0
        store.submit(_make_result())
        assert store.count() == 1
        store.submit(_make_result(hypothesis="B"))
        assert store.count() == 2

    def test_delete(self, store: RegistryStore) -> None:
        r = _make_result()
        store.submit(r)
        assert store.count() == 1
        assert store.delete(r.result_id) is True
        assert store.count() == 0
        assert store.delete(r.result_id) is False

    def test_submit_replaces_existing(self, store: RegistryStore) -> None:
        r = _make_result(hypothesis="Original")
        store.submit(r)
        r2 = _make_result(
            result_id=r.result_id,
            hypothesis="Updated",
        )
        store.submit(r2)
        loaded = store.get(r.result_id)
        assert loaded is not None
        assert loaded.hypothesis == "Updated"

    def test_search_by_domain(self, store: RegistryStore) -> None:
        store.submit(_make_result(domain="virology"))
        store.submit(_make_result(domain="genetics", hypothesis="B"))
        q = NegativeResultQuery(domain="virology")
        results = store.search(q)
        assert len(results) == 1
        assert results[0].domain_tags == ["virology"]

    def test_search_by_topic(self, store: RegistryStore) -> None:
        store.submit(_make_result(hypothesis="Test A hypothesis"))
        store.submit(_make_result(hypothesis="Test B hypothesis different"))
        q = NegativeResultQuery(topic="hypothesis")
        results = store.search(q)
        assert len(results) == 2
        q2 = NegativeResultQuery(topic="A")
        results2 = store.search(q2)
        assert len(results2) == 1

    def test_search_by_outcome(self, store: RegistryStore) -> None:
        store.submit(_make_result(outcome=NegativeResultOutcome.contradictory))
        store.submit(
            _make_result(
                outcome=NegativeResultOutcome.inconclusive,
                hypothesis="B",
            )
        )
        q = NegativeResultQuery(outcome=NegativeResultOutcome.contradictory)
        results = store.search(q)
        assert len(results) == 1
        assert results[0].outcome == NegativeResultOutcome.contradictory

    def test_search_by_date_range(self, store: RegistryStore) -> None:
        r1 = _make_result(hypothesis="A")
        r1.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        r2 = _make_result(hypothesis="B")
        r2.created_at = datetime(2025, 6, 1, tzinfo=UTC)
        store.submit(r1)
        store.submit(r2)
        q = NegativeResultQuery(
            date_from=datetime(2025, 1, 15, tzinfo=UTC),
        )
        results = store.search(q)
        assert len(results) == 1
        assert results[0].hypothesis == "B"

    def test_search_by_method(self, store: RegistryStore) -> None:
        r = _make_result(method_used="western_blot")
        store.submit(r)
        r2 = _make_result(hypothesis="B")
        store.submit(r2)
        q = NegativeResultQuery(method="blot")
        results = store.search(q)
        assert len(results) == 1

    def test_purge_expired(self, store: RegistryStore) -> None:
        r1 = _make_result(hypothesis="Fresh")
        r2 = _make_result(
            hypothesis="Expired",
            expires_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        store.submit(r1)
        store.submit(r2)
        assert store.count() == 2
        purged = store.purge_expired()
        assert purged == 1
        assert store.count() == 1
        assert store.get(r1.result_id) is not None

    def test_get_graveyard_stats(self, store: RegistryStore) -> None:
        store.submit(
            _make_result(
                outcome=NegativeResultOutcome.contradictory,
                domain="virology",
            )
        )
        store.submit(
            _make_result(
                outcome=NegativeResultOutcome.inconclusive,
                domain="virology",
                hypothesis="B",
            )
        )
        store.submit(
            _make_result(
                outcome=NegativeResultOutcome.contradictory,
                domain="genetics",
                hypothesis="C",
            )
        )
        stats = store.get_graveyard_stats()
        assert stats["total"] == 3
        assert stats["by_outcome"]["contradictory"] == 2
        assert stats["by_outcome"]["inconclusive"] == 1
        assert stats["by_domain"]["virology"] == 2
        assert stats["by_domain"]["genetics"] == 1

    def test_json_string_parsing(self, store: RegistryStore) -> None:
        """Verify that JSON string fields are deserialized by the model."""
        r = _make_result(
            suggestions=["Do X", "Do Y"],
            source_references=["W1", "W2"],
            domain_tags=["virology"],
        )
        store.submit(r)
        loaded = store.get(r.result_id)
        assert loaded is not None
        assert loaded.suggestions == ["Do X", "Do Y"]
        assert loaded.source_references == ["W1", "W2"]
        assert loaded.domain_tags == ["virology"]


# -- Export tests ------------------------------------------------------------


class TestNegativeResultExporter:
    def test_to_json(self) -> None:
        r = _make_result()
        output = NegativeResultExporter.to_json([r])
        parsed = json.loads(output)
        assert len(parsed) == 1
        assert parsed[0]["hypothesis"] == r.hypothesis
        assert parsed[0]["outcome"] == "contradictory"

    def test_to_json_empty(self) -> None:
        output = NegativeResultExporter.to_json([])
        assert json.loads(output) == []

    def test_to_csv(self) -> None:
        r = _make_result()
        output = NegativeResultExporter.to_csv([r])
        lines = output.strip().split("\n")
        assert len(lines) == 2  # header + data
        assert "result_id" in lines[0]
        assert r.hypothesis in lines[1]

    def test_to_csv_multiple(self) -> None:
        r1 = _make_result(hypothesis="A")
        r2 = _make_result(hypothesis="B")
        output = NegativeResultExporter.to_csv([r1, r2])
        lines = output.strip().split("\n")
        assert len(lines) == 3  # header + 2 data

    def test_to_ro_crate_structure(self) -> None:
        r = _make_result()
        crate = NegativeResultExporter.to_ro_crate(
            [r],
            dataset_name="Test Export",
        )
        assert crate["@context"] == "https://w3id.org/ro/crate/1.1/context"
        assert "@graph" in crate
        entities = crate["@graph"]
        assert len(entities) == 2  # root + result
        root = entities[0]
        assert root["@type"] == "Dataset"
        assert root["name"] == "Test Export"
        result_entity = entities[1]
        assert result_entity["outcome"] == "contradictory"
        assert result_entity["@id"] == f"#negresult-{r.result_id}"

    def test_to_ro_crate_with_refs(self) -> None:
        r = _make_result(source_references=["W123", "W456"])
        crate = NegativeResultExporter.to_ro_crate([r])
        entity = crate["@graph"][1]
        assert "citation" in entity
        assert len(entity["citation"]) == 2

    def test_to_ro_crate_empty(self) -> None:
        crate = NegativeResultExporter.to_ro_crate([])
        assert len(crate["@graph"]) == 1  # root only
        assert crate["@graph"][0]["hasPart"] == []


# -- Cross-link tests --------------------------------------------------------


class TestNegativeResultCrossLinker:
    def test_link_to_reference(self, store: RegistryStore) -> None:
        r = _make_result()
        store.submit(r)
        linker = NegativeResultCrossLinker(store)
        assert linker.link_to_reference(r.result_id, "W999") is True
        links = linker.get_links(r.result_id)
        assert len(links) == 1
        assert links[0]["reference_id"] == "W999"
        assert links[0]["relationship"] == "related"

    def test_link_duplicate(self, store: RegistryStore) -> None:
        r = _make_result()
        store.submit(r)
        linker = NegativeResultCrossLinker(store)
        linker.link_to_reference(r.result_id, "W999")
        # Second insert should be ignored
        assert linker.link_to_reference(r.result_id, "W999") is False

    def test_unlink_reference(self, store: RegistryStore) -> None:
        r = _make_result()
        store.submit(r)
        linker = NegativeResultCrossLinker(store)
        linker.link_to_reference(r.result_id, "W999")
        assert linker.unlink_reference(r.result_id, "W999") is True
        assert linker.get_links(r.result_id) == []
        assert linker.unlink_reference(r.result_id, "W999") is False

    def test_get_links_empty(self, store: RegistryStore) -> None:
        r = _make_result()
        store.submit(r)
        linker = NegativeResultCrossLinker(store)
        assert linker.get_links(r.result_id) == []

    def test_find_referencing_results(self, store: RegistryStore) -> None:
        r1 = _make_result(hypothesis="A")
        r2 = _make_result(hypothesis="B")
        store.submit(r1)
        store.submit(r2)
        linker = NegativeResultCrossLinker(store)
        linker.link_to_reference(r1.result_id, "W999")
        linker.link_to_reference(r2.result_id, "W999")
        results = linker.find_referencing_results("W999")
        assert len(results) == 2
        hypotheses = {r.hypothesis for r in results}
        assert hypotheses == {"A", "B"}

    def test_find_related_references_no_client(
        self,
        store: RegistryStore,
    ) -> None:
        r = _make_result()
        linker = NegativeResultCrossLinker(store)  # no openalex
        refs = linker.find_related_references(r)
        assert refs == []

    def test_count_links(self, store: RegistryStore) -> None:
        r = _make_result()
        store.submit(r)
        linker = NegativeResultCrossLinker(store)
        assert linker.count_links() == 0
        linker.link_to_reference(r.result_id, "W1")
        linker.link_to_reference(r.result_id, "W2")
        assert linker.count_links() == 2

    def test_get_all_links(self, store: RegistryStore) -> None:
        r = _make_result()
        store.submit(r)
        linker = NegativeResultCrossLinker(store)
        linker.link_to_reference(r.result_id, "W1")
        linker.link_to_reference(r.result_id, "W2")
        all_links = linker.get_all_links()
        assert len(all_links) == 2

    def test_raise_when_store_not_connected(self) -> None:
        s = RegistryStore()
        linker = NegativeResultCrossLinker(s)
        with pytest.raises(RuntimeError):
            linker.get_links("x")


# -- Integration tests -------------------------------------------------------


class TestSubmitFromFalsification:
    def test_strong_contradicted_registered(self, store: RegistryStore) -> None:
        report = _strong_falsification_report()
        rid = submit_from_falsification(store, report)
        assert rid is not None
        loaded = store.get(rid)
        assert loaded is not None
        assert loaded.outcome == NegativeResultOutcome.contradictory
        assert loaded.confidence == 0.9
        assert len(loaded.source_references) == 2
        assert len(loaded.suggestions) == 1

    def test_weak_assessment_skipped(self, store: RegistryStore) -> None:
        report = _strong_falsification_report()
        report["overall_assessment"] = "weak"
        rid = submit_from_falsification(store, report)
        assert rid is None

    def test_empty_hypothesis_skipped(self, store: RegistryStore) -> None:
        report = _strong_falsification_report(hypothesis="")
        rid = submit_from_falsification(store, report)
        assert rid is None

    def test_moderate_assessment(self, store: RegistryStore) -> None:
        report = _strong_falsification_report()
        report["overall_assessment"] = "moderate"
        rid = submit_from_falsification(store, report)
        assert rid is not None
        loaded = store.get(rid)
        assert loaded is not None
        assert loaded.outcome == NegativeResultOutcome.inconclusive
        assert loaded.confidence == 0.5

    def test_strong_confounded_only(self, store: RegistryStore) -> None:
        report = _strong_falsification_report()
        report["n_contradicting_sources_found"] = 0
        rid = submit_from_falsification(store, report)
        assert rid is not None
        loaded = store.get(rid)
        assert loaded is not None
        assert loaded.outcome == NegativeResultOutcome.methodological_failure

    def test_end_to_end(self, store: RegistryStore) -> None:
        """Full cycle: falsification report → store → search → export."""
        report = _strong_falsification_report()
        rid = submit_from_falsification(store, report)
        assert rid is not None

        loaded = store.get(rid)
        assert loaded is not None
        assert loaded.outcome == NegativeResultOutcome.contradictory

        q = NegativeResultQuery(domain="virology")
        results = store.search(q)
        assert len(results) == 1

        csv_out = NegativeResultExporter.to_csv(results)
        assert loaded.hypothesis in csv_out

    def test_provenance_entry_id_passed(self, store: RegistryStore) -> None:
        report = _strong_falsification_report()
        rid = submit_from_falsification(
            store,
            report,
            provenance_entry_id="prov_abc123",
        )
        assert rid is not None
        loaded = store.get(rid)
        assert loaded is not None
        assert loaded.provenance_entry_id == "prov_abc123"


# -- FalsificationAgent integration (implicit) -------------------------------


class TestFalsificationAgentWiring:
    """Verify that the optional registry param works in FalsificationAgent."""

    @pytest.mark.asyncio
    async def test_agent_accepts_registry(
        self,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        from openscire.agent.bus import AgentBus
        from openscire.agent.falsification import FalsificationAgent
        from openscire.agent.models import (
            AgentMessage,
            MessageType,
            ResultPayload,
            TaskPayload,
        )

        AgentBus.reset()
        reg = RegistryStore(db_path=str(tmp_path / "wire_test.db"))
        reg.connect()
        bus = AgentBus.get_bus("test_neg_wire")
        agent = FalsificationAgent(
            bus=bus,
            agent_id="neg_falsifier",
            negative_result_registry=reg,
        )
        assert agent._neg_registry is reg

        results: list[dict[str, Any]] = []

        async def collector(msg: AgentMessage) -> None:
            p = ResultPayload.model_validate(msg.payload)
            results.append(
                {
                    "success": p.success,
                    "output": p.output,
                }
            )

        bus.subscribe("test_caller", {MessageType.result}, collector)
        bus.publish(
            AgentMessage(
                sender="test_caller",
                recipient="neg_falsifier",
                message_type=MessageType.task,
                payload=TaskPayload(
                    description="Test hypothesis",
                    parameters={"hypothesis": "CRISPR may enhance virulence"},
                ).model_dump(),
            ),
        )

        await asyncio.sleep(0.1)

        assert len(results) >= 1
        assert reg.count() == 1

        reg.close()
        AgentBus.reset()

    def test_agent_without_registry_still_works(self) -> None:
        """Verify backward compatibility — no registry = no crash."""
        from openscire.agent.bus import AgentBus
        from openscire.agent.falsification import FalsificationAgent

        AgentBus.reset()
        bus = AgentBus.get_bus("test_neg_no_reg")
        agent = FalsificationAgent(bus=bus, agent_id="no_reg")
        assert agent._neg_registry is None
        AgentBus.reset()

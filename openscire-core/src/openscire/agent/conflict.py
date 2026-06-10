# SPDX-License-Identifier: Apache-2.0

"""ConflictResolver — detects and adjudicates disagreements between specialist agents.

4-stage pipeline:
  1. detect — scan results for contradictory claims
  2. evidence_request — ask disagreeing agents to strengthen their cases
  3. escalate — unresolved conflicts go to a human
  4. register — final unresolved conflicts are registered as open questions
"""

from openscire.agent.exceptions import ConflictUnresolvedError
from openscire.agent.models import (
    AgentPosition,
    ConflictRecord,
    ConflictStatus,
    ResearchTask,
)


class ConflictResolver:
    """Detects and manages disagreements between specialist agent results.

    Args:
        max_evidence_rounds: Maximum evidence-gathering iterations per conflict
            before escalation.
    """

    def __init__(self, max_evidence_rounds: int = 2) -> None:
        self._conflicts: dict[str, ConflictRecord] = {}
        self._max_evidence_rounds = max_evidence_rounds
        self._evidence_rounds: dict[str, int] = {}

    def detect(self, tasks: list[ResearchTask]) -> list[ConflictRecord]:
        """Scan completed task results for contradictory claims.

        Two results conflict when they address overlapping topics with
        mutually exclusive conclusions. This is a heuristic scan based on
        task metadata — full semantic conflict detection is deferred.

        Args:
            tasks: Completed research tasks.

        Returns:
            Newly detected ConflictRecords.
        """
        new_conflicts: list[ConflictRecord] = []

        completed = [t for t in tasks if t.status.value == "completed" and t.result]
        for i in range(len(completed)):
            for j in range(i + 1, len(completed)):
                conflict = self._check_pair(completed[i], completed[j])
                if conflict is not None:
                    self._conflicts[conflict.conflict_id] = conflict
                    new_conflicts.append(conflict)

        return new_conflicts

    def _check_pair(self, task_a: ResearchTask, task_b: ResearchTask) -> ConflictRecord | None:
        """Check if two tasks have contradictory results.

        Returns a ConflictRecord if a contradiction is detected, None otherwise.
        """
        if not task_a.result or not task_b.result:
            return None

        output_a = task_a.result.get("output", {})
        output_b = task_b.result.get("output", {})

        conclusion_a = output_a.get("conclusion", "")
        conclusion_b = output_b.get("conclusion", "")

        if not conclusion_a or not conclusion_b:
            return None

        if _is_contradictory(conclusion_a, conclusion_b):
            return ConflictRecord(
                topic=_extract_topic(task_a, task_b),
                positions=[
                    AgentPosition(
                        agent_id=task_a.agent_role,
                        claim=conclusion_a,
                        evidence=output_a.get("evidence", []),
                        confidence=output_a.get("confidence"),
                    ),
                    AgentPosition(
                        agent_id=task_b.agent_role,
                        claim=conclusion_b,
                        evidence=output_b.get("evidence", []),
                        confidence=output_b.get("confidence"),
                    ),
                ],
            )
        return None

    def request_evidence(self, conflict_id: str) -> list[str]:
        """Request additional evidence for an open conflict.

        Returns the agent_ids that need to provide more evidence.

        Args:
            conflict_id: The conflict requiring evidence.

        Returns:
            List of agent_ids from which evidence is requested.
        """
        conflict = self._conflicts.get(conflict_id)
        if conflict is None:
            raise ConflictUnresolvedError(
                message=f"Unknown conflict: {conflict_id}",
                source="ConflictResolver.request_evidence",
            )

        rounds = self._evidence_rounds.get(conflict_id, 0)
        if rounds >= self._max_evidence_rounds:
            conflict.status = ConflictStatus.escalated_to_human
            return []

        self._evidence_rounds[conflict_id] = rounds + 1
        conflict.status = ConflictStatus.evidence_requested

        return [pos.agent_id for pos in conflict.positions]

    def escalate_to_human(self, conflict_id: str) -> ConflictRecord:
        """Escalate an unresolved conflict to human review.

        Args:
            conflict_id: The conflict to escalate.

        Returns:
            The updated ConflictRecord.
        """
        conflict = self._conflicts.get(conflict_id)
        if conflict is None:
            raise ConflictUnresolvedError(
                message=f"Unknown conflict: {conflict_id}",
                source="ConflictResolver.escalate_to_human",
            )
        conflict.status = ConflictStatus.escalated_to_human
        conflict.escalated_to_human = True
        return conflict

    def resolve(self, conflict_id: str, resolution: str) -> ConflictRecord:
        """Mark a conflict as resolved.

        Args:
            conflict_id: The conflict to resolve.
            resolution: Description of how it was resolved.

        Returns:
            The updated ConflictRecord.
        """
        conflict = self._conflicts.get(conflict_id)
        if conflict is None:
            raise ConflictUnresolvedError(
                message=f"Unknown conflict: {conflict_id}",
                source="ConflictResolver.resolve",
            )
        conflict.status = ConflictStatus.resolved
        conflict.resolution = resolution
        return conflict

    def register_open_question(self, conflict_id: str) -> ConflictRecord:
        """Register a conflict as an open question (no resolution).

        Args:
            conflict_id: The conflict to register.

        Returns:
            The updated ConflictRecord.
        """
        conflict = self._conflicts.get(conflict_id)
        if conflict is None:
            raise ConflictUnresolvedError(
                message=f"Unknown conflict: {conflict_id}",
                source="ConflictResolver.register_open_question",
            )
        conflict.status = ConflictStatus.registered_as_open_question
        conflict.resolution = "Registered as open question — no definitive resolution."
        return conflict

    def get_conflict(self, conflict_id: str) -> ConflictRecord | None:
        return self._conflicts.get(conflict_id)

    @property
    def open_conflicts(self) -> list[ConflictRecord]:
        return [
            c
            for c in self._conflicts.values()
            if c.status in (ConflictStatus.open, ConflictStatus.evidence_requested)
        ]

    @property
    def all_conflicts(self) -> list[ConflictRecord]:
        return list(self._conflicts.values())


def _is_contradictory(conclusion_a: str, conclusion_b: str) -> bool:
    """Heuristic check if two conclusions are contradictory.

    This is a simple keyword-based check. Full semantic contradiction
    detection requires an LLM and is deferred to post-pilot.
    """
    negation_markers = ["not ", "no ", "does not", "cannot", "unlikely", "contradict"]
    a_lower = conclusion_a.lower()
    b_lower = conclusion_b.lower()

    has_negation_b = any(m in b_lower for m in negation_markers)
    has_negation_a = any(m in a_lower for m in negation_markers)

    noun_phrase_a = _extract_noun_phrase(a_lower)
    noun_phrase_b = _extract_noun_phrase(b_lower)

    same_topic = _words_overlap(noun_phrase_a, noun_phrase_b, min_overlap=2)
    return same_topic and has_negation_b != has_negation_a


def _words_overlap(phrase_a: str, phrase_b: str, min_overlap: int = 2) -> bool:
    """Check if two phrases share at least min_overlap significant words."""
    stop_words = {
        "the",
        "a",
        "an",
        "in",
        "of",
        "to",
        "for",
        "with",
        "on",
        "at",
        "by",
        "from",
        "and",
        "or",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "can",
    }
    words_a = {w for w in phrase_a.split() if w not in stop_words}
    words_b = {w for w in phrase_b.split() if w not in stop_words}
    return len(words_a & words_b) >= min_overlap


def _extract_noun_phrase(text: str) -> str:
    """Extract a simple noun phrase from text (first sentence, first 5 words)."""
    first_sentence = text.split(".")[0]
    words = first_sentence.split()
    return " ".join(words[:5]).lower()


def _extract_topic(task_a: ResearchTask, task_b: ResearchTask) -> str:
    """Derive a topic label from two conflicting tasks."""
    words_a = task_a.description.split()
    words_b = task_b.description.split()
    common = [w for w in words_a if w in words_b and len(w) > 3]
    return " ".join(common[:5]) if common else task_a.description[:80]

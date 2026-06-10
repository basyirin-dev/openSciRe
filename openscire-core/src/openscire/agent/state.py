# SPDX-License-Identifier: Apache-2.0

"""SupervisorStateMachine — state machine for research session orchestration.

States:
    idle → planning → executing → reviewing → completed
      ↓        ↓           ↓            ↓
     failed   failed     failed       failed

The machine enforces valid transitions and rejects invalid ones via SupervisorError.
"""

from openscire.agent.exceptions import SupervisorError
from openscire.agent.models import SupervisorState


class SupervisorStateMachine:
    """Lightweight state machine for supervisor orchestration.

    Encodes exactly 9 valid transitions across 6 states.
    """

    _transitions: dict[SupervisorState, set[SupervisorState]] = {
        SupervisorState.idle: {SupervisorState.planning, SupervisorState.failed},
        SupervisorState.planning: {
            SupervisorState.executing,
            SupervisorState.failed,
            SupervisorState.idle,
        },
        SupervisorState.executing: {
            SupervisorState.reviewing,
            SupervisorState.failed,
            SupervisorState.idle,
        },
        SupervisorState.reviewing: {
            SupervisorState.completed,
            SupervisorState.failed,
            SupervisorState.idle,
        },
        SupervisorState.failed: {SupervisorState.idle},
        SupervisorState.completed: set(),
    }

    def __init__(self, initial_state: SupervisorState = SupervisorState.idle) -> None:
        self._state = initial_state

    def transition(self, new_state: SupervisorState) -> SupervisorState:
        """Transition to a new state.

        Args:
            new_state: The target state.

        Returns:
            The new state (for chaining).

        Raises:
            SupervisorError: If the transition is invalid.
        """
        allowed = self._transitions.get(self._state, set())
        if new_state not in allowed:
            raise SupervisorError(
                message=f"Invalid state transition: {self._state.value} -> {new_state.value}",
                source="SupervisorStateMachine.transition",
            )
        self._state = new_state
        return self._state

    def can_transition(self, new_state: SupervisorState) -> bool:
        """Check whether a transition is valid without applying it."""
        return new_state in self._transitions.get(self._state, set())

    @property
    def state(self) -> SupervisorState:
        return self._state

    @state.setter
    def state(self, value: SupervisorState) -> None:
        self.transition(value)

    @property
    def is_terminal(self) -> bool:
        return self._state in (SupervisorState.completed, SupervisorState.failed)

    @property
    def is_active(self) -> bool:
        terminal = (SupervisorState.idle, SupervisorState.completed, SupervisorState.failed)
        return self._state not in terminal

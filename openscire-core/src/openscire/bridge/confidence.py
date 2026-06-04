# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class PropagationStrategy(StrEnum):
    UNION = "union"
    INTERSECTION = "intersection"
    WEIGHTED_AVERAGE = "weighted_average"


class ConfidenceTrace(BaseModel):
    value: float = Field(default=0.0, ge=0.0, le=1.0)
    source: str = ""
    weight: float = Field(default=1.0, ge=0.0)
    children: list[ConfidenceTrace] = Field(default_factory=list)

    def propagate(self, strategy: PropagationStrategy) -> ConfidenceTrace:
        if not self.children:
            return self.model_copy(deep=True)

        propagated_children = [c.propagate(strategy) for c in self.children]

        if strategy == PropagationStrategy.UNION:
            new_value = max(c.value for c in propagated_children)
        elif strategy == PropagationStrategy.INTERSECTION:
            new_value = min(c.value for c in propagated_children)
        elif strategy == PropagationStrategy.WEIGHTED_AVERAGE:
            total_weight = sum(c.weight for c in propagated_children)
            if total_weight == 0:
                new_value = 0.0
            else:
                new_value = sum(c.value * c.weight for c in propagated_children) / total_weight
        else:
            msg = f"Unknown propagation strategy: {strategy}"
            raise ValueError(msg)

        return ConfidenceTrace(
            value=round(new_value, 6),
            source=self.source,
            weight=self.weight,
            children=propagated_children,
        )

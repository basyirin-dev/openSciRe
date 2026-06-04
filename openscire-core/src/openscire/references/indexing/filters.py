from __future__ import annotations

import re
from enum import StrEnum
from typing import Any


class FilterOperator(StrEnum):
    eq = "eq"
    neq = "neq"
    gt = "gt"
    gte = "gte"
    lt = "lt"
    lte = "lte"
    in_ = "in"
    contains = "contains"


class FilterExpression:
    def evaluate(self, metadata: dict[str, Any]) -> bool:
        raise NotImplementedError


class FieldFilter(FilterExpression):
    def __init__(
        self,
        field: str,
        operator: FilterOperator,
        value: Any,  # noqa: ANN401
    ) -> None:
        self.field = field
        self.operator = operator
        self.value = value

    def evaluate(self, metadata: dict[str, Any]) -> bool:
        actual = metadata.get(self.field)
        if actual is None and self.operator != FilterOperator.neq:
            return False
        return self._compare(actual)

    def _compare(self, actual: Any) -> bool:  # noqa: ANN401
        op = self.operator
        if op == FilterOperator.eq:
            return actual == self.value
        elif op == FilterOperator.neq:
            return actual != self.value
        elif op == FilterOperator.gt:
            return actual is not None and actual > self.value
        elif op == FilterOperator.gte:
            return actual is not None and actual >= self.value
        elif op == FilterOperator.lt:
            return actual is not None and actual < self.value
        elif op == FilterOperator.lte:
            return actual is not None and actual <= self.value
        elif op == FilterOperator.in_:
            return actual in self.value
        elif op == FilterOperator.contains:
            return isinstance(actual, str) and self.value in actual
        return False


class AndFilter(FilterExpression):
    def __init__(self, *children: FilterExpression) -> None:
        self.children = list(children)

    def evaluate(self, metadata: dict[str, Any]) -> bool:
        return all(c.evaluate(metadata) for c in self.children)


class OrFilter(FilterExpression):
    def __init__(self, *children: FilterExpression) -> None:
        self.children = list(children)

    def evaluate(self, metadata: dict[str, Any]) -> bool:
        return any(c.evaluate(metadata) for c in self.children)


class NotFilter(FilterExpression):
    def __init__(self, child: FilterExpression) -> None:
        self.child = child

    def evaluate(self, metadata: dict[str, Any]) -> bool:
        return not self.child.evaluate(metadata)


def evaluate(expr: FilterExpression | None, metadata: dict[str, Any]) -> bool:
    if expr is None:
        return True
    return expr.evaluate(metadata)


def field(field: str, op: str | FilterOperator, value: Any) -> FieldFilter:  # noqa: ANN401
    if isinstance(op, str):
        op = FilterOperator(op)
    return FieldFilter(field, op, value)


def and_(*children: FilterExpression) -> AndFilter:
    return AndFilter(*children)


def or_(*children: FilterExpression) -> OrFilter:
    return OrFilter(*children)


def not_(child: FilterExpression) -> NotFilter:
    return NotFilter(child)

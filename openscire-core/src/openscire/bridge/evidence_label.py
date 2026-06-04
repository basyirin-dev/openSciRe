# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class EvidenceTypeLabel(StrEnum):
    PREDICTED = "P"
    EXPERIMENTAL = "E"
    REVIEWED = "R"


class EvidenceTagged(BaseModel):
    value: Any
    evidence_label: EvidenceTypeLabel = EvidenceTypeLabel.EXPERIMENTAL


class EvidencePropagator:
    @staticmethod
    def combine(labels: list[EvidenceTypeLabel]) -> EvidenceTypeLabel:
        if EvidenceTypeLabel.REVIEWED in labels:
            return EvidenceTypeLabel.REVIEWED
        if EvidenceTypeLabel.EXPERIMENTAL in labels:
            return EvidenceTypeLabel.EXPERIMENTAL
        return EvidenceTypeLabel.PREDICTED

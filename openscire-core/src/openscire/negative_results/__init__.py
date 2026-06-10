# SPDX-License-Identifier: Apache-2.0

"""Negative Result Registry — persistent storage of falsified, contradictory,
or inconclusive hypothesis outcomes.

Provides models, SQLite-backed storage, export (JSON/CSV/RO-Crate),
cross-linking to literature references, and automatic submission
from the FalsificationAgent.
"""

from openscire.negative_results.cross_link import NegativeResultCrossLinker
from openscire.negative_results.export import NegativeResultExporter
from openscire.negative_results.integration import submit_from_falsification
from openscire.negative_results.models import (
    NegativeResult,
    NegativeResultOutcome,
    NegativeResultQuery,
)
from openscire.negative_results.store import RegistryStore

__all__ = [
    "NegativeResult",
    "NegativeResultOutcome",
    "NegativeResultQuery",
    "RegistryStore",
    "NegativeResultExporter",
    "NegativeResultCrossLinker",
    "submit_from_falsification",
]

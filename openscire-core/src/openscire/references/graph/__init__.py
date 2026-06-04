# SPDX-License-Identifier: Apache-2.0

"""Citation graph analysis — traversal, influence scoring, temporal patterns, and clustering."""

from openscire.references.graph.analyzer import CitationGraphAnalyzer
from openscire.references.graph.builder import CitationGraphBuilder
from openscire.references.graph.clustering import ClusterEngine
from openscire.references.graph.export import GraphExporter
from openscire.references.graph.influence import InfluenceScorer
from openscire.references.graph.models import (
    CitationCluster,
    CitationGraphReport,
    CitationTimeline,
    ClusterReport,
    DecayReport,
    DecayResult,
    GraphExport,
    InfluenceReport,
    InfluenceResult,
    YearCount,
)
from openscire.references.graph.temporal import TemporalAnalyzer

__all__ = [
    "CitationCluster",
    "CitationGraphAnalyzer",
    "CitationGraphBuilder",
    "CitationGraphReport",
    "CitationTimeline",
    "ClusterEngine",
    "ClusterReport",
    "DecayReport",
    "DecayResult",
    "GraphExport",
    "GraphExporter",
    "InfluenceReport",
    "InfluenceResult",
    "InfluenceScorer",
    "TemporalAnalyzer",
    "YearCount",
]

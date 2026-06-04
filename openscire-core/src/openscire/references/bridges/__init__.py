# SPDX-License-Identifier: Apache-2.0

"""Bridge implementations for reference managers and search APIs."""

from openscire.references.bridges.ajol import AjolClient
from openscire.references.bridges.arxiv import ArXivClient
from openscire.references.bridges.base import ReferenceBridge, ReferenceBridgeConfig
from openscire.references.bridges.cnki import CnkiClient
from openscire.references.bridges.elibrary import ElibraryClient
from openscire.references.bridges.mendeley import MendeleyBridge
from openscire.references.bridges.openalex import OpenAlexClient
from openscire.references.bridges.pmc import PMCBridge
from openscire.references.bridges.pubmed import PubMedBridge
from openscire.references.bridges.scielo import ScieloClient
from openscire.references.bridges.semantic_scholar import SemanticScholarClient
from openscire.references.bridges.unpaywall import UnpaywallClient
from openscire.references.bridges.wanfang import WanfangClient
from openscire.references.bridges.zotero import ZoteroBridge

__all__ = [
    "ReferenceBridge",
    "ReferenceBridgeConfig",
    "ZoteroBridge",
    "MendeleyBridge",
    "PubMedBridge",
    "PMCBridge",
    "ArXivClient",
    "SemanticScholarClient",
    "OpenAlexClient",
    "UnpaywallClient",
    "AjolClient",
    "CnkiClient",
    "ElibraryClient",
    "ScieloClient",
    "WanfangClient",
]

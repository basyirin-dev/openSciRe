"""Ethical governance layer: firewall, tier classification, carbon tracking, and source grounding.

Provides EthicalFirewall (pre/post-inference scanning), TierClassifier (risk tier
assignment with cool-off), CarbonBudgetTracker (energy/carbon estimation and capping),
DataSovereigntyChecker (consent/export restriction enforcement), IndigenousKnowledgeProtector
(CARE principles), ConfabulationDetector (post-generation claim validation), and
VerificationAsymmetryTracker (epistemic asymmetry auditing).
"""

from openscire.constants import DURCCategory, ErrorCode, RiskTier
from openscire.ethics.audit import FirewallAuditLog
from openscire.ethics.carbon import CarbonBudgetTracker
from openscire.ethics.classifier import (
    DURCClassifier,
    EmbeddingMatcher,
    KeywordMatcher,
    LLMClassifier,
)
from openscire.ethics.confabulation import ConfabulationDetector
from openscire.ethics.durc import DEFAULT_KEYWORD_PATTERNS, EMBEDDING_SEEDS, build_default_rules
from openscire.ethics.feedback import ContestManager
from openscire.ethics.firewall import EthicalFirewall, FirewalledProvider
from openscire.ethics.indigenous_knowledge import (
    CAREPrinciple,
    IndigenousKnowledgeCategory,
    IndigenousKnowledgeProtector,
    IndigenousKnowledgeVerdict,
)
from openscire.ethics.models import (
    AsymmetryRecord,
    BudgetStatus,
    CarbonEstimate,
    CarbonRecord,
    Citation,
    CitationSupport,
    ConfabulationFlag,
    ConfabulationReport,
    ConfabulationType,
    ConsentRestriction,
    ContestRecord,
    DataOrigin,
    DURCResult,
    EthicsDecision,
    ExportRestriction,
    FirewallAction,
    FirewallAuditEntry,
    FirewallRule,
    GroundingVerdict,
    HallucinationRecord,
    MatchType,
    OverrideRecord,
    ScanLevel,
    Source,
    SourceVerification,
    SourceVerificationStatus,
    SovereigntyVerdict,
    TierAssignment,
    TierGovernanceAction,
    TierResult,
    UnsupportedClaimFlag,
    VerifiabilityCategory,
    VerificationAsymmetryReport,
    VerificationPath,
    VerificationStatus,
)
from openscire.ethics.source_grounding import SourceGroundingEngine
from openscire.ethics.sovereignty import (
    ConsentMetadataParser,
    DataSovereigntyChecker,
)
from openscire.ethics.tier import CoolOffRegistry, TierClassifier
from openscire.ethics.verification_asymmetry import VerificationAsymmetryTracker

__all__ = [
    "DURCCategory",
    "ErrorCode",
    "RiskTier",
    "EthicalFirewall",
    "FirewalledProvider",
    "CarbonBudgetTracker",
    "CarbonEstimate",
    "CarbonRecord",
    "BudgetStatus",
    "DURCClassifier",
    "KeywordMatcher",
    "EmbeddingMatcher",
    "LLMClassifier",
    "FirewallAuditLog",
    "ContestManager",
    "FirewallRule",
    "FirewallAction",
    "ScanLevel",
    "MatchType",
    "DURCResult",
    "EthicsDecision",
    "FirewallAuditEntry",
    "ContestRecord",
    "TierClassifier",
    "CoolOffRegistry",
    "TierResult",
    "TierAssignment",
    "TierGovernanceAction",
    "OverrideRecord",
    "DataOrigin",
    "ConsentRestriction",
    "ExportRestriction",
    "SovereigntyVerdict",
    "DataSovereigntyChecker",
    "ConsentMetadataParser",
    "DEFAULT_KEYWORD_PATTERNS",
    "EMBEDDING_SEEDS",
    "build_default_rules",
    "IndigenousKnowledgeCategory",
    "CAREPrinciple",
    "IndigenousKnowledgeProtector",
    "IndigenousKnowledgeVerdict",
    "Citation",
    "CitationSupport",
    "Source",
    "SourceVerification",
    "SourceVerificationStatus",
    "UnsupportedClaimFlag",
    "GroundingVerdict",
    "SourceGroundingEngine",
    "VerifiabilityCategory",
    "VerificationStatus",
    "VerificationPath",
    "AsymmetryRecord",
    "VerificationAsymmetryReport",
    "VerificationAsymmetryTracker",
    "ConfabulationType",
    "ConfabulationFlag",
    "ConfabulationReport",
    "HallucinationRecord",
    "ConfabulationDetector",
]

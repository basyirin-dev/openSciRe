# SPDX-License-Identifier: Apache-2.0

"""Configuration management with env var binding and hot-reload support."""

import os
import subprocess
import sys
import tomllib
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from openscire.constants import DURCCategory, ErrorCode
from openscire.exceptions import ConfigError
from openscire.models import ReproducibilityBundle
from openscire.models.philosophy import (
    AgentDiversityConfig,
    FalsificationConfig,
)


class ModelConfig(BaseModel):
    """Configuration for an LLM provider connection.

    Attributes:
        provider: Provider name (e.g., ollama, openai).
        model_name: Model identifier to use.
        temperature: Sampling temperature (0.0-2.0).
        max_tokens: Maximum tokens per response.
    """

    provider: str = "ollama"
    model_name: str = "llama3.1"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0)


class ProvenanceConfig(BaseModel):
    """Configuration for provenance tracking and storage.

    Attributes:
        storage_backend: Backend type (sqlite, in_memory, postgres).
        signing_key_path: Path to Ed25519 signing key for entry signatures.
        db_path: Path to SQLite database file.
    """

    storage_backend: str = "sqlite"
    signing_key_path: str = ""
    db_path: str = "data/provenance.db"


class LoggingConfig(BaseModel):
    """Configuration for structured logging output.

    Attributes:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL, SCIENCE).
        format: Output format (json or text).
        output: Destination (stdout, stderr, file, syslog).
        log_file: File path when output is 'file'.
    """

    level: str = Field(default="INFO")
    format: str = Field(default="json")
    output: str = "stdout"
    log_file: str = "openscire.log"

    @field_validator("level")
    @classmethod
    def _validate_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "SCIENCE"}
        if v.upper() not in allowed:
            msg = f"Log level must be one of {allowed}"
            raise ConfigError(msg, source="config", error_code=ErrorCode.CONFIG_INVALID)
        return v.upper()

    @field_validator("format")
    @classmethod
    def _validate_format(cls, v: str) -> str:
        allowed = {"json", "text"}
        if v.lower() not in allowed:
            msg = f"Log format must be one of {allowed}"
            raise ConfigError(msg, source="config", error_code=ErrorCode.CONFIG_INVALID)
        return v.lower()

    @field_validator("output")
    @classmethod
    def _validate_output(cls, v: str) -> str:
        allowed = {"stdout", "stderr", "file", "syslog"}
        if v.lower() not in allowed:
            msg = f"Log output must be one of {allowed}"
            raise ConfigError(msg, source="config", error_code=ErrorCode.CONFIG_INVALID)
        return v.lower()


class LiteratureConfig(BaseModel):
    """Configuration for literature retrieval and caching.

    Attributes:
        max_sources: Maximum sources to retrieve per query.
        cache_ttl: Cache time-to-live in seconds.
        retraction_check_interval: Interval in seconds for retraction checks.
        embedding_model: Model name for semantic search embeddings.
    """

    max_sources: int = Field(default=50, gt=0)
    cache_ttl: int = Field(default=3600, gt=0)
    retraction_check_interval: int = Field(default=86400, gt=0)
    embedding_model: str = "all-MiniLM-L6-v2"


class EthicsConfig(BaseModel):
    """Configuration for ethical safeguards, DURC detection, and resource accounting.

    Attributes:
        firewall_mode: Default action on ethics violation (flag, warn, block, escalate).
        durc_enabled: Whether the DURC firewall is active.
        durc_categories: List of enabled DURC categories (default: all).
        durc_embedding_model: Embedding model name for semantic detection
            (empty = disabled). Requires sentence-transformers.
        durc_llm_classifier_provider: Provider for LLM-assisted DURC classification
            (empty = disabled). Should be a separate model from the primary
            inference model to avoid circular jailbreak risk.
        durc_llm_classifier_model: Model name for LLM classifier.
        durc_min_confidence: Minimum confidence threshold for flagging (0.0-1.0).
        audit_db_path: Filesystem path for the firewall audit SQLite DB.
        audit_signing_key_path: Path to Ed25519 signing key for audit entries
            (empty = unsigned).
        enable_feedback_loop: Whether users can contest firewall decisions.
        carbon_budget_monthly_kwh: Monthly carbon budget in kWh.
        tier_enabled: Whether tier-based governance is active.
        tier_cooling_off_hours: Cooling-off period in hours for HIGH tier queries.
        tier_embedding_model: Embedding model for semantic tier classification
            (empty = disabled).
        tier_llm_classifier_provider: Provider for LLM-assisted tier classification
            (empty = disabled).
        tier_llm_classifier_model: Model name for LLM tier classifier.
        tier_min_confidence: Minimum confidence for tier classification (0.0-1.0).
        sovereignty_enabled: Whether data sovereignty checks are active.
        sovereignty_require_origin: Whether data origin metadata is required.
        sovereignty_block_no_consent: Whether to block data without consent metadata.
        sovereignty_allowlist_countries: Comma-separated list of data origin
            countries exempt from export restriction (empty = none).
        indigenous_knowledge_enabled: Whether CARE-based indigenous knowledge
            protection checks are active.
        carbon_enabled: Whether carbon tracking and budget enforcement is active.
        carbon_budget_monthly_kwh: Monthly carbon budget in kWh.
        carbon_budget_warning_threshold: Fraction (0-1) of budget that triggers
            a warning (default 0.8 = 80%).
        carbon_grid_intensity_kg_co2e_per_kwh: Grid carbon intensity in kg CO2e
            per kWh for CO2e estimation.
        carbon_hardware_tdp_watts: GPU TDP in watts for energy modeling
            (default 350 = RTX 3090 class).
        carbon_hardware_flops: GPU FP16 TFLOPS for runtime estimation
            (default 142e12 = RTX 3090).
        carbon_model_params: Default model parameter count (default 7B).
        carbon_equivalences_enabled: Whether to include human-readable
            equivalence text in carbon estimates.
        carbon_db_path: Filesystem path for the carbon budget SQLite DB.
    """

    firewall_mode: str = Field(default="warn")
    durc_enabled: bool = True
    durc_categories: list[str] = Field(default_factory=lambda: [c.value for c in DURCCategory])
    durc_embedding_model: str = ""
    durc_llm_classifier_provider: str = ""
    durc_llm_classifier_model: str = "llama3.2:3b"
    durc_min_confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    audit_db_path: str = "data/firewall_audit.db"
    audit_signing_key_path: str = ""
    enable_feedback_loop: bool = True
    carbon_enabled: bool = True
    carbon_budget_monthly_kwh: float = Field(default=50.0, ge=0.0)
    carbon_budget_warning_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    carbon_grid_intensity_kg_co2e_per_kwh: float = Field(default=0.4, ge=0.0)
    carbon_hardware_tdp_watts: int = Field(default=350, gt=0)
    carbon_hardware_flops: int = Field(default=142_000_000_000_000, gt=0)
    carbon_model_params: int = Field(default=7_000_000_000, gt=0)
    carbon_equivalences_enabled: bool = True
    carbon_db_path: str = "data/carbon_budget.db"
    tier_enabled: bool = True
    tier_cooling_off_hours: int = Field(default=24, gt=0)
    tier_embedding_model: str = ""
    tier_llm_classifier_provider: str = ""
    tier_llm_classifier_model: str = "llama3.2:3b"
    tier_min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    sovereignty_enabled: bool = True
    sovereignty_require_origin: bool = False
    sovereignty_block_no_consent: bool = True
    sovereignty_allowlist_countries: str = ""
    indigenous_knowledge_enabled: bool = True

    @field_validator("firewall_mode")
    @classmethod
    def _validate_firewall_mode(cls, v: str) -> str:
        allowed = {"flag", "warn", "block", "escalate"}
        if v.lower() not in allowed:
            msg = f"firewall_mode must be one of {allowed}"
            raise ConfigError(msg, source="config", error_code=ErrorCode.CONFIG_INVALID)
        return v.lower()


class UncertaintyConfig(BaseModel):
    """Configuration for uncertainty quantification and disclosure.

    Attributes:
        enabled: Whether uncertainty quantification is active.
        min_confidence_for_acceptance: Minimum confidence (0-1) for accepting
            a claim without additional review.
        contradiction_threshold: Overlap threshold (0-1) for detecting
            contradiction between claims.
        boundary_confidence_threshold: Confidence threshold (0-1) for
            flagging a knowledge boundary.
        source_quality_peer_reviewed: Quality score for peer-reviewed sources.
        source_quality_preprint: Quality score for preprints.
        source_quality_gray: Quality score for gray literature.
        source_quality_anecdotal: Quality score for anecdotal sources.
        retraction_penalty: Penalty subtracted from source quality when
            a source is retracted.
    """

    enabled: bool = True
    min_confidence_for_acceptance: float = Field(default=0.3, ge=0.0, le=1.0)
    contradiction_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    boundary_confidence_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    source_quality_peer_reviewed: float = Field(default=0.9, ge=0.0, le=1.0)
    source_quality_preprint: float = Field(default=0.6, ge=0.0, le=1.0)
    source_quality_gray: float = Field(default=0.3, ge=0.0, le=1.0)
    source_quality_anecdotal: float = Field(default=0.1, ge=0.0, le=1.0)
    retraction_penalty: float = Field(default=-0.5, le=0.0)


class SourceGroundingConfig(BaseModel):
    """Configuration for source grounding and citation verification.

    Attributes:
        enabled: Whether source grounding checks are active.
        require_citations: Whether every factual claim must cite at least
            one source.
        verify_retraction_status: Whether to check retraction databases
            when verifying sources.
        min_sources_per_claim: Minimum verified sources required per claim.
        max_citation_age_years: Maximum acceptable citation age.
        allow_unsupported_claims: If True, flag unsupported claims but
            do not block them.
        check_support_level: Whether to distinguish between SUPPORTS and
            NEUTRAL citation relationships.
        extraction_enabled: Whether citation extraction from text is active.
    """

    enabled: bool = True
    require_citations: bool = True
    verify_retraction_status: bool = True
    min_sources_per_claim: int = Field(default=1, ge=0)
    max_citation_age_years: int = Field(default=20, gt=0)
    allow_unsupported_claims: bool = False
    check_support_level: bool = True
    extraction_enabled: bool = True


class VerificationAsymmetryConfig(BaseModel):
    """Configuration for verification asymmetry tracking and reporting.

    Attributes:
        enabled: Whether asymmetry tracking is active.
        db_path: Filesystem path for the asymmetry tracking SQLite DB.
        max_asymmetry_gap: Maximum allowed gap between claim confidence
            and verification score (0-1) before flagging.
        require_citation_verification: If True, only compute asymmetry
            for claims with verified citations.
        flag_severity: Default severity for asymmetry flags.
    """

    enabled: bool = True
    db_path: str = "data/verification_asymmetry.db"
    max_asymmetry_gap: float = Field(default=0.4, ge=0.0, le=1.0)
    require_citation_verification: bool = True
    flag_severity: str = "warn"


class ConfabulationConfig(BaseModel):
    """Configuration for confabulation detection and hallucination tracking.

    Attributes:
        enabled: Whether confabulation detection is active.
        claim_vs_literature_threshold: Minimum Jaccard overlap (0-1) between
            a claim and known literature before flagging as unsupported.
        boundary_confidence_threshold: Confidence threshold (0-1) below which
            a flagged claim gets a KnowledgeBoundaryFlag attached.
        domain_hallucination_threshold: Flag rate threshold (0-1) for a domain
            that triggers auto-escalation.
        db_path: Filesystem path for the hallucination tracking SQLite DB.
        tracking_enabled: Whether historical hallucination tracking is active.
    """

    enabled: bool = True
    claim_vs_literature_threshold: float = Field(default=0.05, ge=0.0, le=1.0)
    boundary_confidence_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    domain_hallucination_threshold: float = Field(default=0.15, ge=0.0, le=1.0)
    db_path: str = "data/confabulation.db"
    tracking_enabled: bool = True


class SandboxConfig(BaseModel):
    """Configuration for sandboxed code execution.

    Attributes:
        time_limit: Maximum execution time in seconds.
        memory_limit_mb: Memory limit in megabytes.
        network_access: Whether sandbox has network access.
    """

    time_limit: int = Field(default=30, gt=0)
    memory_limit_mb: int = Field(default=1024, gt=0)
    network_access: bool = False


class Config(BaseSettings):
    """Central configuration manager for the openSciRe ecosystem.

    Loads from YAML/TOML files and env vars (OPENSCIRE_ prefix).
    Manages model, provenance, logging, literature, ethics, sandbox,
    falsification, and agent diversity sub-configurations.
    """

    model_config = SettingsConfigDict(
        env_prefix="OPENSCIRE_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        frozen=False,
    )

    model: ModelConfig = ModelConfig()
    provenance: ProvenanceConfig = ProvenanceConfig()
    logging: LoggingConfig = LoggingConfig()
    literature: LiteratureConfig = LiteratureConfig()
    ethics: EthicsConfig = EthicsConfig()
    uncertainty: UncertaintyConfig = UncertaintyConfig()
    source_grounding: SourceGroundingConfig = SourceGroundingConfig()
    verification_asymmetry: VerificationAsymmetryConfig = VerificationAsymmetryConfig()
    confabulation: ConfabulationConfig = ConfabulationConfig()
    sandbox: SandboxConfig = SandboxConfig()
    falsification: FalsificationConfig = FalsificationConfig()
    agent_diversity: AgentDiversityConfig = AgentDiversityConfig()
    _secrets: dict[str, SecretStr] = {}

    def load_file(self, path: str | Path) -> None:
        """Load configuration from a YAML or TOML file.

        Args:
            path: Path to the config file (.yaml, .yml, or .toml).

        Raises:
            FileNotFoundError: If the file does not exist.
            ConfigError: If the format is unsupported or content is invalid.
        """
        path = Path(path)
        if not path.exists():
            msg = f"Config file not found: {path}"
            raise FileNotFoundError(msg)

        raw = path.read_text(encoding="utf-8")

        if path.suffix in {".yaml", ".yml"}:
            data = yaml.safe_load(raw)
        elif path.suffix == ".toml":
            data = tomllib.loads(raw)
        else:
            msg = f"Unsupported config file format: {path.suffix}. Use .yaml, .yml, or .toml"
            raise ConfigError(msg, source="config", error_code=ErrorCode.CONFIG_INVALID)

        if not isinstance(data, dict):
            msg = f"Config file must contain a top-level mapping, got {type(data).__name__}"
            raise ConfigError(msg, source="config", error_code=ErrorCode.CONFIG_INVALID)

        for section, values in data.items():
            if hasattr(self, section) and isinstance(values, dict):
                current = getattr(self, section)
                for key, val in values.items():
                    if hasattr(current, key):
                        setattr(current, key, val)

    def set_secret(self, key: str, value: str) -> None:
        """Store a secret value in memory (redacted from dump output).

        Args:
            key: Identifier for the secret.
            value: The secret value to store.
        """
        self._secrets[key] = SecretStr(value)

    def get_secret(self, key: str) -> str | None:
        """Retrieve a previously stored secret value.

        Args:
            key: Identifier for the secret.

        Returns:
            The secret value, or None if not found.
        """
        if key in self._secrets:
            return self._secrets[key].get_secret_value()
        return None

    def to_reproducibility_bundle(self) -> ReproducibilityBundle:
        """Snapshot current environment for reproducibility.

        Captures pip freeze output, dependency tree, config snapshot,
        and hardware profile into a ReproducibilityBundle.

        Returns:
            A ReproducibilityBundle with environment and config state.
        """
        pip_freeze = ""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "freeze"],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if result.returncode == 0:
                pip_freeze = result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pip_freeze = "# pip freeze failed"

        dep_tree: dict[str, str] = {}
        for line in pip_freeze.strip().split("\n"):
            if "==" in line:
                parts = line.split("==", 1)
                dep_tree[parts[0].strip()] = parts[1].strip()

        config_snapshot: dict[str, object] = self.model_dump(mode="python")
        config_snapshot.pop("_secrets", None)

        return ReproducibilityBundle(
            environment_lockfile=pip_freeze,
            dependency_tree=dep_tree,
            config_snapshot=config_snapshot,
            hardware_profile=_capture_hardware(),
        )

    def redacted_dump(self) -> dict[str, object]:
        """Dump configuration with secrets replaced by ``***REDACTED***``.

        Returns:
            Dict of config values safe for logging or display.
        """
        dump: dict[str, object] = self.model_dump(mode="python")
        if self._secrets:
            for key in self._secrets:
                dump[key] = "***REDACTED***"
        return dump

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        """Return the JSON Schema for the Config model.

        Returns:
            JSON Schema dict describing all config fields.
        """
        return cls.model_json_schema()


def _capture_hardware() -> str:
    parts: list[str] = []
    try:
        import platform

        parts.append(f"python={platform.python_version()}")
        parts.append(f"system={platform.system()}")
        parts.append(f"machine={platform.machine()}")
    except ImportError:
        pass
    try:
        cpu = os.cpu_count()
        if cpu is not None:
            parts.append(f"cpu_count={cpu}")
    except OSError:
        pass
    return "; ".join(parts)

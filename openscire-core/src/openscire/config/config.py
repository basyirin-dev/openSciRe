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

from openscire.constants import ErrorCode
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
    """Configuration for ethical safeguards and resource accounting.

    Attributes:
        firewall_mode: Action on ethics violation (flag, warn, block, escalate).
        carbon_budget_monthly_kwh: Monthly carbon budget in kWh.
    """

    firewall_mode: str = Field(default="warn")
    carbon_budget_monthly_kwh: float = Field(default=50.0, ge=0.0)

    @field_validator("firewall_mode")
    @classmethod
    def _validate_firewall_mode(cls, v: str) -> str:
        allowed = {"flag", "warn", "block", "escalate"}
        if v.lower() not in allowed:
            msg = f"firewall_mode must be one of {allowed}"
            raise ConfigError(msg, source="config", error_code=ErrorCode.CONFIG_INVALID)
        return v.lower()


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

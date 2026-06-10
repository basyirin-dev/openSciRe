# SPDX-License-Identifier: Apache-2.0

"""Pydantic models for sandboxed code execution results and environment."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from openscire.models import ReproducibilityBundle


class SandboxExitReason(StrEnum):
    completed = "completed"
    time_limit = "time_limit"
    memory_limit = "memory_limit"
    internal_error = "internal_error"


class ExecutionResult(BaseModel):
    """Result of a sandboxed code execution."""

    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    execution_time_ms: int = 0
    memory_peak_mb: float = 0.0
    sandbox_exit_reason: SandboxExitReason = SandboxExitReason.completed
    provenance_entry_id: str = ""
    reproducibility_bundle: ReproducibilityBundle = Field(default_factory=ReproducibilityBundle)


class SandboxEnvironment(BaseModel):
    """Snapshot of the environment at execution time."""

    pip_freeze: str = ""
    python_version: str = ""
    cpu_info: str = ""
    kernel_version: str = ""
    execution_timestamp: datetime = Field(default_factory=datetime.now)


class StaticAnalysisResult(BaseModel):
    """Result of static analysis on sandbox code."""

    dangerous_imports_found: list[str] = Field(default_factory=list)
    filesystem_access_patterns: list[str] = Field(default_factory=list)
    network_calls: list[str] = Field(default_factory=list)
    allowed: bool = True
    reason: str = ""

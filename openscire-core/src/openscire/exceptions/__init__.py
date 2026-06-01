# SPDX-License-Identifier: Apache-2.0

"""Exception hierarchy for openSciRe.

Defines structured, provenance-aware error types for all subsystems,
with support for error codes and source attribution.
"""

from openscire.exceptions.exceptions import (
    ConfigError,
    EthicsError,
    KeyManagementError,
    ModelProviderError,
    ProvenanceError,
    ValidationError,
    openSciReError,
)

__all__ = [
    "openSciReError",
    "ProvenanceError",
    "ConfigError",
    "ConfigError",
    "KeyManagementError",
    "ModelProviderError",
    "EthicsError",
    "ValidationError",
]

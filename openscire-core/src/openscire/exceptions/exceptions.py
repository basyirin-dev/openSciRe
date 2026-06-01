# SPDX-License-Identifier: Apache-2.0

"""Exception hierarchy for openSciRe with structured error codes."""

from datetime import datetime, timezone

from openscire.constants import ErrorCode


class openSciReError(Exception):  # noqa: N801
    """Base exception for all openSciRe errors.

    Carries an error code, human-readable message, source component,
    and UTC timestamp for structured error handling.
    """

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.ERR_BASE,
        message: str = "",
        source: str = "",
    ) -> None:
        self.error_code = error_code
        self.message = message
        self.source = source
        self.timestamp = datetime.now(timezone.utc)  # noqa: UP017
        msg = f"[{error_code}] {message}" if message else f"[{error_code}]"
        super().__init__(msg)


class ProvenanceError(openSciReError):
    """Raised when provenance chain integrity is violated."""

    def __init__(
        self,
        message: str = "",
        source: str = "",
        error_code: ErrorCode = ErrorCode.PROV_CHAIN_BREAK,
    ) -> None:
        super().__init__(error_code=error_code, message=message, source=source)


class ConfigError(openSciReError):
    """Raised when configuration is invalid or missing required fields."""

    def __init__(
        self,
        message: str = "",
        source: str = "",
        error_code: ErrorCode = ErrorCode.CONFIG_INVALID,
    ) -> None:
        super().__init__(error_code=error_code, message=message, source=source)


class ModelProviderError(openSciReError):
    """Raised on LLM provider connection, auth, rate-limit, or capability failures."""

    def __init__(
        self,
        message: str = "",
        source: str = "",
        error_code: ErrorCode = ErrorCode.MODEL_CONNECTION_FAILURE,
    ) -> None:
        super().__init__(error_code=error_code, message=message, source=source)


class EthicsError(openSciReError):
    """Raised when ethical guardrails (DURC, sovereignty) are triggered."""

    def __init__(
        self,
        message: str = "",
        source: str = "",
        error_code: ErrorCode = ErrorCode.ETHICS_DURC_FLAG,
    ) -> None:
        super().__init__(error_code=error_code, message=message, source=source)


class ValidationError(openSciReError):
    """Raised when claims, evidence, or citations fail validation checks."""

    def __init__(
        self,
        message: str = "",
        source: str = "",
        error_code: ErrorCode = ErrorCode.VALIDATION_CLAIM_INVALID,
    ) -> None:
        super().__init__(error_code=error_code, message=message, source=source)


class KeyManagementError(openSciReError):
    """Raised on BYOK key management failures (missing passphrase, crypto errors)."""

    def __init__(
        self,
        message: str = "",
        source: str = "",
        error_code: ErrorCode = ErrorCode.CONFIG_KEY_MANAGEMENT,
    ) -> None:
        super().__init__(error_code=error_code, message=message, source=source)

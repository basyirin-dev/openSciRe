# SPDX-License-Identifier: Apache-2.0

"""Scientific-grade logging with structured output and secret redaction."""

import logging
import re
import sys
from collections.abc import MutableMapping
from contextvars import ContextVar
from typing import Any

import structlog

from openscire.config import LoggingConfig as _LoggingConfig

SCIENCE_LEVEL_NUM = 25
logging.addLevelName(SCIENCE_LEVEL_NUM, "SCIENCE")
structlog.stdlib.NAME_TO_LEVEL["SCIENCE"] = SCIENCE_LEVEL_NUM  # type: ignore[attr-defined]
structlog.stdlib.LEVEL_TO_NAME[SCIENCE_LEVEL_NUM] = "SCIENCE"  # type: ignore[attr-defined]


_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"api_key", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"passwd", re.IGNORECASE),
    re.compile(r"credential", re.IGNORECASE),
    re.compile(r"auth", re.IGNORECASE),
]


class LogContext:
    """Context variable manager for per-request logging metadata.

    Tracks provenance entry IDs, request IDs, session IDs, and agent IDs
    using contextvars for thread-safe, async-safe correlation.
    """

    _provenance_entry_id: ContextVar[str | None] = ContextVar("_provenance_entry_id", default=None)
    _request_id: ContextVar[str | None] = ContextVar("_request_id", default=None)
    _session_id: ContextVar[str | None] = ContextVar("_session_id", default=None)
    _agent_id: ContextVar[str | None] = ContextVar("_agent_id", default=None)

    @classmethod
    def set_provenance_entry_id(cls, value: str | None) -> None:
        """Set the provenance entry ID for the current context.

        Args:
            value: Provenance entry identifier.
        """
        cls._provenance_entry_id.set(value)

    @classmethod
    def get_provenance_entry_id(cls) -> str | None:
        """Get the provenance entry ID for the current context.

        Returns:
            The current provenance entry ID, or None.
        """
        return cls._provenance_entry_id.get()

    @classmethod
    def set_request_id(cls, value: str | None) -> None:
        """Set the request ID for the current context.

        Args:
            value: Request identifier.
        """
        cls._request_id.set(value)

    @classmethod
    def set_session_id(cls, value: str | None) -> None:
        """Set the session ID for the current context.

        Args:
            value: Session identifier.
        """
        cls._session_id.set(value)

    @classmethod
    def set_agent_id(cls, value: str | None) -> None:
        """Set the agent ID for the current context.

        Args:
            value: Agent identifier.
        """
        cls._agent_id.set(value)

    @classmethod
    def get_context_dict(cls) -> dict[str, str | None]:
        """Return all context variables as a dict for log injection.

        Returns:
            Dict with keys provenance_entry_id, request_id, session_id, agent_id.
        """
        return {
            "provenance_entry_id": cls._provenance_entry_id.get(),
            "request_id": cls._request_id.get(),
            "session_id": cls._session_id.get(),
            "agent_id": cls._agent_id.get(),
        }


def _add_science_level(
    _logger: Any,  # noqa: ANN401
    method_name: str,
    event_dict: MutableMapping[str, Any],  # noqa: ANN401
) -> MutableMapping[str, Any]:
    if method_name == "science":
        event_dict["level"] = SCIENCE_LEVEL_NUM
        event_dict["level_name"] = "SCIENCE"
    return event_dict


def _add_context_processor(
    _logger: Any,  # noqa: ANN401
    _method_name: str,
    event_dict: MutableMapping[str, Any],  # noqa: ANN401
) -> MutableMapping[str, Any]:
    ctx = LogContext.get_context_dict()
    for key, val in ctx.items():
        if val is not None:
            event_dict.setdefault(key, val)
    return event_dict


def _redact_processor(
    _logger: Any,  # noqa: ANN401
    _method_name: str,
    event_dict: MutableMapping[str, Any],  # noqa: ANN401
) -> MutableMapping[str, Any]:
    redacted: MutableMapping[str, Any] = {}
    for key, val in event_dict.items():
        if any(p.search(key) for p in _SECRET_PATTERNS):
            redacted[key] = "***REDACTED***"
        else:
            redacted[key] = val
    return redacted


def science(self: structlog.stdlib.BoundLogger, event: str, **kw: object) -> object:
    return self._proxy_to_logger("science", event, **kw)


structlog.stdlib.BoundLogger.science = science  # type: ignore[attr-defined]


def configure(config: _LoggingConfig | None = None) -> None:
    """Configure structlog with processors, handlers, and formatters.

    Supports stdout, stderr, file, and syslog output. Injects context
    variables and redacts sensitive keys (api_key, token, secret, etc.).

    Args:
        config: LoggingConfig instance; falls back to Config().logging if None.
    """
    if config is None:
        from openscire.config import Config

        config = Config().logging

    stdlib_handler: logging.Handler
    if config.output == "syslog":
        from logging.handlers import SysLogHandler

        stdlib_handler = SysLogHandler(address="/dev/log")
    elif config.output == "file":
        stdlib_handler = logging.FileHandler(config.log_file, encoding="utf-8")
    elif config.output == "stderr":
        stdlib_handler = logging.StreamHandler(sys.stderr)
    else:
        stdlib_handler = logging.StreamHandler(sys.stdout)

    stdlib_handler.setLevel(_level_from_name(config.level))

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            _add_context_processor,
            _redact_processor,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            _add_science_level,
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )

    stdlib_handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.addHandler(stdlib_handler)
    root_logger.setLevel(_level_from_name(config.level))


def _level_from_name(name: str) -> int:
    if name.upper() == "SCIENCE":
        return SCIENCE_LEVEL_NUM
    return getattr(logging, name.upper(), logging.INFO)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structlog BoundLogger with openSciRe processors already configured.

    Args:
        name: Logger name, typically ``__name__``.

    Returns:
        A configured structlog BoundLogger.
    """
    return structlog.get_logger(name)  # type: ignore[no-any-return]

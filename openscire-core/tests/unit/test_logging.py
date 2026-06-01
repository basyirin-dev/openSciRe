# SPDX-License-Identifier: Apache-2.0

import logging
import re

from openscire.logging.logging import (
    SCIENCE_LEVEL_NUM,
    LogContext,
    _add_context_processor,
    _add_science_level,
    _level_from_name,
    _redact_processor,
    configure,
    get_logger,
)


class TestScienceLevel:
    def test_level_number(self) -> None:
        assert SCIENCE_LEVEL_NUM == 25

    def test_level_registered_with_logging(self) -> None:
        assert logging.getLevelName(SCIENCE_LEVEL_NUM) == "SCIENCE"

    def test_get_logger_returns_logger(self) -> None:
        logger = get_logger("test_logger")
        assert logger is not None

    def test_level_from_name_science(self) -> None:
        assert _level_from_name("SCIENCE") == SCIENCE_LEVEL_NUM

    def test_level_from_name_info(self) -> None:
        assert _level_from_name("INFO") == logging.INFO

    def test_level_from_name_debug(self) -> None:
        assert _level_from_name("DEBUG") == logging.DEBUG

    def test_level_from_name_unknown_defaults_to_info(self) -> None:
        assert _level_from_name("NONEXISTENT") == logging.INFO

    def test_level_from_name_lowercase(self) -> None:
        assert _level_from_name("warning") == logging.WARNING


class TestLogContext:
    def test_set_and_get_provenance_entry_id(self) -> None:
        LogContext.set_provenance_entry_id("entry_123")
        assert LogContext.get_provenance_entry_id() == "entry_123"

    def test_get_provenance_entry_id_default(self) -> None:
        LogContext.set_provenance_entry_id(None)
        assert LogContext.get_provenance_entry_id() is None

    def test_set_request_id(self) -> None:
        LogContext.set_request_id("req_abc")
        ctx = LogContext.get_context_dict()
        assert ctx["request_id"] == "req_abc"

    def test_set_session_id(self) -> None:
        LogContext.set_session_id("sess_xyz")
        ctx = LogContext.get_context_dict()
        assert ctx["session_id"] == "sess_xyz"

    def test_set_agent_id(self) -> None:
        LogContext.set_agent_id("agent_007")
        ctx = LogContext.get_context_dict()
        assert ctx["agent_id"] == "agent_007"

    def test_context_dict_all_default(self) -> None:
        LogContext.set_provenance_entry_id(None)
        LogContext.set_request_id(None)
        LogContext.set_session_id(None)
        LogContext.set_agent_id(None)
        ctx = LogContext.get_context_dict()
        assert ctx == {
            "provenance_entry_id": None,
            "request_id": None,
            "session_id": None,
            "agent_id": None,
        }

    def test_context_dict_partial(self) -> None:
        LogContext.set_provenance_entry_id("e1")
        LogContext.set_request_id(None)
        LogContext.set_session_id("s1")
        LogContext.set_agent_id(None)
        ctx = LogContext.get_context_dict()
        assert ctx["provenance_entry_id"] == "e1"
        assert ctx["session_id"] == "s1"
        assert ctx["request_id"] is None
        assert ctx["agent_id"] is None

    def test_context_isolation(self) -> None:
        LogContext.set_provenance_entry_id("outer")
        ctx1 = LogContext.get_context_dict()

        LogContext.set_provenance_entry_id("inner")
        ctx2 = LogContext.get_context_dict()

        assert ctx1["provenance_entry_id"] == "outer"
        assert ctx2["provenance_entry_id"] == "inner"


class TestAddScienceLevel:
    def test_adds_science_level(self) -> None:
        event: dict[str, object] = {}
        result = _add_science_level(None, "science", event)
        assert result["level"] == SCIENCE_LEVEL_NUM
        assert result["level_name"] == "SCIENCE"

    def test_passthrough_non_science(self) -> None:
        event: dict[str, object] = {"level": 20, "level_name": "INFO"}
        result = _add_science_level(None, "info", event)
        assert result["level"] == 20
        assert result["level_name"] == "INFO"


class TestAddContextProcessor:
    def test_adds_context_when_set(self) -> None:
        LogContext.set_agent_id("test_agent")
        event: dict[str, object] = {}
        result = _add_context_processor(None, "info", event)
        assert result["agent_id"] == "test_agent"

    def test_skips_none_context_values(self) -> None:
        LogContext.set_agent_id(None)
        event: dict[str, object] = {}
        result = _add_context_processor(None, "info", event)
        assert "agent_id" not in result

    def test_does_not_overwrite_existing_keys(self) -> None:
        LogContext.set_request_id("ctx_val")
        event: dict[str, object] = {"request_id": "existing_val"}
        result = _add_context_processor(None, "info", event)
        assert result["request_id"] == "existing_val"


class TestRedactProcessor:
    def test_redacts_api_key(self) -> None:
        event: dict[str, object] = {"api_key": "sk-12345", "message": "hello"}
        result = _redact_processor(None, "info", event)
        assert result["api_key"] == "***REDACTED***"
        assert result["message"] == "hello"

    def test_redacts_token(self) -> None:
        event: dict[str, object] = {"auth_token": "abcd", "data": "ok"}
        result = _redact_processor(None, "info", event)
        assert result["auth_token"] == "***REDACTED***"

    def test_redacts_secret(self) -> None:
        event: dict[str, object] = {"secret_key": "s3cr3t"}
        result = _redact_processor(None, "info", event)
        assert result["secret_key"] == "***REDACTED***"

    def test_redacts_password(self) -> None:
        event: dict[str, object] = {"password": "p@ss"}
        result = _redact_processor(None, "info", event)
        assert result["password"] == "***REDACTED***"

    def test_redacts_passwd(self) -> None:
        event: dict[str, object] = {"passwd": "p@ss"}
        result = _redact_processor(None, "info", event)
        assert result["passwd"] == "***REDACTED***"

    def test_redacts_credential(self) -> None:
        event: dict[str, object] = {"credential": "secret"}
        result = _redact_processor(None, "info", event)
        assert result["credential"] == "***REDACTED***"

    def test_redacts_auth(self) -> None:
        event: dict[str, object] = {"auth": "bearer_token"}
        result = _redact_processor(None, "info", event)
        assert result["auth"] == "***REDACTED***"

    def test_redact_case_insensitive(self) -> None:
        event: dict[str, object] = {"API_KEY": "sk-12345"}
        result = _redact_processor(None, "info", event)
        assert result["API_KEY"] == "***REDACTED***"

    def test_no_redact_safe_keys(self) -> None:
        event: dict[str, object] = {"message": "hello", "level": 20}
        result = _redact_processor(None, "info", event)
        assert result["message"] == "hello"
        assert result["level"] == 20


class TestConfigure:
    def test_configure_stdout(self) -> None:
        from openscire.config import LoggingConfig

        cfg = LoggingConfig(level="DEBUG", output="stdout")
        configure(cfg)
        logger = get_logger("test_configure_stdout")
        logger.info("stdout test", extra_field="ok")

    def test_configure_stderr(self) -> None:
        from openscire.config import LoggingConfig

        cfg = LoggingConfig(level="INFO", output="stderr")
        configure(cfg)
        logger = get_logger("test_configure_stderr")
        logger.info("stderr test")

    def test_configure_file(self, tmp_path: object) -> None:
        from openscire.config import LoggingConfig

        log_file = tmp_path / "test.log"
        cfg = LoggingConfig(level="DEBUG", output="file", log_file=str(log_file))
        configure(cfg)
        logger = get_logger("test_configure_file")
        logger.info("file test")
        assert log_file.exists()

    def test_science_level_config(self) -> None:
        from openscire.config import LoggingConfig

        cfg = LoggingConfig(level="SCIENCE", output="stderr")
        configure(cfg)
        logger = get_logger("test_science_cfg")
        logger.info("science level test")

    def test_configure_without_config(self) -> None:
        configure()
        logger = get_logger("test_no_config_file")
        logger.info("no config test")

    def test_context_vars_in_log_output(self) -> None:
        from openscire.config import LoggingConfig

        cfg = LoggingConfig(level="DEBUG", output="stderr")
        configure(cfg)
        LogContext.set_agent_id("agent_context_test")
        LogContext.set_request_id("req_context_test")
        logger = get_logger("test_context_vars_log")
        logger.info("context test")


class TestSecretPatterns:
    def test_all_patterns_compile(self) -> None:
        from openscire.logging.logging import _SECRET_PATTERNS

        assert len(_SECRET_PATTERNS) == 7
        for p in _SECRET_PATTERNS:
            assert isinstance(p, re.Pattern)

    def test_pattern_matches_keywords(self) -> None:
        from openscire.logging.logging import _SECRET_PATTERNS

        test_cases = {
            "api_key": ["api_key", "API_KEY", "my_api_key"],
            "token": ["token", "auth_token", "TOKEN"],
            "secret": ["secret", "secret_key", "SECRET"],
            "password": ["password", "PASSWORD"],
            "passwd": ["passwd", "PASSWD"],
            "credential": ["credential", "CREDENTIAL"],
            "auth": ["auth", "AUTH", "authorization"],
        }
        for keyword, examples in test_cases.items():
            matching = [p for p in _SECRET_PATTERNS if keyword in p.pattern.lower()]
            assert matching, f"No pattern for keyword: {keyword}"
            for example in examples:
                assert matching[0].search(example), (
                    f"Pattern {matching[0].pattern} should match {example}"
                )

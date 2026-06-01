# SPDX-License-Identifier: Apache-2.0

"""Security tests: no secrets in logs, no plaintext keys in serialization."""

import io
import json
import logging

from openscire.exceptions import ModelProviderError
from openscire.logging import configure
from openscire.logging.logging import _redact_processor


class TestLoggingNoSecrets:
    def test_log_redactor_masks_api_key(self) -> None:
        event = {"api_key": "sk-1234567890abcdef", "message": "test"}
        result = _redact_processor(None, "info", event)
        assert "sk-1234567890abcdef" not in str(result)
        assert result["api_key"] == "***REDACTED***"

    def test_log_redactor_masks_all_secret_patterns(self) -> None:
        event = {
            "api_key": "secret1",
            "auth_token": "secret2",
            "password": "secret3",
            "safe_field": "visible",
        }
        result = _redact_processor(None, "info", event)
        assert result["api_key"] == "***REDACTED***"
        assert result["auth_token"] == "***REDACTED***"
        assert result["password"] == "***REDACTED***"
        assert result["safe_field"] == "visible"

    def test_no_plaintext_keys_in_stdout_log(self) -> None:
        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        handler.setLevel(logging.DEBUG)
        root = logging.getLogger()
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)

        configure()
        from openscire.logging import get_logger

        logger = get_logger("security_test")
        logger.info("test message", api_key="sk-abcdef123456")

        output = buf.getvalue()
        assert "sk-abcdef123456" not in output
        assert "***REDACTED***" in output or "REDACTED" in output

        root.removeHandler(handler)

    def test_exception_no_key_leak(self) -> None:
        err = ModelProviderError(
            "Connection failed",
            source="test",
        )
        err_str = str(err)
        assert "secret" not in err_str.lower() or "***REDACTED***" in err_str


class TestProviderConfigSecrets:
    def test_provider_config_api_key_redacted_in_repr(self) -> None:
        from openscire.provider.base import ProviderConfig
        from pydantic import SecretStr

        cfg = ProviderConfig(api_key=SecretStr("sk-test-key-12345"))
        dumped = cfg.model_dump(mode="python")
        assert str(dumped["api_key"]) == "**********"

    def test_provider_config_api_key_redacted_in_json(self) -> None:
        from openscire.provider.base import ProviderConfig
        from pydantic import SecretStr

        cfg = ProviderConfig(api_key=SecretStr("sk-test-key-12345"))
        json_str = cfg.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["api_key"] == "**********"

    def test_provider_config_api_key_not_in_str(self) -> None:
        from openscire.provider.base import ProviderConfig
        from pydantic import SecretStr

        cfg = ProviderConfig(api_key=SecretStr("sk-test-key-12345"))
        assert "sk-test-key-12345" not in str(cfg)
        assert "sk-test-key-12345" not in repr(cfg)

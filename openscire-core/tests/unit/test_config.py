# SPDX-License-Identifier: Apache-2.0


from openscire.config import Config
from openscire.exceptions import ConfigError


class TestConfigDefaults:
    def test_default_construction(self) -> None:
        cfg = Config()
        assert cfg.model.provider == "ollama"
        assert cfg.provenance.storage_backend == "sqlite"
        assert cfg.logging.level == "INFO"
        assert cfg.ethics.firewall_mode == "warn"
        assert cfg.sandbox.time_limit == 30
        assert cfg.falsification.enabled is True
        assert cfg.agent_diversity.serendipity_level == 0.4

    def test_redacted_dump(self) -> None:
        cfg = Config()
        dump = cfg.redacted_dump()
        assert "model" in dump
        assert "falsification" in dump
        assert "agent_diversity" in dump

    def test_json_schema(self) -> None:
        schema = Config.json_schema()
        assert "properties" in schema


class TestConfigValidators:
    def test_valid_log_levels(self) -> None:
        for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "SCIENCE"):
            c = Config()
            c.logging.level = level
            assert c.logging.level == level

    def test_valid_log_outputs(self) -> None:
        for out in ("stdout", "stderr", "file", "syslog"):
            c = Config()
            c.logging.output = out
            assert c.logging.output == out

    def test_valid_firewall_modes(self) -> None:
        for mode in ("flag", "warn", "block", "escalate"):
            c = Config()
            c.ethics.firewall_mode = mode
            assert c.ethics.firewall_mode == mode

    def test_field_constraints(self) -> None:
        c = Config()
        c.model.temperature = 1.5
        assert c.model.temperature == 1.5
        c.model.max_tokens = 8192
        assert c.model.max_tokens == 8192


class TestConfigEnvOverrides:
    def test_env_override_simple(self, monkeypatch: object) -> None:
        monkeypatch.setenv("OPENSCIRE_MODEL__PROVIDER", "anthropic")  # type: ignore
        cfg = Config()
        assert cfg.model.provider == "anthropic"

    def test_env_override_nested(self, monkeypatch: object) -> None:
        monkeypatch.setenv("OPENSCIRE_FALSIFICATION__ENABLED", "false")  # type: ignore
        cfg = Config()
        assert cfg.falsification.enabled is False

    def test_env_override_serendipity(self, monkeypatch: object) -> None:
        monkeypatch.setenv("OPENSCIRE_AGENT_DIVERSITY__SERENDIPITY_LEVEL", "0.9")  # type: ignore
        cfg = Config()
        assert cfg.agent_diversity.serendipity_level == 0.9


class TestConfigFileParsing:
    def test_yaml_parse(self, tmp_path: object) -> None:
        path = tmp_path / "config.yaml"
        path.write_text("model:\n  provider: openai\n  temperature: 0.5\n")
        cfg = Config()
        cfg.load_file(str(path))
        assert cfg.model.provider == "openai"
        assert cfg.model.temperature == 0.5

    def test_toml_parse(self, tmp_path: object) -> None:
        path = tmp_path / "config.toml"
        path.write_text('[model]\nprovider = "anthropic"\ntemperature = 0.3\n')
        cfg = Config()
        cfg.load_file(str(path))
        assert cfg.model.provider == "anthropic"

    def test_file_not_found(self, tmp_path: object) -> None:
        cfg = Config()
        try:
            cfg.load_file(str(tmp_path / "nonexistent.yaml"))
            raise AssertionError()
        except FileNotFoundError:
            pass

    def test_unsupported_format(self, tmp_path: object) -> None:
        path = tmp_path / "config.txt"
        path.write_text("invalid")
        cfg = Config()
        try:
            cfg.load_file(str(path))
            raise AssertionError()
        except ConfigError:
            pass

    def test_non_dict_root(self, tmp_path: object) -> None:
        path = tmp_path / "config.yaml"
        path.write_text("- list\n- of\n- items\n")
        cfg = Config()
        try:
            cfg.load_file(str(path))
            raise AssertionError()
        except ConfigError:
            pass


class TestConfigSecrets:
    def test_set_and_get_secret(self) -> None:
        cfg = Config()
        cfg.set_secret("api_key", "sk-abc123")
        assert cfg.get_secret("api_key") == "sk-abc123"

    def test_get_unknown_secret(self) -> None:
        cfg = Config()
        assert cfg.get_secret("nonexistent") is None

    def test_redacted_dump_hides_secrets(self) -> None:
        cfg = Config()
        cfg.set_secret("api_key", "sk-secret")
        dump = cfg.redacted_dump()
        assert dump.get("api_key") == "***REDACTED***"


class TestConfigReproducibility:
    def test_to_reproducibility_bundle(self) -> None:
        cfg = Config()
        bundle = cfg.to_reproducibility_bundle()
        assert "pydantic" in bundle.dependency_tree
        assert isinstance(bundle.hardware_profile, str)

# SPDX-License-Identifier: Apache-2.0

"""Tests for the BYOK Config Module (Task 2.9)."""

from __future__ import annotations

from pathlib import Path

import openscire.config.byok as byok_mod
import pytest
from openscire.config.byok import (
    BYOKManager,
    BYOKProfile,
    CryptoEngine,
    EncryptedPayload,
    KeyManagementError,
    KeyStore,
)
from openscire.constants import ErrorCode
from pydantic import SecretStr, ValidationError

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect BYOK config dir to a temp path."""
    config_dir = tmp_path / ".config" / "openscire"
    config_dir.mkdir(parents=True)
    monkeypatch.setattr(byok_mod, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(byok_mod, "_PROFILES_PATH", config_dir / "byok.json")
    monkeypatch.setattr(byok_mod, "_PASSPHRASE_PATH", config_dir / "byok.pass")
    monkeypatch.setattr(byok_mod, "_KEYRING_AVAILABLE", False)
    return config_dir


@pytest.fixture
def passphrase() -> str:
    return "my-strong-passphrase-123!"


@pytest.fixture
def manager(passphrase: str, tmp_home: Path) -> BYOKManager:
    return BYOKManager(passphrase=passphrase)


# ── BYOKProfile tests ─────────────────────────────────────────────────────


class TestBYOKProfile:
    def test_create_profile(self) -> None:
        profile = BYOKProfile(
            profile_name="personal",
            provider_type="openai_compatible",
            base_url="https://api.openai.com/v1",
            model_id="gpt-4o",
            api_key=SecretStr("sk-test123"),
        )
        assert profile.profile_name == "personal"
        assert profile.api_key is not None
        assert profile.api_key.get_secret_value() == "sk-test123"

    def test_profile_name_validation(self) -> None:
        BYOKProfile(profile_name="valid-name_123")
        with pytest.raises(ValidationError):
            BYOKProfile(profile_name="")
        with pytest.raises(ValidationError):
            BYOKProfile(profile_name="name with spaces")
        with pytest.raises(ValidationError):
            BYOKProfile(profile_name="name/with/slashes")

    def test_profile_to_provider_config(self) -> None:
        profile = BYOKProfile(
            profile_name="test",
            provider_type="openai_compatible",
            base_url="https://api.example.com",
            model_id="test-model",
            custom_headers={"X-Custom": "value"},
            api_key=SecretStr("sk-test"),
        )
        pconfig = profile.to_provider_config()
        assert pconfig.base_url == "https://api.example.com"
        assert pconfig.default_model == "test-model"
        assert pconfig.extra_headers == {"X-Custom": "value"}
        assert pconfig.api_key is not None
        assert pconfig.api_key.get_secret_value() == "sk-test"

    def test_profile_defaults(self) -> None:
        profile = BYOKProfile(profile_name="defaults")
        assert profile.provider_type == "openai_compatible"
        assert profile.base_url == ""
        assert profile.model_id == ""
        assert profile.custom_headers == {}
        assert profile.api_key is None


# ── CryptoEngine tests ────────────────────────────────────────────────────


class TestCryptoEngine:
    def test_encrypt_decrypt_roundtrip(self, passphrase: str) -> None:
        payload = CryptoEngine.encrypt(passphrase, "sk-super-secret-key")
        decrypted = CryptoEngine.decrypt(passphrase, payload)
        assert decrypted == "sk-super-secret-key"

    def test_encrypt_empty_string(self, passphrase: str) -> None:
        payload = CryptoEngine.encrypt(passphrase, "")
        decrypted = CryptoEngine.decrypt(passphrase, payload)
        assert decrypted == ""

    def test_decrypt_wrong_passphrase(self, passphrase: str) -> None:
        payload = CryptoEngine.encrypt(passphrase, "secret-data")
        with pytest.raises(KeyManagementError):
            CryptoEngine.decrypt("wrong-passphrase", payload)

    def test_decrypt_wrong_passphrase_empty(self, passphrase: str) -> None:
        payload = CryptoEngine.encrypt(passphrase, "secret-data")
        with pytest.raises(KeyManagementError):
            CryptoEngine.decrypt("", payload)

    def test_encrypt_different_each_call(self, passphrase: str) -> None:
        p1 = CryptoEngine.encrypt(passphrase, "same-data")
        p2 = CryptoEngine.encrypt(passphrase, "same-data")
        assert p1.ciphertext != p2.ciphertext
        assert p1.salt != p2.salt
        assert p1.nonce != p2.nonce

    def test_encrypted_payload_fields(self, passphrase: str) -> None:
        payload = CryptoEngine.encrypt(passphrase, "test-key")
        assert payload.ciphertext
        assert payload.nonce
        assert payload.salt
        import base64

        assert len(base64.b64decode(payload.salt)) == 16
        assert len(base64.b64decode(payload.nonce)) in (12, 24)

    def test_payload_dict_roundtrip(self) -> None:
        original = EncryptedPayload(
            ciphertext="abc",
            nonce="def",
            salt="ghi",
        )
        d = original.to_dict()
        restored = EncryptedPayload.from_dict(d)
        assert restored.ciphertext == "abc"
        assert restored.nonce == "def"
        assert restored.salt == "ghi"

    def test_long_api_key_roundtrip(self, passphrase: str) -> None:
        long_key = "sk-" + "a" * 200
        payload = CryptoEngine.encrypt(passphrase, long_key)
        decrypted = CryptoEngine.decrypt(passphrase, payload)
        assert decrypted == long_key


# ── KeyStore tests ────────────────────────────────────────────────────────


class TestKeyStore:
    def test_store_retrieve_file_fallback(self, tmp_home: Path, passphrase: str) -> None:
        KeyStore.store_passphrase(passphrase)
        retrieved = KeyStore.retrieve_passphrase()
        assert retrieved == passphrase

    def test_file_fallback_permissions(self, tmp_home: Path, passphrase: str) -> None:
        KeyStore.store_passphrase(passphrase)
        assert byok_mod._PASSPHRASE_PATH.exists()
        mode = byok_mod._PASSPHRASE_PATH.stat().st_mode
        assert mode & 0o777 == 0o600

    def test_retrieve_no_passphrase(self, tmp_home: Path) -> None:
        retrieved = KeyStore.retrieve_passphrase()
        assert retrieved is None

    def test_clear_passphrase_removes_file(self, tmp_home: Path, passphrase: str) -> None:
        KeyStore.store_passphrase(passphrase)
        assert byok_mod._PASSPHRASE_PATH.exists()
        KeyStore.clear_passphrase()
        assert not byok_mod._PASSPHRASE_PATH.exists()

    def test_clear_when_not_exists(self, tmp_home: Path) -> None:
        assert KeyStore.clear_passphrase() is True

    def test_keyring_fallback_order(
        self,
        tmp_home: Path,
        passphrase: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        stored: list[tuple[str, str, str]] = []

        def mock_set(service: str, account: str, value: str) -> None:
            stored.append((service, account, value))

        def mock_get(service: str, account: str) -> str | None:
            for s, a, v in stored:
                if s == service and a == account:
                    return v
            return None

        def mock_delete(service: str, account: str) -> None:
            stored.clear()

        monkeypatch.setattr(byok_mod, "_KEYRING_AVAILABLE", True)
        mock_keyring = type("MockKeyring", (), {})()
        mock_keyring.set_password = mock_set
        mock_keyring.get_password = mock_get
        mock_keyring.delete_password = mock_delete
        monkeypatch.setattr(byok_mod, "_keyring", mock_keyring)

        KeyStore.store_passphrase(passphrase)
        assert ("openscire-byok", "master", passphrase) in stored
        retrieved = KeyStore.retrieve_passphrase()
        assert retrieved == passphrase
        KeyStore.clear_passphrase()
        assert not stored


# ── BYOKManager tests ─────────────────────────────────────────────────────


class TestBYOKManager:
    def test_initialize_passphrase(self, tmp_home: Path) -> None:
        mgr = BYOKManager(passphrase="init-phrase")
        assert mgr._passphrase == "init-phrase"

    def test_no_passphrase_raises(self, tmp_home: Path) -> None:
        with pytest.raises(KeyManagementError) as exc:
            BYOKManager()
        assert ErrorCode.CONFIG_KEY_MANAGEMENT in str(exc.value)

    def test_create_and_get_profile(self, manager: BYOKManager) -> None:
        profile = manager.create_profile(
            name="personal",
            provider_type="anthropic",
            base_url="https://api.anthropic.com",
            model_id="claude-sonnet-4",
            api_key="sk-ant-test123",
        )
        assert profile.profile_name == "personal"
        assert profile.provider_type == "anthropic"
        assert profile.api_key is not None
        assert profile.api_key.get_secret_value() == "sk-ant-test123"

        loaded = manager.get_profile("personal")
        assert loaded is not None
        assert loaded.profile_name == "personal"
        assert loaded.api_key is not None
        assert loaded.api_key.get_secret_value() == "sk-ant-test123"

    def test_get_nonexistent_profile(self, manager: BYOKManager) -> None:
        result = manager.get_profile("nonexistent")
        assert result is None

    def test_list_profiles(self, manager: BYOKManager) -> None:
        manager.create_profile(name="alpha", api_key="k1")
        manager.create_profile(name="beta", api_key="k2")
        assert set(manager.list_profiles()) == {"alpha", "beta"}

    def test_list_profiles_empty(self, manager: BYOKManager) -> None:
        assert manager.list_profiles() == []

    def test_delete_profile(self, manager: BYOKManager) -> None:
        manager.create_profile(name="delete-me", api_key="k")
        assert manager.delete_profile("delete-me") is True
        assert manager.get_profile("delete-me") is None

    def test_delete_nonexistent(self, manager: BYOKManager) -> None:
        assert manager.delete_profile("ghost") is False

    def test_update_profile(self, manager: BYOKManager) -> None:
        profile = manager.create_profile(name="updatable", api_key="old-key")
        profile.api_key = SecretStr("new-key")
        profile.model_id = "new-model"
        manager.update_profile(profile)

        loaded = manager.get_profile("updatable")
        assert loaded is not None
        assert loaded.api_key is not None
        assert loaded.api_key.get_secret_value() == "new-key"
        assert loaded.model_id == "new-model"

    def test_active_profile(self, manager: BYOKManager) -> None:
        manager.create_profile(name="primary", api_key="k1")
        manager.create_profile(name="secondary", api_key="k2")

        assert manager.get_active_profile() is None

        manager.set_active_profile("primary")
        active = manager.get_active_profile()
        assert active is not None
        assert active.profile_name == "primary"

        manager.set_active_profile("secondary")
        active = manager.get_active_profile()
        assert active is not None
        assert active.profile_name == "secondary"

    def test_active_profile_deleted_resets(self, manager: BYOKManager) -> None:
        manager.create_profile(name="active-one", api_key="k")
        manager.set_active_profile("active-one")
        manager.delete_profile("active-one")
        assert manager.get_active_profile() is None

    def test_multiple_profiles_independent(self, manager: BYOKManager) -> None:
        manager.create_profile(name="profile-a", api_key="key-a", model_id="model-a")
        manager.create_profile(name="profile-b", api_key="key-b", model_id="model-b")

        loaded_a = manager.get_profile("profile-a")
        loaded_b = manager.get_profile("profile-b")
        assert loaded_a is not None
        assert loaded_b is not None
        assert loaded_a.api_key.get_secret_value() == "key-a"
        assert loaded_b.api_key.get_secret_value() == "key-b"
        assert loaded_a.model_id == "model-a"
        assert loaded_b.model_id == "model-b"


# ── Export / Import tests ─────────────────────────────────────────────────


class TestBYOKExportImport:
    def test_export_import_profile_roundtrip(
        self,
        manager: BYOKManager,
        tmp_path: Path,
    ) -> None:
        manager.create_profile(
            name="exportable",
            provider_type="anthropic",
            base_url="https://api.anthropic.com",
            model_id="claude-sonnet-4",
            api_key="sk-ant-export-test",
            custom_headers={"X-Test": "yes"},
        )

        export_path = str(tmp_path / "profile.byok")
        export_passphrase = "export-secret-456"
        manager.export_profile("exportable", export_path, export_passphrase)

        imported = manager.import_profile(export_path, export_passphrase)
        assert imported.profile_name == "exportable"
        assert imported.provider_type == "anthropic"
        assert imported.api_key is not None
        assert imported.api_key.get_secret_value() == "sk-ant-export-test"
        assert imported.base_url == "https://api.anthropic.com"
        assert imported.model_id == "claude-sonnet-4"
        assert imported.custom_headers == {"X-Test": "yes"}

    def test_export_all_import_all_roundtrip(
        self,
        manager: BYOKManager,
        tmp_path: Path,
    ) -> None:
        manager.create_profile(name="prof-a", api_key="key-a")
        manager.create_profile(name="prof-b", api_key="key-b")

        export_path = str(tmp_path / "all.byok")
        export_passphrase = "bulk-export-pass"
        manager.export_all(export_path, export_passphrase)

        names = manager.import_all(export_path, export_passphrase)
        assert set(names) == {"prof-a", "prof-b"}

    def test_import_wrong_passphrase(
        self,
        manager: BYOKManager,
        tmp_path: Path,
    ) -> None:
        manager.create_profile(name="secret", api_key="sensitive-key")
        export_path = str(tmp_path / "secret.byok")
        manager.export_profile("secret", export_path, "correct-phrase")

        with pytest.raises(KeyManagementError):
            manager.import_profile(export_path, "wrong-phrase")

    def test_import_corrupted_file(self, manager: BYOKManager, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.byok"
        bad_file.write_text("not-json", encoding="utf-8")

        with pytest.raises(KeyManagementError):
            manager.import_profile(str(bad_file), "any-phrase")

    def test_export_nonexistent_profile(self, manager: BYOKManager, tmp_path: Path) -> None:
        export_path = str(tmp_path / "ghost.byok")
        with pytest.raises(KeyManagementError):
            manager.export_profile("ghost", export_path, "pass")

    def test_import_export_same_passphrase(
        self,
        manager: BYOKManager,
        tmp_path: Path,
    ) -> None:
        manager.create_profile(name="shared", api_key="shared-key")
        export_passphrase = "master-phrase"
        export_path = str(tmp_path / "shared.byok")
        manager.export_profile("shared", export_path, export_passphrase)

        imported = manager.import_profile(export_path, export_passphrase)
        assert imported.api_key is not None
        assert imported.api_key.get_secret_value() == "shared-key"

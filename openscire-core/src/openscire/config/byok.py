# SPDX-License-Identifier: Apache-2.0

"""BYOK (Bring Your Own Key) config module.

Provides encrypted-at-rest storage for provider API keys with OS keyring
integration, passphrase-derived encryption, multiple profiles, and portable
encrypted import/export.
"""

from __future__ import annotations

import base64
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, SecretStr

from openscire.exceptions import KeyManagementError
from openscire.provider.base import ProviderConfig

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM
    from nacl.secret import SecretBox as _SecretBox

_CRYPTOGRAPHY_AVAILABLE: bool = False
_PYNACL_AVAILABLE: bool = False
_KEYRING_AVAILABLE: bool = False

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM

    _CRYPTOGRAPHY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _AESGCM = None  # type: ignore[assignment, misc]
    _CRYPTOGRAPHY_AVAILABLE = False

try:
    from nacl.secret import SecretBox as _SecretBox

    _PYNACL_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SecretBox = None  # type: ignore[assignment, misc]
    _PYNACL_AVAILABLE = False

try:
    import keyring as _keyring

    _KEYRING_AVAILABLE = True
except ImportError:  # pragma: no cover
    _keyring = None
    _KEYRING_AVAILABLE = False


_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_KEY_LENGTH = 32
_GCM_NONCE_LENGTH = 12
_SECRETBOX_NONCE_LENGTH = 24
_SALT_LENGTH = 16

_CONFIG_DIR = Path("~/.config/openscire").expanduser()
_PROFILES_PATH = _CONFIG_DIR / "byok.json"
_PASSPHRASE_PATH = _CONFIG_DIR / "byok.pass"
_KEYRING_SERVICE = "openscire-byok"
_KEYRING_ACCOUNT = "master"


@dataclass
class EncryptedPayload:
    """Encrypted blob with the parameters needed to decrypt it."""

    ciphertext: str = ""
    nonce: str = ""
    salt: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"ciphertext": self.ciphertext, "nonce": self.nonce, "salt": self.salt}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> EncryptedPayload:
        return cls(
            ciphertext=data.get("ciphertext", ""),
            nonce=data.get("nonce", ""),
            salt=data.get("salt", ""),
        )


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    import hashlib

    return hashlib.scrypt(
        password=passphrase.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_KEY_LENGTH,
    )


def _ensure_config_dir() -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _set_file_permissions(path: Path) -> None:
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


class CryptoEngine:
    """AES-256-GCM encryption with Scrypt key derivation.

    Requires ``cryptography`` (primary) or ``pynacl`` (fallback).
    Key derivation uses stdlib ``hashlib.scrypt``, available in Python 3.12+,
    so the derived key is identical regardless of which encryption backend
    is available.
    """

    @staticmethod
    def encrypt(passphrase: str, plaintext: str) -> EncryptedPayload:
        """Encrypt plaintext with passphrase-derived AES-256-GCM key.

        Args:
            passphrase: User's master passphrase.
            plaintext: Data to encrypt (typically an API key).

        Returns:
            ``EncryptedPayload`` with base64-encoded ciphertext, nonce, and salt.
        """
        salt = os.urandom(_SALT_LENGTH)
        key = _derive_key(passphrase, salt)

        if _CRYPTOGRAPHY_AVAILABLE:
            nonce = os.urandom(_GCM_NONCE_LENGTH)
            assert _AESGCM is not None
            aesgcm = _AESGCM(key)
            ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
            return EncryptedPayload(
                ciphertext=base64.b64encode(ct).decode("ascii"),
                nonce=base64.b64encode(nonce).decode("ascii"),
                salt=base64.b64encode(salt).decode("ascii"),
            )

        if _PYNACL_AVAILABLE:
            assert _SecretBox is not None
            box = _SecretBox(key)
            encrypted = box.encrypt(plaintext.encode("utf-8"))
            return EncryptedPayload(
                ciphertext=base64.b64encode(bytes(encrypted.ciphertext)).decode("ascii"),
                nonce=base64.b64encode(bytes(encrypted.nonce)).decode("ascii"),
                salt=base64.b64encode(salt).decode("ascii"),
            )

        raise KeyManagementError(
            message="No encryption library available. Install openscire-core[byok] "
            "(adds cryptography) or ensure pynacl is installed.",
            source="config.byok.CryptoEngine",
        )

    @staticmethod
    def decrypt(passphrase: str, payload: EncryptedPayload) -> str:
        """Decrypt an EncryptedPayload with passphrase-derived key.

        Args:
            passphrase: User's master passphrase.
            payload: ``EncryptedPayload`` with ciphertext, nonce, and salt.

        Returns:
            Decrypted plaintext string.
        """
        salt = base64.b64decode(payload.salt)
        key = _derive_key(passphrase, salt)

        if _CRYPTOGRAPHY_AVAILABLE:
            nonce = base64.b64decode(payload.nonce)
            ct = base64.b64decode(payload.ciphertext)
            assert _AESGCM is not None
            aesgcm = _AESGCM(key)
            try:
                plaintext = aesgcm.decrypt(nonce, ct, None)
            except Exception as exc:
                raise KeyManagementError(
                    message="Decryption failed: incorrect passphrase or corrupted data.",
                    source="config.byok.CryptoEngine",
                ) from exc
            return plaintext.decode("utf-8")

        if _PYNACL_AVAILABLE:
            nonce_bytes = base64.b64decode(payload.nonce)
            ct_bytes = base64.b64decode(payload.ciphertext)
            assert _SecretBox is not None
            box = _SecretBox(key)
            try:
                plaintext = box.decrypt(ct_bytes + nonce_bytes)
            except Exception as exc:
                raise KeyManagementError(
                    message="Decryption failed: incorrect passphrase or corrupted data.",
                    source="config.byok.CryptoEngine",
                ) from exc
            return plaintext.decode("utf-8")

        raise KeyManagementError(
            message="No encryption library available. Install openscire-core[byok] "
            "or ensure pynacl is installed.",
            source="config.byok.CryptoEngine",
        )


class KeyStore:
    """OS keyring storage with encrypted file fallback.

    Primary: ``keyring`` package (macOS Keychain, Linux Secret Service,
    Windows Credential Manager).
    Fallback: ``~/.config/openscire/byok.pass`` with 0600 permissions.
    """

    @staticmethod
    def store_passphrase(passphrase: str) -> bool:
        """Store master passphrase in the OS keyring (or file fallback).

        Returns:
            ``True`` if stored successfully.
        """
        if _KEYRING_AVAILABLE:
            try:
                assert _keyring is not None
                _keyring.set_password(_KEYRING_SERVICE, _KEYRING_ACCOUNT, passphrase)
                return True
            except Exception:
                pass
        _ensure_config_dir()
        _PASSPHRASE_PATH.write_text(passphrase, encoding="utf-8")
        _set_file_permissions(_PASSPHRASE_PATH)
        return True

    @staticmethod
    def retrieve_passphrase() -> str | None:
        """Retrieve master passphrase from OS keyring (or file fallback).

        Returns:
            Passphrase string, or ``None`` if not found.
        """
        if _KEYRING_AVAILABLE:
            try:
                assert _keyring is not None
                value = _keyring.get_password(_KEYRING_SERVICE, _KEYRING_ACCOUNT)
                if value:
                    return str(value)
            except Exception:
                pass
        if _PASSPHRASE_PATH.exists():
            return _PASSPHRASE_PATH.read_text(encoding="utf-8").strip()
        return None

    @staticmethod
    def clear_passphrase() -> bool:
        """Remove stored passphrase from keyring and file fallback.

        Returns:
            ``True`` if cleared (or already absent).
        """
        if _KEYRING_AVAILABLE:
            try:
                assert _keyring is not None
                _keyring.delete_password(_KEYRING_SERVICE, _KEYRING_ACCOUNT)
            except Exception:
                pass
        if _PASSPHRASE_PATH.exists():
            _PASSPHRASE_PATH.unlink()
        return True


class BYOKProfile(BaseModel):
    """A named BYOK profile holding provider connection config and API key.

    The ``api_key`` field is a ``SecretStr`` — it is held in plaintext in
    memory but redacted on ``repr()``, ``str()``, ``model_dump()``, and
    ``model_dump_json()``.

    Use ``to_provider_config()`` to produce a ``ProviderConfig`` for direct
    use with any openSciRe provider adapter.
    """

    profile_name: str = Field(min_length=1, pattern=r"^[a-zA-Z0-9_-]+$")
    provider_type: str = "openai_compatible"
    base_url: str = ""
    model_id: str = ""
    custom_headers: dict[str, str] = Field(default_factory=dict)
    api_key: SecretStr | None = None
    created_at: str = ""
    updated_at: str = ""

    def to_provider_config(self) -> ProviderConfig:
        """Convert this profile to a ``ProviderConfig``.

        Returns:
            ``ProviderConfig`` with api_key, base_url, default_model,
            and extra_headers populated from this profile.
        """
        return ProviderConfig(
            api_key=self.api_key,
            base_url=self.base_url,
            default_model=self.model_id,
            extra_headers=self.custom_headers,
        )


class _ProfileStore:
    """Persists profiles with encrypted API keys to ``~/.config/openscire/byok.json``.

    Only the ``api_key`` field is encrypted at rest. All other profile
    metadata is stored in plaintext for fast listing without decryption.
    """

    def __init__(self, passphrase: str) -> None:
        self._passphrase = passphrase
        self._crypto = CryptoEngine()

    def _load_raw(self) -> dict[str, Any]:
        if not _PROFILES_PATH.exists():
            return {"profiles": {}, "active_profile": None}
        try:
            return json.loads(_PROFILES_PATH.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
        except (json.JSONDecodeError, OSError):
            return {"profiles": {}, "active_profile": None}

    def _save_raw(self, data: dict[str, Any]) -> None:
        _ensure_config_dir()
        _PROFILES_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        _set_file_permissions(_PROFILES_PATH)

    def list_profiles(self) -> list[str]:
        data = self._load_raw()
        return sorted(data.get("profiles", {}).keys())

    def load_profile(self, name: str) -> BYOKProfile | None:
        data = self._load_raw()
        entry = data.get("profiles", {}).get(name)
        if entry is None:
            return None
        encrypted = EncryptedPayload.from_dict(entry.get("encrypted_api_key", {}))
        api_key_str = self._crypto.decrypt(self._passphrase, encrypted)
        return BYOKProfile(
            profile_name=name,
            provider_type=entry.get("provider_type", "openai_compatible"),
            base_url=entry.get("base_url", ""),
            model_id=entry.get("model_id", ""),
            custom_headers=entry.get("custom_headers", {}),
            api_key=SecretStr(api_key_str),
            created_at=entry.get("created_at", ""),
            updated_at=entry.get("updated_at", ""),
        )

    def save_profile(self, profile: BYOKProfile) -> None:
        data = self._load_raw()
        api_key_value = profile.api_key.get_secret_value() if profile.api_key else ""
        encrypted = self._crypto.encrypt(self._passphrase, api_key_value)
        data.setdefault("profiles", {})[profile.profile_name] = {
            "provider_type": profile.provider_type,
            "base_url": profile.base_url,
            "model_id": profile.model_id,
            "custom_headers": profile.custom_headers,
            "encrypted_api_key": encrypted.to_dict(),
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
        }
        self._save_raw(data)

    def delete_profile(self, name: str) -> bool:
        data = self._load_raw()
        profiles = data.get("profiles", {})
        if name not in profiles:
            return False
        del profiles[name]
        if data.get("active_profile") == name:
            data["active_profile"] = None
        self._save_raw(data)
        return True

    def get_active_profile_name(self) -> str | None:
        data = self._load_raw()
        active: str | None = data.get("active_profile")
        return active if active else None

    def set_active_profile_name(self, name: str | None) -> None:
        data = self._load_raw()
        data["active_profile"] = name
        self._save_raw(data)


class BYOKManager:
    """High-level BYOK manager integrating passphrase storage, key encryption,
    profile persistence, and portable import/export.

    Typical usage::

        # First-time setup
        mgr = BYOKManager()
        mgr.initialize_passphrase("my-strong-passphrase")

        # Create a profile
        profile = mgr.create_profile(
            name="personal",
            provider_type="openai_compatible",
            base_url="https://api.openai.com/v1",
            model_id="gpt-4o",
            api_key="sk-...",
        )

        # Use it
        config = profile.to_provider_config()
        provider = OpenAICompatibleProvider(config)
        ...

        # Switch profiles
        mgr.set_active_profile("lab-enterprise")
        profile = mgr.get_active_profile()

    Args:
        passphrase: Optional master passphrase. If not provided, the
            manager attempts to load it from the OS keyring (or file
            fallback). Raises ``KeyManagementError`` if not found.
    """

    def __init__(self, passphrase: str | None = None) -> None:
        self._passphrase = passphrase
        if self._passphrase is None:
            self._passphrase = KeyStore.retrieve_passphrase()
        if self._passphrase is None:
            raise KeyManagementError(
                message="No master passphrase available. Call initialize_passphrase() "
                "or provide a passphrase to BYOKManager().",
                source="config.byok.BYOKManager",
            )
        self._store = _ProfileStore(self._passphrase)

    def initialize_passphrase(
        self,
        passphrase: str,
        store_in_keyring: bool = True,
    ) -> None:
        """First-time setup: store master passphrase.

        Args:
            passphrase: Master passphrase for key encryption.
            store_in_keyring: If ``True``, store in OS keyring.
                If ``False``, the passphrase must be provided on every
                ``BYOKManager()`` instantiation.
        """
        self._passphrase = passphrase
        self._store = _ProfileStore(self._passphrase)
        if store_in_keyring:
            KeyStore.store_passphrase(passphrase)

    def create_profile(
        self,
        name: str,
        provider_type: str = "openai_compatible",
        base_url: str = "",
        model_id: str = "",
        api_key: str = "",
        custom_headers: dict[str, str] | None = None,
    ) -> BYOKProfile:
        """Create and persist a new BYOK profile.

        Args:
            name: Unique profile name (``[a-zA-Z0-9_-]+``).
            provider_type: Provider type identifier.
            base_url: Provider API base URL.
            model_id: Default model ID.
            api_key: Provider API key.
            custom_headers: Optional extra HTTP headers.

        Returns:
            The newly created ``BYOKProfile``.
        """
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        profile = BYOKProfile(
            profile_name=name,
            provider_type=provider_type,
            base_url=base_url,
            model_id=model_id,
            custom_headers=custom_headers or {},
            api_key=SecretStr(api_key) if api_key else None,
            created_at=now,
            updated_at=now,
        )
        self._store.save_profile(profile)
        return profile

    def get_profile(self, name: str) -> BYOKProfile | None:
        """Load a profile by name.

        Returns:
            ``BYOKProfile`` with decrypted ``api_key``, or ``None``.
        """
        return self._store.load_profile(name)

    def update_profile(self, profile: BYOKProfile) -> None:
        """Update an existing profile's persisted data.

        Args:
            profile: Profile with updated fields. Its ``api_key`` is
                re-encrypted on save.
        """
        from datetime import datetime, timezone

        profile.updated_at = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        self._store.save_profile(profile)

    def delete_profile(self, name: str) -> bool:
        """Delete a profile by name.

        Returns:
            ``True`` if the profile existed and was deleted.
        """
        return self._store.delete_profile(name)

    def list_profiles(self) -> list[str]:
        """List all stored profile names."""
        return self._store.list_profiles()

    def get_active_profile(self) -> BYOKProfile | None:
        """Load the currently active profile (if set)."""
        active = self._store.get_active_profile_name()
        if active is None:
            return None
        return self.get_profile(active)

    def set_active_profile(self, name: str) -> None:
        """Set the active profile by name."""
        self._store.set_active_profile_name(name)

    def _export_payload(
        self,
        profiles: dict[str, BYOKProfile],
        export_passphrase: str,
    ) -> str:
        payload: dict[str, Any] = {"version": 1, "profiles": {}}
        for name, profile in profiles.items():
            api_key_value = profile.api_key.get_secret_value() if profile.api_key else ""
            encrypted = CryptoEngine.encrypt(export_passphrase, api_key_value)
            payload["profiles"][name] = {
                "provider_type": profile.provider_type,
                "base_url": profile.base_url,
                "model_id": profile.model_id,
                "custom_headers": profile.custom_headers,
                "encrypted_api_key": encrypted.to_dict(),
                "created_at": profile.created_at,
                "updated_at": profile.updated_at,
            }

        salt = os.urandom(_SALT_LENGTH)
        key = _derive_key(export_passphrase, salt)
        plaintext = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        if _CRYPTOGRAPHY_AVAILABLE:
            nonce = os.urandom(_GCM_NONCE_LENGTH)
            assert _AESGCM is not None
            aesgcm = _AESGCM(key)
            ct = aesgcm.encrypt(nonce, plaintext, None)
            envelope = {
                "version": 1,
                "salt": base64.b64encode(salt).decode("ascii"),
                "nonce": base64.b64encode(nonce).decode("ascii"),
                "ciphertext": base64.b64encode(ct).decode("ascii"),
            }
        elif _PYNACL_AVAILABLE:
            assert _SecretBox is not None
            box = _SecretBox(key)
            encrypted_msg = box.encrypt(plaintext)
            envelope = {
                "version": 1,
                "salt": base64.b64encode(salt).decode("ascii"),
                "nonce": base64.b64encode(encrypted_msg.nonce).decode("ascii"),
                "ciphertext": base64.b64encode(encrypted_msg.ciphertext).decode("ascii"),
            }
        else:
            raise KeyManagementError(
                message="No encryption library available for export.",
                source="config.byok.BYOKManager",
            )

        return json.dumps(envelope, ensure_ascii=False)

    def _import_payload(
        self,
        file_contents: str,
        export_passphrase: str,
    ) -> dict[str, BYOKProfile]:
        try:
            envelope = json.loads(file_contents)
        except json.JSONDecodeError as exc:
            raise KeyManagementError(
                message="Invalid export file format.",
                source="config.byok.BYOKManager",
            ) from exc

        version = envelope.get("version", 0)
        if version != 1:
            raise KeyManagementError(
                message=f"Unsupported export format version: {version}",
                source="config.byok.BYOKManager",
            )

        salt = base64.b64decode(envelope["salt"])
        key = _derive_key(export_passphrase, salt)

        if _CRYPTOGRAPHY_AVAILABLE:
            nonce = base64.b64decode(envelope["nonce"])
            ct = base64.b64decode(envelope["ciphertext"])
            assert _AESGCM is not None
            aesgcm = _AESGCM(key)
            try:
                plaintext = aesgcm.decrypt(nonce, ct, None)
            except Exception as exc:
                raise KeyManagementError(
                    message="Export decryption failed: incorrect passphrase.",
                    source="config.byok.BYOKManager",
                ) from exc
        elif _PYNACL_AVAILABLE:
            nonce_bytes = base64.b64decode(envelope["nonce"])
            ct_bytes = base64.b64decode(envelope["ciphertext"])
            assert _SecretBox is not None
            box = _SecretBox(key)
            try:
                plaintext = box.decrypt(ct_bytes + nonce_bytes)
            except Exception as exc:
                raise KeyManagementError(
                    message="Export decryption failed: incorrect passphrase.",
                    source="config.byok.BYOKManager",
                ) from exc
        else:
            raise KeyManagementError(
                message="No encryption library available for import.",
                source="config.byok.BYOKManager",
            )

        payload = json.loads(plaintext.decode("utf-8"))
        profiles: dict[str, BYOKProfile] = {}
        for name, entry in payload.get("profiles", {}).items():
            encrypted = EncryptedPayload.from_dict(entry.get("encrypted_api_key", {}))
            api_key_str = CryptoEngine.decrypt(export_passphrase, encrypted)
            profiles[name] = BYOKProfile(
                profile_name=name,
                provider_type=entry.get("provider_type", "openai_compatible"),
                base_url=entry.get("base_url", ""),
                model_id=entry.get("model_id", ""),
                custom_headers=entry.get("custom_headers", {}),
                api_key=SecretStr(api_key_str) if api_key_str else None,
                created_at=entry.get("created_at", ""),
                updated_at=entry.get("updated_at", ""),
            )
        return profiles

    def export_profile(self, name: str, output_path: str, export_passphrase: str) -> None:
        """Export a single profile to a portable encrypted ``.byok`` file.

        The file is encrypted with AES-256-GCM using the *export passphrase*,
        which may differ from the master passphrase.

        Args:
            name: Profile name to export.
            output_path: Filesystem path for the ``.byok`` file.
            export_passphrase: Passphrase to encrypt the export.
        """
        profile = self.get_profile(name)
        if profile is None:
            raise KeyManagementError(
                message=f"Profile '{name}' not found for export.",
                source="config.byok.BYOKManager",
            )
        data = self._export_payload({name: profile}, export_passphrase)
        Path(output_path).write_text(data, encoding="utf-8")

    def import_profile(self, input_path: str, export_passphrase: str) -> BYOKProfile:
        """Import a single profile from a portable ``.byok`` file.

        Args:
            input_path: Path to the ``.byok`` file.
            export_passphrase: Passphrase used to encrypt the export.

        Returns:
            The decrypted ``BYOKProfile``. It is **not** automatically
            saved — call ``save_profile()`` or ``update_profile()`` to
            persist it under the local master passphrase.
        """
        contents = Path(input_path).read_text(encoding="utf-8")
        profiles = self._import_payload(contents, export_passphrase)
        if not profiles:
            raise KeyManagementError(
                message="Export file contains no profiles.",
                source="config.byok.BYOKManager",
            )
        return next(iter(profiles.values()))

    def export_all(self, output_path: str, export_passphrase: str) -> None:
        """Export all profiles to a portable encrypted ``.byok`` file.

        Args:
            output_path: Filesystem path for the ``.byok`` file.
            export_passphrase: Passphrase to encrypt the export.
        """
        profiles: dict[str, BYOKProfile] = {}
        for name in self.list_profiles():
            profile = self.get_profile(name)
            if profile is not None:
                profiles[name] = profile
        data = self._export_payload(profiles, export_passphrase)
        Path(output_path).write_text(data, encoding="utf-8")

    def import_all(self, input_path: str, export_passphrase: str) -> list[str]:
        """Import all profiles from a portable ``.byok`` file.

        Each imported profile is automatically saved under the local
        master passphrase. Existing profiles with the same name are
        overwritten.

        Args:
            input_path: Path to the ``.byok`` file.
            export_passphrase: Passphrase used to encrypt the export.

        Returns:
            List of imported profile names.
        """
        contents = Path(input_path).read_text(encoding="utf-8")
        imported = self._import_payload(contents, export_passphrase)
        for _name, profile in imported.items():
            self._store.save_profile(profile)
        return list(imported.keys())

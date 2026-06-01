# SPDX-License-Identifier: Apache-2.0

"""Ed25519 signing and verification for provenance entries."""

import hashlib
import json

import nacl.bindings
import nacl.exceptions

from openscire.models import ProvenanceEntry


def content_hash(entry: ProvenanceEntry) -> str:
    """Compute a SHA-256 hash of a provenance entry's content.

    The cryptographic_signature field is excluded from the hash.

    Args:
        entry: The ProvenanceEntry to hash.

    Returns:
        Hex-encoded SHA-256 digest.
    """
    dump = entry.model_dump(mode="python", exclude={"cryptographic_signature"})
    dump["_sorted"] = True
    raw = json.dumps(dump, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def sign_entry(
    entry: ProvenanceEntry,
    private_key_hex: str,
) -> ProvenanceEntry:
    """Cryptographically sign a provenance entry with an Ed25519 private key.

    Args:
        entry: The ProvenanceEntry to sign.
        private_key_hex: Ed25519 private key (or seed) as hex string.

    Returns:
        A new ProvenanceEntry with cryptographic_signature set.
    """
    key_bytes = bytes.fromhex(private_key_hex)
    if len(key_bytes) == nacl.bindings.crypto_sign_SEEDBYTES:
        _, key_bytes = nacl.bindings.crypto_sign_seed_keypair(key_bytes)
    msg = content_hash(entry).encode("utf-8")
    sig = nacl.bindings.crypto_sign(msg, key_bytes)
    sig_hex = sig[: nacl.bindings.crypto_sign_BYTES].hex()
    return entry.model_copy(update={"cryptographic_signature": sig_hex})


def verify_entry(
    entry: ProvenanceEntry,
    public_key_hex: str,
) -> bool:
    """Verify a provenance entry's cryptographic signature.

    Args:
        entry: The ProvenanceEntry to verify.
        public_key_hex: Ed25519 public key as hex string.

    Returns:
        True if the signature is valid, False otherwise.
    """
    if entry.cryptographic_signature is None:
        return False
    try:
        key_bytes = bytes.fromhex(public_key_hex)
        sig_bytes = bytes.fromhex(entry.cryptographic_signature)
        msg = content_hash(entry).encode("utf-8")
        nacl.bindings.crypto_sign_open(sig_bytes + msg, key_bytes)
        return True
    except (
        nacl.exceptions.BadSignatureError,
        ValueError,
        nacl.exceptions.ValueError,
    ):
        return False

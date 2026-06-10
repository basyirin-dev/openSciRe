from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import FirewallAuditEntry

logger = logging.getLogger(__name__)

_AUDIT_TABLE = """
CREATE TABLE IF NOT EXISTS firewall_audit (
    entry_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    category TEXT NOT NULL,
    action_taken TEXT NOT NULL,
    match_type TEXT NOT NULL,
    matched_content TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    user_id TEXT DEFAULT '',
    contested INTEGER DEFAULT 0,
    contest_reason TEXT DEFAULT '',
    signature TEXT,
    metadata TEXT DEFAULT '{}'
)
"""

_CONTESTS_TABLE = """
CREATE TABLE IF NOT EXISTS contests (
    contest_id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    reviewed INTEGER DEFAULT 0,
    reviewed_at TEXT,
    review_notes TEXT DEFAULT '',
    upheld INTEGER
)
"""

_MAX_MATCHED_LENGTH = 200


class FirewallAuditLog:
    """Append-only audit log for firewall decisions.

    Stores entries in SQLite. No update or delete methods are exposed;
    entries are INSERT-only.  When an explicit signing key is provided,
    entries are Ed25519-signed for tamper evidence (reuses provenance
    signing machinery).

    Attributes:
        db_path: Filesystem path to the SQLite database.
    """

    def __init__(self, db_path: str | Path = "data/firewall_audit.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = self._connect()
        self._init_tables()

    def _connect(self) -> Any:  # noqa: ANN401
        import sqlite3

        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_tables(self) -> None:
        self._conn.execute(_AUDIT_TABLE)
        self._conn.execute(_CONTESTS_TABLE)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON firewall_audit(timestamp)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_decision ON firewall_audit(decision_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_contest_decision ON contests(decision_id)"
        )
        self._conn.commit()

    def append(
        self,
        entry: FirewallAuditEntry,
        signing_key: str | None = None,
    ) -> FirewallAuditEntry:
        """Append a firewall audit entry.

        If ``signing_key`` is provided, the entry is Ed25519-signed before
        storage.

        Args:
            entry: The audit entry to persist.
            signing_key: Optional hex-encoded Ed25519 private key.

        Returns:
            The persisted entry (with signature if signing was applied).
        """
        if not entry.entry_id:
            entry = entry.model_copy(update={"entry_id": str(uuid.uuid4())})

        if signing_key is not None:
            entry = self._sign(entry, signing_key)

        self._conn.execute(
            "INSERT OR IGNORE INTO firewall_audit "
            "(entry_id, timestamp, decision_id, category, action_taken, "
            "match_type, matched_content, input_hash, user_id, contested, "
            "contest_reason, signature, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entry.entry_id,
                entry.timestamp.isoformat(),
                entry.decision_id,
                entry.category,
                entry.action_taken,
                entry.match_type,
                entry.matched_content[:_MAX_MATCHED_LENGTH],
                entry.input_hash,
                entry.user_id,
                1 if entry.contested else 0,
                entry.contest_reason,
                entry.cryptographic_signature or "",
                _json_dumps(entry.metadata),
            ),
        )
        self._conn.commit()
        return entry

    def get(self, entry_id: str) -> FirewallAuditEntry | None:
        """Retrieve a single audit entry by ID."""
        row = self._conn.execute(
            "SELECT * FROM firewall_audit WHERE entry_id = ?", (entry_id,)
        ).fetchone()
        if row is None:
            return None
        return _row_to_entry(row)

    def query(
        self,
        category: str | None = None,
        action_taken: str | None = None,
        match_type: str | None = None,
        contested: bool | None = None,
        user_id: str | None = None,
        decision_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[FirewallAuditEntry]:
        """Query audit entries with optional filters.

        Args:
            category: Filter by DURC category.
            action_taken: Filter by action (flag, warn, block, escalate).
            match_type: Filter by match type (keyword, embedding, llm).
            contested: Filter by contested status.
            user_id: Filter by user identifier.
            decision_id: Filter by decision UUID.
            limit: Maximum entries to return.
            offset: Pagination offset.

        Returns:
            List of matching FirewallAuditEntry objects.
        """
        sql = "SELECT * FROM firewall_audit WHERE 1=1"
        params: list[Any] = []
        if category is not None:
            sql += " AND category = ?"
            params.append(category)
        if action_taken is not None:
            sql += " AND action_taken = ?"
            params.append(action_taken)
        if match_type is not None:
            sql += " AND match_type = ?"
            params.append(match_type)
        if contested is not None:
            sql += " AND contested = ?"
            params.append(1 if contested else 0)
        if user_id is not None:
            sql += " AND user_id = ?"
            params.append(user_id)
        if decision_id is not None:
            sql += " AND decision_id = ?"
            params.append(decision_id)
        sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self._conn.execute(sql, params).fetchall()
        return [_row_to_entry(r) for r in rows]

    def count(
        self,
        category: str | None = None,
        action_taken: str | None = None,
    ) -> int:
        """Count entries with optional filters."""
        sql = "SELECT COUNT(*) FROM firewall_audit WHERE 1=1"
        params: list[Any] = []
        if category is not None:
            sql += " AND category = ?"
            params.append(category)
        if action_taken is not None:
            sql += " AND action_taken = ?"
            params.append(action_taken)
        row = self._conn.execute(sql, params).fetchone()
        return row[0] if row else 0

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _sign(entry: FirewallAuditEntry, signing_key: str) -> FirewallAuditEntry:
        try:
            import nacl.bindings

            key_bytes = bytes.fromhex(signing_key)
            if len(key_bytes) == nacl.bindings.crypto_sign_SEEDBYTES:
                _, key_bytes = nacl.bindings.crypto_sign_seed_keypair(key_bytes)

            msg = _entry_sign_bytes(entry)
            sig = nacl.bindings.crypto_sign(msg, key_bytes)
            sig_hex = sig[: nacl.bindings.crypto_sign_BYTES].hex()
            return entry.model_copy(update={"cryptographic_signature": sig_hex})
        except Exception:
            logger.warning("Failed to sign audit entry", exc_info=True)
            return entry

    @staticmethod
    def verify(entry: FirewallAuditEntry, public_key_hex: str) -> bool:
        """Verify an audit entry's signature.

        Args:
            entry: The entry to verify.
            public_key_hex: Ed25519 public key as hex string.

        Returns:
            True if the signature is valid, False otherwise.
        """
        if entry.cryptographic_signature is None:
            return False
        try:
            import nacl.bindings
            import nacl.exceptions

            key_bytes = bytes.fromhex(public_key_hex)
            sig_bytes = bytes.fromhex(entry.cryptographic_signature)
            msg = _entry_sign_bytes(entry)
            nacl.bindings.crypto_sign_open(sig_bytes + msg, key_bytes)
            return True
        except (
            nacl.exceptions.BadSignatureError,
            ValueError,
            nacl.exceptions.ValueError,
        ):
            return False
        except Exception:
            return False


def _entry_sign_bytes(entry: FirewallAuditEntry) -> bytes:
    from hashlib import sha256

    raw = (
        f"{entry.entry_id}:{entry.decision_id}:{entry.category}"
        f":{entry.action_taken}:{entry.timestamp.isoformat()}"
    )
    return sha256(raw.encode()).digest()


def _json_dumps(data: dict[str, Any]) -> str:
    import json

    return json.dumps(data, default=str, sort_keys=True)


def _row_to_entry(row: Any) -> FirewallAuditEntry:  # noqa: ANN401
    import json

    return FirewallAuditEntry(
        entry_id=row[0],
        timestamp=datetime.fromisoformat(row[1]),
        decision_id=row[2],
        category=row[3],
        action_taken=row[4],
        match_type=row[5],
        matched_content=row[6],
        input_hash=row[7],
        user_id=row[8],
        contested=bool(row[9]),
        contest_reason=row[10] or "",
        cryptographic_signature=row[11] or None,
        metadata=json.loads(row[12]) if row[12] else {},
    )

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from openscire.logging import get_logger

from .audit import FirewallAuditLog
from .models import ContestRecord

logger = get_logger("openscire.ethics.feedback")


class ContestManager:
    """Manages the false-positive feedback loop for firewall decisions.

    Users can contest firewall decisions.  Contests are stored in the
    audit log's contests table and can be reviewed, closed, and exported
    for classifier tuning.
    """

    def __init__(self, audit_log: FirewallAuditLog) -> None:
        self._audit_log = audit_log

    def submit_contest(
        self,
        decision_id: str,
        user_id: str,
        reason: str,
    ) -> ContestRecord:
        """Submit a contest against a firewall decision.

        Args:
            decision_id: The decision ID to contest.
            user_id: The user submitting the contest.
            reason: Free-text explanation of why the decision was wrong.

        Returns:
            The created ContestRecord.

        Raises:
            ValueError: If the decision_id does not exist in the audit log.
        """
        conn = self._audit_log._conn
        exists = conn.execute(
            "SELECT 1 FROM firewall_audit WHERE decision_id = ? LIMIT 1",
            (decision_id,),
        ).fetchone()
        if exists is None:
            msg = f"No audit entry found for decision_id: {decision_id}"
            raise ValueError(msg)  # noqa: TRY004

        contest_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        conn.execute(
            "INSERT INTO contests "
            "(contest_id, decision_id, user_id, reason, timestamp) "
            "VALUES (?, ?, ?, ?, ?)",
            (contest_id, decision_id, user_id, reason, now.isoformat()),
        )
        conn.execute(
            "UPDATE firewall_audit SET contested = 1, contest_reason = ? WHERE decision_id = ?",
            (reason[:500], decision_id),
        )
        conn.commit()

        logger.info(
            "Contest submitted",
            contest_id=contest_id,
            decision_id=decision_id,
            user_id=user_id,
        )

        return ContestRecord(
            contest_id=contest_id,
            decision_id=decision_id,
            user_id=user_id,
            reason=reason,
            timestamp=now,
        )

    def list_open_contests(self) -> list[ContestRecord]:
        """List all contests that have not been reviewed."""
        conn = self._audit_log._conn
        rows = conn.execute(
            "SELECT * FROM contests WHERE reviewed = 0 ORDER BY timestamp DESC"
        ).fetchall()
        return [_row_to_contest(r) for r in rows]

    def list_all_contests(self) -> list[ContestRecord]:
        """List all contests."""
        conn = self._audit_log._conn
        rows = conn.execute("SELECT * FROM contests ORDER BY timestamp DESC").fetchall()
        return [_row_to_contest(r) for r in rows]

    def review_contest(
        self,
        contest_id: str,
        upheld: bool,
        review_notes: str = "",
    ) -> ContestRecord | None:
        """Review and close a contest.

        Args:
            contest_id: The contest to review.
            upheld: True if the contest is valid (false positive), False otherwise.
            review_notes: Optional notes from the reviewer.

        Returns:
            The updated ContestRecord, or None if not found.
        """
        conn = self._audit_log._conn
        now = datetime.now(UTC)
        conn.execute(
            "UPDATE contests SET reviewed = 1, reviewed_at = ?, "
            "review_notes = ?, upheld = ? WHERE contest_id = ?",
            (now.isoformat(), review_notes, 1 if upheld else 0, contest_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM contests WHERE contest_id = ?", (contest_id,)).fetchone()
        if row is None:
            return None

        logger.info(
            "Contest reviewed",
            contest_id=contest_id,
            upheld=upheld,
        )
        return _row_to_contest(row)

    def export_jsonl(self, path: str) -> int:
        """Export all contested entries as JSONL for classifier tuning.

        Each line contains the original audit entry fields plus contest
        decision (upheld or not).

        Args:
            path: Output file path.

        Returns:
            Number of entries exported.
        """
        conn = self._audit_log._conn
        rows = conn.execute(
            "SELECT a.*, c.upheld, c.review_notes "
            "FROM firewall_audit a "
            "JOIN contests c ON a.decision_id = c.decision_id "
            "WHERE c.reviewed = 1"
        ).fetchall()

        count = 0
        with open(path, "w", encoding="utf-8") as f:
            for row in rows:
                entry = {
                    "entry_id": row[0],
                    "timestamp": row[1],
                    "decision_id": row[2],
                    "category": row[3],
                    "action_taken": row[4],
                    "match_type": row[5],
                    "matched_content": row[6],
                    "input_hash": row[7],
                    "contested": bool(row[9]),
                    "upheld": bool(row[13]) if len(row) > 13 else None,
                    "review_notes": row[14] if len(row) > 14 else "",
                }
                f.write(json.dumps(entry, sort_keys=True) + "\n")
                count += 1

        logger.info("Exported contested entries", path=path, count=count)
        return count


def _row_to_contest(row: Any) -> ContestRecord:  # noqa: ANN401
    return ContestRecord(
        contest_id=row[0],
        decision_id=row[1],
        user_id=row[2],
        reason=row[3],
        timestamp=datetime.fromisoformat(row[4]),
        reviewed=bool(row[5]),
        reviewed_at=datetime.fromisoformat(row[6]) if row[6] else None,
        review_notes=row[7] or "",
        upheld=bool(row[8]) if row[8] is not None else None,
    )

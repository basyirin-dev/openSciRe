from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from openscire.constants import ErrorCode
from openscire.exceptions import EthicsError

from .models import BudgetStatus, CarbonEstimate, CarbonRecord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hardware profile lookup table
# ---------------------------------------------------------------------------

HARDWARE_PROFILES: dict[str, tuple[int, int]] = {
    "rtx3090": (350, 142_000_000_000_000),
    "rtx4090": (450, 330_000_000_000_000),
    "a100": (400, 312_000_000_000_000),
    "a100_80gb": (400, 312_000_000_000_000),
    "h100": (700, 989_000_000_000_000),
    "l4": (72, 121_000_000_000_000),
    "t4": (70, 65_000_000_000_000),
    "v100": (300, 125_000_000_000_000),
    "cpu": (150, 5_000_000_000_000),
}

# ---------------------------------------------------------------------------
# Equivalence helpers
# ---------------------------------------------------------------------------


def _build_equivalence_text(
    kwh: float,
    co2e_kg: float,
) -> str:
    parts: list[str] = []

    km = co2e_kg / 0.2 if co2e_kg > 0 else 0.0
    if km > 0.1:
        parts.append(f"~{km:.1f} km of driving")

    tree_months = co2e_kg / 1.83 if co2e_kg > 0 else 0.0
    if tree_months > 0.1:
        parts.append(f"~{tree_months:.1f} tree-months of sequestration")

    charges = kwh / 0.005 if kwh > 0 else 0.0
    if charges > 1:
        parts.append(f"~{charges:.0f} smartphone charges")

    if not parts:
        return "Negligible carbon impact."

    return "Equivalent to " + ", ".join(parts) + "."


# ---------------------------------------------------------------------------
# CarbonBudgetTracker
# ---------------------------------------------------------------------------


class CarbonBudgetTracker:
    """Tracks per-query carbon estimates and enforces monthly budget limits.

    Uses SQLite for cumulative budget persistence across restarts.
    Designed to be injected into EthicalFirewall and called after each
    LLM inference completes.
    """

    def __init__(
        self,
        budget_kwh: float = 50.0,
        warning_threshold: float = 0.8,
        grid_intensity_kg_co2e_per_kwh: float = 0.4,
        hardware_tdp_watts: int = 350,
        hardware_flops: int = 142_000_000_000_000,
        model_params: int = 7_000_000_000,
        equivalences_enabled: bool = True,
        db_path: str = "data/carbon_budget.db",
        provenance_tracker: Any = None,  # noqa: ANN401
    ) -> None:
        self._budget_kwh = budget_kwh
        self._warning_threshold = warning_threshold
        self._grid_intensity = grid_intensity_kg_co2e_per_kwh
        self._tdp_watts = hardware_tdp_watts
        self._flops_per_second = hardware_flops
        self._model_params = model_params
        self._equivalences_enabled = equivalences_enabled
        self._provenance_tracker = provenance_tracker

        self._db_path = str(Path(db_path).resolve())
        self._init_db()

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        db_dir = Path(self._db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS carbon_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id TEXT NOT NULL,
                    decision_id TEXT DEFAULT '',
                    kwh REAL NOT NULL,
                    co2e_kg REAL NOT NULL,
                    month TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _current_month_key(self) -> str:
        return datetime.now().strftime("%Y-%m")

    def _sum_monthly_kwh(self, month: str | None = None) -> float:
        if month is None:
            month = self._current_month_key()
        conn = sqlite3.connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT COALESCE(SUM(kwh), 0.0) FROM carbon_usage WHERE month = ?",
                (month,),
            ).fetchone()
            return float(row[0]) if row else 0.0
        finally:
            conn.close()

    def _delete_month(self, month: str) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("DELETE FROM carbon_usage WHERE month = ?", (month,))
            conn.commit()
        finally:
            conn.close()

    def _insert_record(
        self,
        record_id: str,
        decision_id: str,
        kwh: float,
        co2e_kg: float,
        month: str,
    ) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            sql = (
                "INSERT INTO carbon_usage "
                "(record_id, decision_id, kwh, co2e_kg, month, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)"
            )
            conn.execute(
                sql,
                (record_id, decision_id, kwh, co2e_kg, month, datetime.now().isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Estimation
    # ------------------------------------------------------------------

    def estimate(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        model_params: int | None = None,
    ) -> CarbonEstimate:
        """Estimate carbon cost for an inference query.

        Args:
            prompt_tokens: Number of input tokens.
            completion_tokens: Number of output tokens.
            model_params: Override for model parameter count (default from config).

        Returns:
            A CarbonEstimate with FLOPs, kWh, CO2e, and equivalence text.
        """
        params = model_params or self._model_params
        total_tokens = prompt_tokens + completion_tokens

        flops = 2.0 * params * (prompt_tokens + 3.0 * completion_tokens)
        if flops < 0:
            flops = 0.0

        time_seconds = flops / self._flops_per_second if self._flops_per_second > 0 else 0.0
        kwh_tdp = (self._tdp_watts * time_seconds) / 3_600_000.0

        kwh_efficiency = total_tokens * 0.0004
        kwh = max(kwh_tdp, kwh_efficiency)

        co2e_kg = kwh * self._grid_intensity

        eq_text = ""
        if self._equivalences_enabled:
            eq_text = _build_equivalence_text(kwh, co2e_kg)

        return CarbonEstimate(
            flops=flops,
            kwh=kwh,
            co2e_kg=co2e_kg,
            equivalence_text=eq_text,
        )

    # ------------------------------------------------------------------
    # Tracking
    # ------------------------------------------------------------------

    def track_query(
        self,
        estimate: CarbonEstimate,
        decision_id: str = "",
    ) -> CarbonRecord:
        """Record a carbon estimate and check budget thresholds.

        Args:
            estimate: The CarbonEstimate from the query.
            decision_id: The firewall decision ID for provenance linking.

        Returns:
            A CarbonRecord with budget context.

        Raises:
            EthicsError: If monthly budget is already exhausted (≥100%).
        """
        record_id = uuid.uuid4().hex[:12]
        month = self._current_month_key()

        self._insert_record(
            record_id=record_id,
            decision_id=decision_id,
            kwh=estimate.kwh,
            co2e_kg=estimate.co2e_kg,
            month=month,
        )

        current_usage = self._sum_monthly_kwh(month)
        percentage = (current_usage / self._budget_kwh * 100.0) if self._budget_kwh > 0 else 100.0
        warning = percentage >= self._warning_threshold * 100.0
        blocked = current_usage >= self._budget_kwh

        if self._provenance_tracker is not None:
            import contextlib

            with contextlib.suppress(Exception):
                self._provenance_tracker.track(
                    action_type="carbon_estimate",
                    params={
                        "record_id": record_id,
                        "decision_id": decision_id,
                        "kwh": estimate.kwh,
                        "co2e_kg": estimate.co2e_kg,
                        "monthly_usage_kwh": current_usage,
                        "monthly_budget_kwh": self._budget_kwh,
                        "percentage_used": percentage,
                        "warning": warning,
                        "blocked": blocked,
                    },
                )

        if warning:
            logger.warning(
                "Carbon budget warning: usage=%.4f kWh, budget=%.4f kWh, percentage=%.1f%%",
                current_usage,
                self._budget_kwh,
                percentage,
            )

        if blocked:
            raise EthicsError(
                message=(
                    f"Monthly carbon budget of {self._budget_kwh} kWh exceeded. "
                    f"Current usage: {current_usage:.3f} kWh ({percentage:.1f}%). "
                    "Reduce query volume or increase budget."
                ),
                source="carbon.track_query",
                error_code=ErrorCode.ETHICS_CARBON_BUDGET_EXCEEDED,
            )

        return CarbonRecord(
            record_id=record_id,
            decision_id=decision_id,
            estimate=estimate,
            monthly_usage_kwh=current_usage,
            monthly_budget_kwh=self._budget_kwh,
            percentage_used=percentage,
            warning_triggered=warning,
            blocked=blocked,
        )

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def current_monthly_usage(self) -> float:
        """Return kWh consumed in the current month."""
        return self._sum_monthly_kwh()

    def budget_status(self) -> BudgetStatus:
        """Return the current cumulative budget status."""
        usage = self._sum_monthly_kwh()
        percentage = (usage / self._budget_kwh * 100.0) if self._budget_kwh > 0 else 100.0
        return BudgetStatus(
            current_usage_kwh=usage,
            budget_kwh=self._budget_kwh,
            percentage_used=percentage,
            warning=percentage >= self._warning_threshold * 100.0,
            blocked=usage >= self._budget_kwh,
        )

    def reset_monthly_budget(self, month: str | None = None) -> None:
        """Reset cumulative usage for a given month (for testing/admin).

        Args:
            month: Month key in YYYY-MM format (default: current month).
        """
        if month is None:
            month = self._current_month_key()
        self._delete_month(month)

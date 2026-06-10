from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from openscire.references.retraction.crossref_feed import CrossrefRetractionClient
from openscire.references.retraction.database import RetractionDatabase
from openscire.references.retraction.models import (
    RetractionRecord,
    RetractionSource,
    RetractionStatus,
)
from openscire.references.retraction.pubmed_feed import PubMedRetractionClient
from openscire.references.retraction.pubpeer import PubPeerClient

logger = logging.getLogger(__name__)


FlagCallback = Callable[[str, RetractionStatus, RetractionStatus, list[RetractionRecord]], None]


class RetractionMonitor:
    def __init__(
        self,
        database: RetractionDatabase,
        pubmed_client: PubMedRetractionClient | None = None,
        crossref_client: CrossrefRetractionClient | None = None,
        pubpeer_client: PubPeerClient | None = None,
        openalex_is_retracted_fn: Callable[[str], bool] | None = None,
        provenance_tracker: Any | None = None,  # noqa: ANN401
    ) -> None:
        self._db = database
        self._pubmed = pubmed_client
        self._crossref = crossref_client
        self._pubpeer = pubpeer_client
        self._openalex_is_retracted = openalex_is_retracted_fn
        self._provenance = provenance_tracker
        self._on_flag_callbacks: list[FlagCallback] = []

    def on_flag(self, callback: FlagCallback) -> None:
        self._on_flag_callbacks.append(callback)

    async def check_paper(
        self,
        doi: str,
    ) -> tuple[RetractionStatus, list[RetractionRecord]]:
        records: list[RetractionRecord] = []
        worst = RetractionStatus.unchecked

        sources_to_check = [
            ("openalex", self._check_openalex),
            ("pubmed", self._check_pubmed),
            ("crossref", self._check_crossref),
            ("pubpeer", self._check_pubpeer),
        ]

        for _name, check_fn in sources_to_check:
            with suppress(Exception):
                result = await check_fn(doi)
                if result is not None:
                    records.append(result)
                    self._db.upsert(result)
                    if self._is_worse(result.retraction_status, worst):
                        worst = result.retraction_status

        track_data = {
            "identifier": doi,
            "sources_checked": len(records),
            "worst_status": worst.value,
        }
        self._emit_provenance("retraction_check", track_data)
        return worst, records

    async def check_batch(
        self,
        dois: list[str],
    ) -> dict[str, tuple[RetractionStatus, list[RetractionRecord]]]:
        results: dict[str, tuple[RetractionStatus, list[RetractionRecord]]] = {}
        for doi in dois:
            results[doi] = await self.check_paper(doi)
        return results

    async def check_stored_papers(
        self,
        max_age: int = 86400,
    ) -> int:
        stale = self._db.list_needing_update(max_age_seconds=max_age)
        flagged = 0
        for record in stale:
            prev_status = record.retraction_status
            new_status, new_records = await self.check_paper(record.identifier)

            if self._is_worse(new_status, prev_status):
                flagged += 1
                for cb in self._on_flag_callbacks:
                    with suppress(Exception):
                        cb(record.identifier, prev_status, new_status, new_records)
                track_data = {
                    "identifier": record.identifier,
                    "prev_status": prev_status.value,
                    "new_status": new_status.value,
                }
                self._emit_provenance("retraction_flagged", track_data)

        return flagged

    async def refresh_if_needed(
        self,
        doi: str,
        max_age: int = 86400,
    ) -> RetractionStatus | None:
        existing = self._db.get(doi)
        if existing is None:
            status, _records = await self.check_paper(doi)
            return status

        if self._is_stale(existing, max_age):
            new_status, _records = await self.check_paper(doi)
            return new_status

        return existing.retraction_status

    def needs_update(self, doi: str, max_age: int = 86400) -> bool:
        existing = self._db.get(doi)
        if existing is None:
            return True
        return self._is_stale(existing, max_age)

    def get_status(self, doi: str) -> RetractionStatus:
        existing = self._db.get(doi)
        if existing is None:
            return RetractionStatus.unchecked
        return existing.retraction_status

    def invalidate_citations(
        self,
        doi: str,
        claims: list[Any] | None = None,
        sources: list[Any] | None = None,
    ) -> dict[str, list[str]]:
        invalidated_claims: list[str] = []
        invalidated_sources: list[str] = []

        if claims is not None:
            try:
                from openscire.models.models import ScientificClaim

                for claim in claims:
                    if isinstance(claim, ScientificClaim):
                        refs = [r.lower() for r in claim.source_references]
                        if doi.lower() in refs:
                            claim.verification_status = type(claim.verification_status).retracted
                            invalidated_claims.append(claim.field)
            except ImportError:
                logger.debug("ScientificClaim not available — skipping claim invalidation")

        if sources is not None:
            try:
                from openscire.ethics.models import Source

                for s in sources:
                    if isinstance(s, Source) and s.doi.lower() == doi.lower():
                        s.retracted = True
                        invalidated_sources.append(s.source_id)
            except ImportError:
                logger.debug("Source model not available — skipping source invalidation")

        track_data = {
            "identifier": doi,
            "invalidated_claims": invalidated_claims,
            "invalidated_sources": invalidated_sources,
        }
        self._emit_provenance("retraction_invalidated", track_data)
        return {
            "claims": invalidated_claims,
            "sources": invalidated_sources,
        }

    async def _check_openalex(self, doi: str) -> RetractionRecord | None:
        if self._openalex_is_retracted is None:
            return None
        try:
            is_ret = self._openalex_is_retracted(doi)
        except Exception:
            return None
        if not is_ret:
            return None
        return RetractionRecord(
            identifier=doi,
            retraction_status=RetractionStatus.retracted,
            source=RetractionSource.openalex,
            detected_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            notice_text="Marked as retracted in OpenAlex",
        )

    async def _check_pubmed(self, doi: str) -> RetractionRecord | None:
        if self._pubmed is None:
            return None
        results = await self._pubmed.search_retracted(max_results=200)
        for summary in results:
            if summary.get("doi", "").lower() == doi.lower():
                return await self._pubmed.to_retraction_record(summary)
        return None

    async def _check_crossref(self, doi: str) -> RetractionRecord | None:
        if self._crossref is None:
            return None
        detail = await self._crossref.get_correction_detail(doi)
        updates = detail.get("update-to") or []
        for update in updates:
            utype = (update.get("type") or "").lower()
            if utype in ("retraction", "correction", "expression-of-concern"):
                item = {
                    "DOI": detail.get("DOI", ""),
                    "title": detail.get("title", [""]),
                }
                return await self._crossref.to_retraction_record(item, update)
        return None

    async def _check_pubpeer(self, doi: str) -> RetractionRecord | None:
        if self._pubpeer is None:
            return None
        concerns = await self._pubpeer.get_concerns(doi)
        if not concerns:
            return None
        return await self._pubpeer.to_retraction_record(concerns[0])

    def _emit_provenance(self, action_type: str, data: dict[str, Any]) -> None:
        if self._provenance is None:
            return
        try:
            from openscire.provenance.tracker import ProvenanceTracker

            if isinstance(self._provenance, ProvenanceTracker):
                self._provenance.track(
                    action_type=action_type,
                    params=data,
                )
        except ImportError:
            logger.debug("ProvenanceTracker not available — skipping provenance")
        except Exception:
            logger.warning("Failed to record provenance for %s", action_type, exc_info=True)

    @staticmethod
    def _is_worse(
        new: RetractionStatus,
        current: RetractionStatus,
    ) -> bool:
        severity = [
            RetractionStatus.unchecked,
            RetractionStatus.unknown,
            RetractionStatus.corrected,
            RetractionStatus.concern_raised,
            RetractionStatus.expression_of_concern,
            RetractionStatus.retracted,
        ]
        try:
            return severity.index(new) > severity.index(current)
        except ValueError:
            return False

    @staticmethod
    def _is_stale(record: RetractionRecord, max_age: int) -> bool:
        updated = record.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=UTC)
        age = (datetime.now(UTC) - updated).total_seconds()
        return age > max_age

    async def close(self) -> None:
        if self._pubmed:
            await self._pubmed.close()
        if self._crossref:
            await self._crossref.close()
        if self._pubpeer:
            await self._pubpeer.close()
        self._db.close()

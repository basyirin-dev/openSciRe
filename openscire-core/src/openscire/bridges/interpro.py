# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
import math
import re
from enum import StrEnum
from typing import Any

import httpx
from pydantic import BaseModel, Field

from openscire.bridge.confidence import ConfidenceTrace
from openscire.bridge.evidence_label import EvidenceTypeLabel
from openscire.bridge.rate_limiter import TokenBucketRateLimiter
from openscire.exceptions import ReferenceError

logger = logging.getLogger(__name__)


class SignatureDBMethod(StrEnum):
    HMM = "HMM"
    RPS_BLAST = "RPS-BLAST"
    PATTERN = "pattern"
    PROFILE = "profile"
    FINGERPRINT = "fingerprint"


class SignatureDBMeta(BaseModel):
    database: str = ""
    method: SignatureDBMethod = SignatureDBMethod.HMM
    description: str = ""


_SIGNATURE_DB_META: dict[str, SignatureDBMeta] = {
    "pfam": SignatureDBMeta(
        database="Pfam",
        method=SignatureDBMethod.HMM,
        description="Protein families",
    ),
    "cdd": SignatureDBMeta(
        database="CDD",
        method=SignatureDBMethod.RPS_BLAST,
        description="Conserved Domain Database",
    ),
    "panther": SignatureDBMeta(
        database="PANTHER",
        method=SignatureDBMethod.HMM,
        description="Protein family classification",
    ),
    "smart": SignatureDBMeta(
        database="SMART",
        method=SignatureDBMethod.HMM,
        description="Simple Modular Architecture Research Tool",
    ),
    "prosite": SignatureDBMeta(
        database="PROSITE",
        method=SignatureDBMethod.PATTERN,
        description="Protein domain patterns",
    ),
    "profile": SignatureDBMeta(
        database="PROSITE Profiles",
        method=SignatureDBMethod.PROFILE,
        description="PROSITE profile",
    ),
    "prints": SignatureDBMeta(
        database="PRINTS",
        method=SignatureDBMethod.FINGERPRINT,
        description="Protein fingerprints",
    ),
    "hamap": SignatureDBMeta(
        database="HAMAP",
        method=SignatureDBMethod.HMM,
        description="High-quality Automated and Manual Annotation of Proteins",
    ),
    "pirsf": SignatureDBMeta(
        database="PIRSF",
        method=SignatureDBMethod.HMM,
        description="Protein Information Resource SuperFamily",
    ),
    "sfld": SignatureDBMeta(
        database="SFLD",
        method=SignatureDBMethod.HMM,
        description="Structure-Function Linkage Database",
    ),
    "cathgene3d": SignatureDBMeta(
        database="CATH-Gene3D",
        method=SignatureDBMethod.HMM,
        description="Protein domain superfamilies",
    ),
    "ssf": SignatureDBMeta(
        database="SUPERFAMILY",
        method=SignatureDBMethod.HMM,
        description="Structural classification of proteins",
    ),
    "ncbifam": SignatureDBMeta(
        database="NCBIFAM",
        method=SignatureDBMethod.HMM,
        description="NCBI protein families",
    ),
}


class GoTerm(BaseModel):
    identifier: str = ""
    name: str = ""
    category: str = ""


class LiteratureRef(BaseModel):
    pmid: str = ""
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    year: int = 0
    doi: str = ""


class MemberDatabaseEntry(BaseModel):
    database: str = ""
    accession: str = ""
    name: str = ""


class MatchLocation(BaseModel):
    start: int = 0
    end: int = 0


class InterProMatch(BaseModel):
    accession: str = ""
    name: str = ""
    type: str = ""
    source_db: str = ""
    signature_accession: str = ""
    description: str = ""
    e_value: float | None = None
    score: float | None = None
    locations: list[MatchLocation] = Field(default_factory=list)
    evidence_label: EvidenceTypeLabel = EvidenceTypeLabel.PREDICTED
    extra: dict[str, Any] = Field(default_factory=dict)

    def to_confidence_trace(self) -> ConfidenceTrace:
        confidence = _evalue_to_confidence(self.e_value) if self.e_value is not None else 0.5
        return ConfidenceTrace(
            value=round(confidence, 6),
            source="interpro",
            weight=1.0,
        )


class InterProEntry(BaseModel):
    accession: str = ""
    entry_id: str | None = None
    name: str = ""
    short_name: str = ""
    type: str = ""
    source_database: str = ""
    description: str = ""
    go_terms: list[GoTerm] = Field(default_factory=list)
    member_databases: list[MemberDatabaseEntry] = Field(default_factory=list)
    literature: list[LiteratureRef] = Field(default_factory=list)
    counters: dict[str, Any] = Field(default_factory=dict)
    cross_references: dict[str, Any] = Field(default_factory=dict)
    entry_date: str = ""
    evidence_label: EvidenceTypeLabel = EvidenceTypeLabel.PREDICTED
    extra: dict[str, Any] = Field(default_factory=dict)


class InterProProteinEntry(BaseModel):
    accession: str = ""
    source_database: str = ""
    matches: list[InterProMatch] = Field(default_factory=list)


class InterProScanResult(BaseModel):
    job_id: str = ""
    status: str = ""
    sequence: str = ""
    matches: list[InterProMatch] = Field(default_factory=list)


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub("", text).strip()


def _evalue_to_confidence(e_value: float) -> float:
    if e_value <= 0.0:
        return 1.0
    return math.exp(-e_value)


class InterProClient:
    BASE_URL = "https://www.ebi.ac.uk/interpro/api"

    def __init__(
        self,
        timeout: int = 30,
        rate: float = 5.0,
        burst: int = 2,
        e_value_threshold: float = 1.0,
        strict_evalue_experimental: bool = False,
    ) -> None:
        self._rate_limiter = TokenBucketRateLimiter(rate=rate, burst=burst)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )
        self.e_value_threshold = e_value_threshold
        self._strict_evalue_experimental = strict_evalue_experimental

    async def _get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> Any:  # noqa: ANN401
        await self._rate_limiter.acquire()
        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise ReferenceError(
                f"InterPro API error: {e.response.status_code} {e.response.text[:200]}",
                source="interpro",
            ) from e
        except Exception as e:
            raise ReferenceError(
                f"InterPro request failed: {e}",
                source="interpro",
            ) from e

    # --- 4.19.1: Entry query ---

    async def get_entry(self, accession: str) -> InterProEntry:
        data = await self._get_json(f"{self.BASE_URL}/entry/interpro/{accession}")
        return self._parse_entry(data)

    async def search_entries(
        self,
        source: str = "interpro",
        query: str = "",
        page_size: int = 20,
    ) -> list[InterProEntry]:
        params: dict[str, Any] = {"page_size": min(page_size, 200)}
        if query:
            params["search"] = query
        url = f"{self.BASE_URL}/entry/{source}"
        entries: list[InterProEntry] = []
        remaining = page_size
        while url and remaining > 0:
            data = await self._get_json(url, params=params)
            results = data.get("results", [])
            for item in results:
                if remaining <= 0:
                    break
                entries.append(self._parse_entry(item))
                remaining -= 1
            url = data.get("next", "")
        return entries

    async def get_entry_by_source(
        self,
        source: str,
        accession: str,
    ) -> InterProEntry:
        data = await self._get_json(f"{self.BASE_URL}/entry/{source}/{accession}")
        return self._parse_entry(data)

    # --- Protein queries ---

    async def get_protein_entries(
        self,
        uniprot_accession: str,
        source: str = "interpro",
    ) -> list[InterProProteinEntry]:
        url = f"{self.BASE_URL}/entry/{source}/protein/uniprot/{uniprot_accession}"
        data = await self._get_json(url)
        results = data.get("results", [])
        return [self._parse_protein_entry(r) for r in results]

    async def get_protein_matches(
        self,
        uniprot_accession: str,
    ) -> list[InterProMatch]:
        url = f"{self.BASE_URL}/protein/uniprot/{uniprot_accession}?residues"
        data = await self._get_json(url)
        return self._parse_protein_matches(data)

    # --- 4.19.3: E-value filtering ---

    @staticmethod
    def filter_matches(
        matches: list[InterProMatch],
        threshold: float | None = None,
    ) -> list[InterProMatch]:
        if threshold is None:
            return list(matches)
        return [m for m in matches if m.e_value is None or m.e_value <= threshold]

    # --- 4.19.4: Signature metadata ---

    @staticmethod
    def get_signature_metadata(db_name: str) -> SignatureDBMeta | None:
        return _SIGNATURE_DB_META.get(db_name)

    @staticmethod
    def get_match_method(match: InterProMatch) -> str:
        meta = _SIGNATURE_DB_META.get(match.source_db)
        if meta is not None:
            return meta.method.value
        return "unknown"

    @staticmethod
    def list_signature_databases() -> dict[str, SignatureDBMeta]:
        return dict(_SIGNATURE_DB_META)

    # --- Response parsing ---

    def _parse_entry(self, data: dict[str, Any]) -> InterProEntry:
        meta = data.get("metadata") or data
        accession = meta.get("accession", "")
        source_db = meta.get("source_database", "")

        name_data = meta.get("name") or {}
        name = ""
        short_name = ""
        if isinstance(name_data, dict):
            name = name_data.get("name", "")
            short_name = name_data.get("short", "")
        elif isinstance(name_data, str):
            name = name_data

        raw_descriptions = meta.get("description") or []
        description = " ".join(
            _strip_html(d.get("text", ""))
            for d in raw_descriptions
            if isinstance(d, dict) and d.get("text")
        )

        go_terms = self._parse_go_terms(meta.get("go_terms") or [])
        member_dbs = self._parse_member_databases(
            meta.get("member_databases") or {},
        )
        literature = self._parse_literature(meta.get("literature") or {})

        counters: dict[str, Any] = {}
        raw_counters = meta.get("counters") or {}
        if isinstance(raw_counters, dict):
            counters = dict(raw_counters)

        cr: dict[str, Any] = meta.get("cross_references") or {}

        entry_type = meta.get("type", "")

        evidence_label = EvidenceTypeLabel.PREDICTED

        return InterProEntry(
            accession=accession,
            entry_id=meta.get("entry_id", ""),
            name=name,
            short_name=short_name,
            type=entry_type,
            source_database=source_db,
            description=description,
            go_terms=go_terms,
            member_databases=member_dbs,
            literature=literature,
            counters=counters,
            cross_references=cr,
            entry_date=meta.get("entry_date", ""),
            evidence_label=evidence_label,
            extra={
                "integrated": meta.get("integrated"),
                "wikipedia": meta.get("wikipedia"),
                "is_llm": meta.get("is_llm"),
                "is_reviewed_llm": meta.get("is_reviewed_llm"),
                "representative_structure": meta.get("representative_structure"),
            },
        )

    @staticmethod
    def _parse_protein_entry(data: dict[str, Any]) -> InterProProteinEntry:
        meta = data.get("metadata") or data
        acc = meta.get("accession", "")
        source_db = meta.get("source_database", "")
        return InterProProteinEntry(
            accession=acc,
            source_database=source_db,
        )

    def _parse_protein_matches(
        self,
        data: dict[str, Any],
    ) -> list[InterProMatch]:
        meta = data.get("metadata") or data
        entries = meta.get("entries") or meta.get("results") or []
        matches: list[InterProMatch] = []
        for entry in entries:
            entry_meta = entry.get("metadata") or entry
            acc = entry_meta.get("accession", "")
            name = self._get_entry_name(entry_meta)
            entry_type = entry_meta.get("type", "")
            db = entry_meta.get("source_database", "")

            locations_raw = entry.get("locations") or entry.get(
                "entry_protein_locations",
            ) or []
            locations: list[MatchLocation] = []
            for loc in locations_raw:
                fragments = loc.get("fragments") or [loc]
                for frag in fragments:
                    locations.append(MatchLocation(
                        start=frag.get("start", 0),
                        end=frag.get("end", 0),
                    ))

            matches.append(InterProMatch(
                accession=acc,
                name=name,
                type=entry_type,
                source_db=db,
                locations=locations,
            ))
        return matches

    @staticmethod
    def _get_entry_name(meta: dict[str, Any]) -> str:
        name_data = meta.get("name") or {}
        if isinstance(name_data, dict):
            return name_data.get("name", "")
        if isinstance(name_data, str):
            return name_data
        return ""

    @staticmethod
    def _parse_go_terms(
        go_data: list[dict[str, Any]],
    ) -> list[GoTerm]:
        terms: list[GoTerm] = []
        for g in go_data:
            if not isinstance(g, dict):
                continue
            cat_data = g.get("category") or {}
            cat_code = ""
            if isinstance(cat_data, dict):
                cat_code = cat_data.get("code", "")
            elif isinstance(cat_data, str):
                cat_code = cat_data
            terms.append(GoTerm(
                identifier=g.get("identifier", ""),
                name=g.get("name", ""),
                category=cat_code,
            ))
        return terms

    @staticmethod
    def _parse_member_databases(
        md: dict[str, dict[str, str]],
    ) -> list[MemberDatabaseEntry]:
        entries: list[MemberDatabaseEntry] = []
        for db_name, signatures in md.items():
            if isinstance(signatures, dict):
                for sig_acc, sig_name in signatures.items():
                    entries.append(MemberDatabaseEntry(
                        database=db_name,
                        accession=sig_acc,
                        name=str(sig_name),
                    ))
            elif isinstance(signatures, list):
                for sig in signatures:
                    if isinstance(sig, dict):
                        entries.append(MemberDatabaseEntry(
                            database=db_name,
                            accession=sig.get("accession", ""),
                            name=sig.get("name", ""),
                        ))
        return entries

    @staticmethod
    def _parse_literature(
        lit: dict[str, dict[str, Any]],
    ) -> list[LiteratureRef]:
        refs: list[LiteratureRef] = []
        for _pub_id, details in lit.items():
            if not isinstance(details, dict):
                continue
            authors_raw = details.get("authors") or []
            authors: list[str] = []
            for a in authors_raw:
                if isinstance(a, str):
                    authors.append(a)
                elif isinstance(a, dict):
                    authors.append(a.get("name", ""))
            refs.append(LiteratureRef(
                pmid=str(details.get("PMID", "")),
                title=details.get("title", ""),
                authors=authors,
                year=details.get("year", 0) or 0,
                doi=details.get("DOI_URL", "").replace("http://dx.doi.org/", ""),
            ))
        return refs

    async def close(self) -> None:
        await self._client.aclose()


class InterProScanClient:
    BASE_URL = "https://www.ebi.ac.uk/Tools/services/rest/iprscan5"

    def __init__(
        self,
        timeout: int = 60,
        rate: float = 5.0,
        burst: int = 2,
        poll_interval: float = 5.0,
        poll_timeout: float = 300.0,
    ) -> None:
        self._rate_limiter = TokenBucketRateLimiter(rate=rate, burst=burst)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout

    async def _get_text(self, url: str) -> str:
        await self._rate_limiter.acquire()
        try:
            response = await self._client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            raise ReferenceError(
                f"InterProScan API error: {e.response.status_code} {e.response.text[:200]}",
                source="interpro",
            ) from e
        except httpx.RequestError as e:
            raise ReferenceError(
                f"InterProScan request failed: {e}",
                source="interpro",
            ) from e

    async def _get_json(self, url: str) -> Any:  # noqa: ANN401
        await self._rate_limiter.acquire()
        try:
            response = await self._client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise ReferenceError(
                f"InterProScan API error: {e.response.status_code} {e.response.text[:200]}",
                source="interpro",
            ) from e
        except httpx.RequestError as e:
            raise ReferenceError(
                f"InterProScan request failed: {e}",
                source="interpro",
            ) from e

    async def _post_form(
        self,
        url: str,
        data: dict[str, str],
    ) -> httpx.Response:
        await self._rate_limiter.acquire()
        try:
            response = await self._client.post(url, data=data)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            raise ReferenceError(
                f"InterProScan submission error: {e.response.status_code} {e.response.text[:200]}",
                source="interpro",
            ) from e
        except httpx.RequestError as e:
            raise ReferenceError(
                f"InterProScan submission failed: {e}",
                source="interpro",
            ) from e

    async def submit_sequence(
        self,
        sequence: str,
        stype: str = "p",
        email: str = "",
        appl: list[str] | None = None,
    ) -> str:
        if not sequence.strip():
            msg = "Sequence is empty"
            raise ReferenceError(msg, source="interpro")
        data: dict[str, str] = {
            "sequence": sequence,
            "stype": stype,
        }
        if email:
            data["email"] = email
        if appl:
            data["appl"] = ",".join(appl)
        response = await self._post_form(f"{self.BASE_URL}/run", data=data)
        job_id = response.text.strip()
        if not job_id:
            msg = "No job ID returned from InterProScan"
            raise ReferenceError(msg, source="interpro")
        return job_id

    async def poll_status(self, job_id: str) -> str:
        status = await self._get_text(f"{self.BASE_URL}/status/{job_id}")
        return status.strip().upper()

    async def get_results(self, job_id: str) -> list[InterProMatch]:
        data = await self._get_json(f"{self.BASE_URL}/result/{job_id}/json")
        return self._parse_scan_result(data)

    async def scan_sequence(
        self,
        sequence: str,
        stype: str = "p",
        email: str = "",
        appl: list[str] | None = None,
    ) -> InterProScanResult:
        import asyncio

        job_id = await self.submit_sequence(
            sequence, stype=stype, email=email, appl=appl,
        )
        elapsed = 0.0
        while elapsed < self.poll_timeout:
            status = await self.poll_status(job_id)
            if status == "FINISHED":
                matches = await self.get_results(job_id)
                return InterProScanResult(
                    job_id=job_id,
                    status="FINISHED",
                    matches=matches,
                )
            if status in ("ERROR", "NOT_FOUND"):
                return InterProScanResult(
                    job_id=job_id,
                    status=status,
                )
            await asyncio.sleep(self.poll_interval)
            elapsed += self.poll_interval
        return InterProScanResult(
            job_id=job_id,
            status="TIMEOUT",
        )

    # --- Response parsing ---

    def _parse_scan_result(
        self,
        data: list[dict[str, Any]],
    ) -> list[InterProMatch]:
        matches: list[InterProMatch] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            match_data = item.get("match", {})
            sig_data = match_data.get("signature", {}) or {}
            acc = sig_data.get("accession", "")
            name = sig_data.get("name", "")
            db_data = sig_data.get("database", {}) or {}
            source_db = db_data.get("name", "").lower()
            description = sig_data.get("description", "")

            entry_data = match_data.get("entry", {}) or {}
            entry_acc = entry_data.get("accession", acc)
            entry_type = entry_data.get("type", "")

            locations: list[MatchLocation] = []
            locations_raw = match_data.get("locations", [])
            for loc in locations_raw:
                start = loc.get("start", 0)
                end = loc.get("end", 0)
                if start and end:
                    locations.append(MatchLocation(start=start, end=end))

            evidence_label = EvidenceTypeLabel.PREDICTED

            matches.append(InterProMatch(
                accession=entry_acc,
                name=name,
                type=entry_type,
                source_db=source_db,
                signature_accession=acc,
                description=description,
                e_value=sig_data.get("e_value"),
                score=sig_data.get("score"),
                locations=locations,
                evidence_label=evidence_label,
                extra={
                    "full_db_name": db_data.get("name", ""),
                    "db_version": db_data.get("version", ""),
                    "model_length": sig_data.get("signature_model", {}).get("length"),
                },
            ))
        return matches

    async def close(self) -> None:
        await self._client.aclose()

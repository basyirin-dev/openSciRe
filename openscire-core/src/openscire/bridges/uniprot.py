# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import BaseModel, Field

from openscire.bridge.evidence_label import EvidenceTypeLabel
from openscire.bridge.rate_limiter import TokenBucketRateLimiter
from openscire.exceptions import ReferenceError

logger = logging.getLogger(__name__)

# Target databases for cross-reference extraction (4.15.6)
_TARGET_XREF_DBS = frozenset(
    {
        "PDB",
        "EMBL",
        "Pfam",
        "InterPro",
        "STRING",
        "Reactome",
        "GO",
    }
)


class UniProtFeature(BaseModel):
    type: str = ""
    description: str = ""
    feature_id: str = ""
    start: int | None = None
    end: int | None = None
    evidence_codes: list[str] = Field(default_factory=list)


class CrossReference(BaseModel):
    database: str = ""
    identifier: str = ""
    properties: dict[str, str] = Field(default_factory=dict)


class UniProtComment(BaseModel):
    comment_type: str = ""
    texts: list[str] = Field(default_factory=list)
    evidence_codes: list[str] = Field(default_factory=list)


class UniProtResult(BaseModel):
    primary_accession: str = ""
    entry_name: str = ""
    entry_type: str = ""
    is_reviewed: bool = False
    protein_names: list[str] = Field(default_factory=list)
    gene_names: list[str] = Field(default_factory=list)
    organism: str = ""
    organism_taxon_id: int | None = None
    protein_existence: str = ""
    function: str = ""
    subcellular_location: list[str] = Field(default_factory=list)
    ptms: list[str] = Field(default_factory=list)
    sequence: str = ""
    sequence_length: int = 0
    molecular_weight: int | None = None
    features: list[UniProtFeature] = Field(default_factory=list)
    comments: list[UniProtComment] = Field(default_factory=list)
    cross_references: list[CrossReference] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    evidence_label: EvidenceTypeLabel = EvidenceTypeLabel.EXPERIMENTAL
    entry_version: int = 0
    sequence_version: int = 0
    first_public_date: str = ""
    last_annotation_update: str = ""
    last_sequence_update: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class UniProtSearchResult(BaseModel):
    results: list[UniProtResult] = Field(default_factory=list)
    total_count: int = 0
    page: int = 0
    page_size: int = 0


class UniProtQueryBuilder:
    def __init__(self) -> None:
        self._parts: list[str] = []

    def organism(self, tax_id: int) -> UniProtQueryBuilder:
        self._parts.append(f"organism_id:{tax_id}")
        return self

    def gene(self, name: str) -> UniProtQueryBuilder:
        self._parts.append(f"gene:{name}")
        return self

    def protein(self, name: str) -> UniProtQueryBuilder:
        self._parts.append(f"protein_name:{name}")
        return self

    def sequence_length(self, min_len: int = 0, max_len: int = 0) -> UniProtQueryBuilder:
        if min_len > 0 and max_len > 0:
            self._parts.append(f"length:[{min_len} TO {max_len}]")
        elif min_len > 0:
            self._parts.append(f"length:[{min_len} TO *]")
        elif max_len > 0:
            self._parts.append(f"length:[1 TO {max_len}]")
        return self

    def reviewed(self, reviewed: bool = True) -> UniProtQueryBuilder:
        self._parts.append(f"reviewed:{str(reviewed).lower()}")
        return self

    def taxonomy(self, name: str) -> UniProtQueryBuilder:
        self._parts.append(f"taxonomy_name:{name}")
        return self

    def build(self) -> str:
        return " AND ".join(self._parts)


class UniProtClient:
    BASE_URL = "https://rest.uniprot.org"

    def __init__(
        self,
        timeout: int = 30,
        rate: float = 5.0,
        burst: int = 2,
    ) -> None:
        self._rate_limiter = TokenBucketRateLimiter(rate=rate, burst=burst)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )

    async def _get(
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
                f"UniProt API error: {e.response.status_code} {e.response.text[:200]}",
                source="uniprot",
            ) from e
        except httpx.RequestError as e:
            raise ReferenceError(
                f"UniProt request failed: {e}",
                source="uniprot",
            ) from e

    # --- 4.15.1: REST API endpoints ---

    async def search(
        self,
        query: str | UniProtQueryBuilder,
        size: int = 25,
        offset: int = 0,
    ) -> UniProtSearchResult:
        if isinstance(query, UniProtQueryBuilder):
            query = query.build()
        params: dict[str, Any] = {
            "query": query,
            "size": min(size, 100),
            "offset": offset,
            "format": "json",
        }
        data = await self._get(f"{self.BASE_URL}/uniprotkb/search", params=params)
        results_raw = data.get("results", [])
        page_info = data.get("pageInfo", {})
        results = [self._parse_entry(r) for r in results_raw]
        return UniProtSearchResult(
            results=results,
            total_count=page_info.get("totalRecords", 0),
            page=page_info.get("offset", offset) // max(page_info.get("size", size), 1),
            page_size=len(results_raw),
        )

    async def get(self, accession: str) -> UniProtResult:
        data = await self._get(f"{self.BASE_URL}/uniprotkb/{accession}")
        return self._parse_entry(data)

    # --- 4.15.3: Response parsing ---

    def _parse_entry(self, data: dict[str, Any]) -> UniProtResult:
        entry_type = data.get("entryType", "")
        is_reviewed = "Swiss-Prot" in entry_type

        protein_names = self._extract_protein_names(data.get("proteinDescription") or {})
        gene_names = self._extract_gene_names(data.get("genes") or [])
        organism_data = data.get("organism") or {}
        organism = organism_data.get("scientificName", "")
        organism_taxon_id = organism_data.get("taxonId")

        comments_data = data.get("comments") or []
        function, subcellular, ptms, parsed_comments = self._extract_comments(comments_data)

        features = self._parse_features(data.get("features") or [])
        sequence_data = data.get("sequence") or {}
        sequence = sequence_data.get("value", "")
        sequence_length = sequence_data.get("length", 0)
        mol_weight = sequence_data.get("molWeight")

        keywords = [k.get("name", "") for k in (data.get("keywords") or []) if k.get("name")]
        cross_references = self._extract_cross_references(
            data.get("uniProtKBCrossReferences") or [],
        )

        audit_data = data.get("entryAudit") or {}
        entry_version = audit_data.get("entryVersion", 0)
        sequence_version = audit_data.get("sequenceVersion", 0)
        first_public_date = audit_data.get("firstPublicDate", "")
        last_annotation_update = audit_data.get("lastAnnotationUpdateDate", "")
        last_sequence_update = audit_data.get("lastSequenceUpdateDate", "")

        evidence_label = self._extract_evidence_label(entry_type)

        return UniProtResult(
            primary_accession=data.get("primaryAccession", ""),
            entry_name=data.get("uniProtkbId", ""),
            entry_type=entry_type,
            is_reviewed=is_reviewed,
            protein_names=protein_names,
            gene_names=gene_names,
            organism=organism,
            organism_taxon_id=organism_taxon_id,
            protein_existence=data.get("proteinExistence", ""),
            function=function,
            subcellular_location=subcellular,
            ptms=ptms,
            sequence=sequence,
            sequence_length=sequence_length,
            molecular_weight=mol_weight,
            features=features,
            comments=parsed_comments,
            cross_references=cross_references,
            keywords=keywords,
            evidence_label=evidence_label,
            entry_version=entry_version,
            sequence_version=sequence_version,
            first_public_date=first_public_date,
            last_annotation_update=last_annotation_update,
            last_sequence_update=last_sequence_update,
            extra={
                "annotation_score": data.get("annotationScore"),
                "secondary_accessions": data.get("secondaryAccessions", []),
                "protein_existence": data.get("proteinExistence", ""),
            },
        )

    @staticmethod
    def _extract_protein_names(pd: dict[str, Any]) -> list[str]:
        names: list[str] = []
        rec = pd.get("recommendedName", {})
        full = rec.get("fullName", {}).get("value", "")
        if full:
            names.append(full)
        for alt in pd.get("alternativeNames", []):
            alt_name = alt.get("fullName", {}).get("value", "")
            if alt_name:
                names.append(alt_name)
        for sub in pd.get("submissionNames", []):
            sub_name = sub.get("fullName", {}).get("value", "")
            if sub_name:
                names.append(sub_name)
        return names

    @staticmethod
    def _extract_gene_names(genes: list[dict[str, Any]]) -> list[str]:
        names: list[str] = []
        for g in genes:
            gene_name = g.get("geneName", {}).get("value", "")
            if gene_name:
                names.append(gene_name)
            for syn in g.get("synonyms", []):
                syn_name = syn.get("value", "")
                if syn_name:
                    names.append(syn_name)
        return names

    @staticmethod
    def _extract_comments(
        comments: list[dict[str, Any]],
    ) -> tuple[str, list[str], list[str], list[UniProtComment]]:
        function = ""
        subcellular: list[str] = []
        ptms: list[str] = []
        parsed: list[UniProtComment] = []

        for c in comments:
            ctype = c.get("commentType", "")
            texts = [t.get("value", "") for t in c.get("texts", []) if t.get("value")]
            ev_codes: list[str] = []
            for t in c.get("texts", []):
                for ev in t.get("evidences", []):
                    eco = ev.get("evidenceCode", "")
                    if eco:
                        ev_codes.append(eco)

            if texts:
                parsed.append(
                    UniProtComment(
                        comment_type=ctype,
                        texts=texts,
                        evidence_codes=ev_codes,
                    )
                )

            if ctype == "FUNCTION":
                function = texts[0] if texts else ""
            elif ctype == "SUBCELLULAR LOCATION":
                subcellular.extend(texts)
            elif ctype == "PTM":
                ptms.extend(texts)

        return function, subcellular, ptms, parsed

    @staticmethod
    def _parse_features(features: list[dict[str, Any]]) -> list[UniProtFeature]:
        result: list[UniProtFeature] = []
        for f in features:
            ev_codes: list[str] = []
            for ev in f.get("evidences", []):
                eco = ev.get("evidenceCode", "")
                if eco:
                    ev_codes.append(eco)

            location = f.get("location", {})
            start = None
            end = None
            start_data = location.get("start", {})
            end_data = location.get("end", {})
            if start_data and "value" in start_data:
                start = start_data["value"]
            if end_data and "value" in end_data:
                end = end_data["value"]

            result.append(
                UniProtFeature(
                    type=f.get("type", ""),
                    description=f.get("description", ""),
                    feature_id=f.get("featureId", ""),
                    start=start,
                    end=end,
                    evidence_codes=ev_codes,
                )
            )
        return result

    # --- 4.15.4: Evidence code extraction ---

    @staticmethod
    def _extract_evidence_label(entry_type: str) -> EvidenceTypeLabel:
        if "Swiss-Prot" in entry_type:
            return EvidenceTypeLabel.EXPERIMENTAL
        return EvidenceTypeLabel.PREDICTED

    @staticmethod
    def _extract_evidence_codes(evidences: list[dict[str, Any]]) -> list[str]:
        return [ev.get("evidenceCode", "") for ev in evidences if ev.get("evidenceCode")]

    # --- 4.15.5: Version tracking ---

    @staticmethod
    def _extract_entry_audit(audit: dict[str, Any]) -> dict[str, Any]:
        return {
            "entry_version": audit.get("entryVersion", 0),
            "sequence_version": audit.get("sequenceVersion", 0),
            "first_public_date": audit.get("firstPublicDate", ""),
            "last_annotation_update": audit.get("lastAnnotationUpdateDate", ""),
            "last_sequence_update": audit.get("lastSequenceUpdateDate", ""),
        }

    # --- 4.15.6: Cross-reference extraction ---

    @staticmethod
    def _extract_cross_references(
        xrefs: list[dict[str, Any]],
    ) -> list[CrossReference]:
        result: list[CrossReference] = []
        for x in xrefs:
            db = x.get("database", "")
            identifier = x.get("id", "")
            if not db or not identifier:
                continue
            if db not in _TARGET_XREF_DBS:
                continue
            properties: dict[str, str] = {}
            for prop in x.get("properties", []):
                key = prop.get("key", "")
                value = prop.get("value", "")
                if key and value:
                    properties[key] = value
            result.append(
                CrossReference(
                    database=db,
                    identifier=identifier,
                    properties=properties,
                )
            )
        return result

    async def close(self) -> None:
        await self._client.aclose()

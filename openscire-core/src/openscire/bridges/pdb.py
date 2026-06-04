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

_TARGET_ANNOTATION_TYPES = frozenset({
    "InterPro", "SCOP", "CATH", "GO",
})

_GRAPHQL_ENTRY_QUERY = """
query($id: String!) {
  entry(entry_id: $id) {
    rcsb_id
    struct { title }
    exptl { method }
    rcsb_entry_info {
      resolution_combined
      experimental_method
      structure_determination_methodology
      molecular_weight
    }
    rcsb_accession_info {
      initial_release_date
    }
    rcsb_primary_citation {
      title
      journal_abbrev
      year
      pdbx_database_id_PubMed
      pdbx_database_id_DOI
      rcsb_authors
    }
    refine {
      ls_d_res_high
      ls_R_factor_R_free
      ls_R_factor_R_work
    }
    audit_author { name }
    polymer_entities {
      rcsb_id
      entity_poly {
        rcsb_entity_polymer_type
        pdbx_seq_one_letter_code_can
      }
      rcsb_polymer_entity_container_identifiers {
        asym_ids
      }
      uniprots {
        rcsb_uniprot_accession
      }
      pfams {
        rcsb_pfam_accession
      }
      rcsb_polymer_entity_annotation {
        type
        name
        provenance_source
      }
    }
    database_2 {
      database_id
      database_code
    }
    rcsb_entry_container_identifiers {
      entry_id
      emdb_ids
    }
  }
}
"""


class PdbAuthor(BaseModel):
    name: str = ""


class PdbCitation(BaseModel):
    title: str = ""
    journal: str = ""
    year: int | None = None
    doi: str = ""
    pubmed_id: int | None = None
    authors: list[str] = Field(default_factory=list)


class PdbCrossReference(BaseModel):
    database: str = ""
    identifier: str = ""
    properties: dict[str, str] = Field(default_factory=dict)


class PdbPolymerEntity(BaseModel):
    entity_id: str = ""
    polymer_type: str = ""
    sequence: str = ""
    chain_ids: list[str] = Field(default_factory=list)
    uniprot_accessions: list[str] = Field(default_factory=list)
    pfam_accessions: list[str] = Field(default_factory=list)


class PdbStructureResult(BaseModel):
    pdb_id: str = ""
    title: str = ""
    experimental_method: str = ""
    experimental_method_category: str = ""
    structure_determination_methodology: str = ""
    resolution: float | None = None
    r_free: float | None = None
    r_work: float | None = None
    release_date: str = ""
    molecular_weight: float | None = None
    authors: list[PdbAuthor] = Field(default_factory=list)
    citation: PdbCitation | None = None
    polymer_entities: list[PdbPolymerEntity] = Field(default_factory=list)
    cross_references: list[PdbCrossReference] = Field(default_factory=list)
    evidence_label: EvidenceTypeLabel = EvidenceTypeLabel.EXPERIMENTAL
    extra: dict[str, Any] = Field(default_factory=dict)


class PdbSearchResult(BaseModel):
    pdb_ids: list[str] = Field(default_factory=list)
    total_count: int = 0
    start: int = 0
    rows: int = 25


class PdbQueryBuilder:
    def __init__(self) -> None:
        self._nodes: list[dict[str, Any]] = []

    def _add_terminal(
        self,
        attribute: str,
        operator: str,
        value: Any,  # noqa: ANN401
        service: str = "text",
    ) -> PdbQueryBuilder:
        self._nodes.append({
            "type": "terminal",
            "service": service,
            "parameters": {
                "attribute": attribute,
                "operator": operator,
                "value": value,
            },
        })
        return self

    def resolution(
        self,
        max_res: float,
        min_res: float = 0.0,
    ) -> PdbQueryBuilder:
        if min_res > 0:
            return self._add_range(
                "rcsb_entry_info.resolution_combined",
                min_res,
                max_res,
            )
        return self._add_terminal(
            "rcsb_entry_info.resolution_combined",
            "less_or_equal",
            max_res,
        )

    def _add_range(
        self,
        attribute: str,
        min_val: float,
        max_val: float,
    ) -> PdbQueryBuilder:
        self._nodes.append({
            "type": "group",
            "logical_operator": "and",
            "nodes": [
                {
                    "type": "terminal",
                    "service": "text",
                    "parameters": {
                        "attribute": attribute,
                        "operator": "greater_or_equal",
                        "value": min_val,
                    },
                },
                {
                    "type": "terminal",
                    "service": "text",
                    "parameters": {
                        "attribute": attribute,
                        "operator": "less_or_equal",
                        "value": max_val,
                    },
                },
            ],
        })
        return self

    def ligand(self, ligand_id: str) -> PdbQueryBuilder:
        return self._add_terminal(
            "rcsb_chem_comp_annotation.comp_id",
            "exact_match",
            ligand_id.upper(),
        )

    def author(self, name: str) -> PdbQueryBuilder:
        return self._add_terminal(
            "rcsb_entry_info.author_last_name",
            "exact_match",
            name,
        )

    def sequence(
        self,
        seq: str,
        identity: float = 0.9,
    ) -> PdbQueryBuilder:
        self._nodes.append({
            "type": "terminal",
            "service": "sequence",
            "parameters": {
                "value": seq,
                "sequence_type": "protein",
                "identity_cutoff": identity,
            },
        })
        return self

    def structure_id(self, pdb_id: str) -> PdbQueryBuilder:
        return self._add_terminal(
            "rcsb_entry_info.entry_id",
            "exact_match",
            pdb_id.upper(),
        )

    def experimental_method(self, method: str) -> PdbQueryBuilder:
        return self._add_terminal(
            "rcsb_entry_info.experimental_method",
            "exact_match",
            method,
        )

    def build(self) -> dict[str, Any]:
        if not self._nodes:
            return {}

        query: dict[str, Any]
        if len(self._nodes) == 1:
            query = self._nodes[0]
        else:
            query = {
                "type": "group",
                "logical_operator": "and",
                "nodes": self._nodes,
            }

        return {
            "query": query,
            "return_type": "entry",
            "request_options": {
                "paginate": {"start": 0, "rows": 25},
                "scoring_strategy": "text",
            },
        }


class PdbClient:
    BASE_URL = "https://data.rcsb.org"
    SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"

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

    async def _post(
        self,
        url: str,
        json_data: dict[str, Any],
    ) -> Any:  # noqa: ANN401
        await self._rate_limiter.acquire()
        try:
            response = await self._client.post(url, json=json_data)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise ReferenceError(
                f"PDB API error: {e.response.status_code} {e.response.text[:200]}",
                source="pdb",
            ) from e
        except httpx.RequestError as e:
            raise ReferenceError(
                f"PDB request failed: {e}",
                source="pdb",
            ) from e

    # --- 4.16.1: REST API endpoints ---

    async def get(self, pdb_id: str) -> PdbStructureResult:
        variables = {"id": pdb_id.strip().upper()}
        payload = {
            "query": _GRAPHQL_ENTRY_QUERY,
            "variables": variables,
        }
        data = await self._post(f"{self.BASE_URL}/graphql", payload)
        entry_data = data.get("data", {}).get("entry")
        if entry_data is None:
            errors = data.get("errors", [])
            detail = errors[0].get("message", "") if errors else "entry not found"
            raise ReferenceError(
                f"PDB API error: {detail}",
                source="pdb",
            )
        return self._parse_structure(entry_data)

    async def search(
        self,
        query: dict[str, Any] | PdbQueryBuilder,
    ) -> PdbSearchResult:
        if isinstance(query, PdbQueryBuilder):
            query = query.build()
        data = await self._post(self.SEARCH_URL, query)
        result_set = data.get("result_set", [])
        pdb_ids = [r.get("identifier", "") for r in result_set if r.get("identifier")]
        return PdbSearchResult(
            pdb_ids=pdb_ids,
            total_count=data.get("total_count", 0),
            start=query.get("request_options", {}).get("paginate", {}).get("start", 0),
            rows=len(pdb_ids),
        )

    async def search_by_resolution(
        self,
        max_res: float,
        min_res: float = 0.0,
    ) -> PdbSearchResult:
        qb = PdbQueryBuilder().resolution(max_res, min_res)
        return await self.search(qb)

    async def search_by_ligand(self, ligand_id: str) -> PdbSearchResult:
        qb = PdbQueryBuilder().ligand(ligand_id)
        return await self.search(qb)

    async def search_by_author(self, name: str) -> PdbSearchResult:
        qb = PdbQueryBuilder().author(name)
        return await self.search(qb)

    async def search_by_sequence(
        self,
        seq: str,
        identity: float = 0.9,
    ) -> PdbSearchResult:
        qb = PdbQueryBuilder().sequence(seq, identity)
        return await self.search(qb)

    # --- 4.16.2: Structure metadata parsing ---

    def _parse_structure(self, data: dict[str, Any]) -> PdbStructureResult:
        pdb_id = data.get("rcsb_id", "")

        struct_data = data.get("struct", {}) or {}
        title = (struct_data.get("title") or "").strip()

        exptl_list = data.get("exptl") or []
        raw_method = exptl_list[0].get("method", "") if exptl_list else ""

        entry_info = data.get("rcsb_entry_info", {}) or {}
        method_category = entry_info.get("experimental_method", "")
        methodology = entry_info.get("structure_determination_methodology", "")
        resolution_raw = (entry_info.get("resolution_combined") or [None])[0]
        mol_weight = entry_info.get("molecular_weight")

        accession_info = data.get("rcsb_accession_info", {}) or {}
        release_date = accession_info.get("initial_release_date", "")

        refine_list = data.get("refine") or []
        r_free = None
        r_work = None
        if refine_list:
            r_free = refine_list[0].get("ls_R_factor_R_free")
            r_work = refine_list[0].get("ls_R_factor_R_work")

        authors = self._parse_authors(data.get("audit_author") or [])
        citation = self._parse_citation(data.get("rcsb_primary_citation"))
        polymer_entities = self._parse_polymer_entities(
            data.get("polymer_entities") or [],
        )
        cross_references = self._extract_cross_references(
            data,
            polymer_entities,
        )
        evidence_label = self._extract_evidence_label(methodology, raw_method)

        extra: dict[str, Any] = {}
        identifiers = data.get("rcsb_entry_container_identifiers", {}) or {}
        emdb_ids = identifiers.get("emdb_ids")
        if emdb_ids:
            extra["emdb_ids"] = emdb_ids

        return PdbStructureResult(
            pdb_id=pdb_id,
            title=title,
            experimental_method=raw_method,
            experimental_method_category=method_category,
            structure_determination_methodology=methodology,
            resolution=resolution_raw,
            r_free=r_free,
            r_work=r_work,
            release_date=release_date,
            molecular_weight=mol_weight,
            authors=authors,
            citation=citation,
            polymer_entities=polymer_entities,
            cross_references=cross_references,
            evidence_label=evidence_label,
            extra=extra,
        )

    @staticmethod
    def _parse_authors(
        audit_author: list[dict[str, Any]],
    ) -> list[PdbAuthor]:
        return [
            PdbAuthor(name=a.get("name", ""))
            for a in audit_author
            if a.get("name")
        ]

    @staticmethod
    def _parse_citation(
        citation_data: dict[str, Any] | None,
    ) -> PdbCitation | None:
        if not citation_data:
            return None
        title = (citation_data.get("title") or "").strip()
        journal = (citation_data.get("journal_abbrev") or "").strip()
        year = citation_data.get("year")
        doi = citation_data.get("pdbx_database_id_DOI", "")
        pubmed_raw = citation_data.get("pdbx_database_id_PubMed")
        pubmed_id = int(pubmed_raw) if pubmed_raw else None
        authors = citation_data.get("rcsb_authors") or []

        if not title and not journal and not doi:
            return None

        return PdbCitation(
            title=title,
            journal=journal,
            year=year,
            doi=doi,
            pubmed_id=pubmed_id,
            authors=list(authors),
        )

    @staticmethod
    def _parse_polymer_entities(
        entities: list[dict[str, Any]],
    ) -> list[PdbPolymerEntity]:
        result: list[PdbPolymerEntity] = []
        for ent in entities:
            entity_id = ent.get("rcsb_id", "")
            poly = ent.get("entity_poly", {}) or {}
            polymer_type = poly.get("rcsb_entity_polymer_type", "")
            sequence = poly.get("pdbx_seq_one_letter_code_can", "")
            container = (
                ent.get("rcsb_polymer_entity_container_identifiers", {}) or {}
            )
            chain_ids = container.get("asym_ids", [])

            uniprots_raw = ent.get("uniprots") or []
            uniprot_accessions: list[str] = []
            for u in uniprots_raw:
                accs = u.get("rcsb_uniprot_accession") or []
                if accs:
                    uniprot_accessions.append(str(accs[0]))

            pfams_raw = ent.get("pfams") or []
            pfam_accessions = [
                p.get("rcsb_pfam_accession", "")
                for p in pfams_raw
                if p.get("rcsb_pfam_accession")
            ]

            result.append(PdbPolymerEntity(
                entity_id=entity_id,
                polymer_type=polymer_type,
                sequence=sequence,
                chain_ids=list(chain_ids),
                uniprot_accessions=uniprot_accessions,
                pfam_accessions=pfam_accessions,
            ))
        return result

    # --- 4.16.3: Experimental vs predicted classification ---

    @staticmethod
    def _extract_evidence_label(
        methodology: str,
        raw_method: str,  # noqa: ARG004
    ) -> EvidenceTypeLabel:
        if methodology == "computational":
            return EvidenceTypeLabel.PREDICTED
        if methodology == "integrative":
            return EvidenceTypeLabel.REVIEWED
        return EvidenceTypeLabel.EXPERIMENTAL

    # --- 4.16.4: Resolution/quality filtering ---

    @staticmethod
    def filter_by_resolution(
        results: list[PdbStructureResult],
        max_res: float,
    ) -> list[PdbStructureResult]:
        return [
            r for r in results
            if r.resolution is not None and r.resolution <= max_res
        ]

    @staticmethod
    def check_quality(
        result: PdbStructureResult,
        max_r_free: float = 0.4,
        max_r_work: float = 0.3,
    ) -> bool:
        if not result.experimental_method:
            return False
        r_free_ok = (
            result.r_free is None or result.r_free <= max_r_free
        )
        r_work_ok = (
            result.r_work is None or result.r_work <= max_r_work
        )
        return r_free_ok and r_work_ok

    # --- 4.16.5: Cross-reference extraction ---

    def _extract_cross_references(
        self,
        data: dict[str, Any],
        polymer_entities: list[PdbPolymerEntity],
    ) -> list[PdbCrossReference]:
        xrefs: list[PdbCrossReference] = []

        for entity in polymer_entities:
            for acc in entity.uniprot_accessions:
                xrefs.append(PdbCrossReference(
                    database="UniProt",
                    identifier=acc,
                ))
            for pfam in entity.pfam_accessions:
                xrefs.append(PdbCrossReference(
                    database="Pfam",
                    identifier=pfam,
                ))

        annotations: list[dict[str, Any]] = []
        for ent in data.get("polymer_entities", []):
            anns = ent.get("rcsb_polymer_entity_annotation") or []
            annotations.extend(anns)

        seen_annotation: set[tuple[str, str]] = set()
        for ann in annotations:
            atype = ann.get("type", "")
            aname = ann.get("name", "")
            if atype in _TARGET_ANNOTATION_TYPES and aname:
                key = (atype, aname)
                if key not in seen_annotation:
                    seen_annotation.add(key)
                    xrefs.append(PdbCrossReference(
                        database=atype,
                        identifier=aname,
                        properties={"provenance": ann.get("provenance_source", "")},
                    ))

        citation = self._parse_citation(data.get("rcsb_primary_citation"))
        if citation and citation.pubmed_id:
            xrefs.append(PdbCrossReference(
                database="PubMed",
                identifier=str(citation.pubmed_id),
            ))

        identifiers = data.get("rcsb_entry_container_identifiers", {}) or {}
        for emdb in identifiers.get("emdb_ids") or []:
            xrefs.append(PdbCrossReference(
                database="EMDB",
                identifier=emdb,
            ))

        return xrefs

    async def close(self) -> None:
        await self._client.aclose()

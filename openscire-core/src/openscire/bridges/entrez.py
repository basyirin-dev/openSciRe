# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import contextlib
import json
import logging
import xml.etree.ElementTree as ET
from typing import Any

import httpx
from pydantic import BaseModel, Field

from openscire.bridge.rate_limiter import TokenBucketRateLimiter
from openscire.exceptions import ReferenceError

logger = logging.getLogger(__name__)


class EntrezSearchResult(BaseModel):
    ids: list[str] = Field(default_factory=list)
    total_count: int = 0
    retstart: int = 0
    webenv: str = ""
    query_key: str = ""
    db: str = ""


class EntrezSummary(BaseModel):
    id: str = ""
    db: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class NucleotideRecord(BaseModel):
    accession: str = ""
    accession_version: str = ""
    length: int = 0
    definition: str = ""
    molecule_type: str = ""
    topology: str = ""
    strandedness: str = ""
    organism: str = ""
    taxon_id: int | None = None
    gene_name: str = ""
    sequence: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class AssemblyRecord(BaseModel):
    assembly_accession: str = ""
    assembly_name: str = ""
    organism: str = ""
    taxon_id: int | None = None
    assembly_level: str = ""
    assembly_type: str = ""
    genome_representation: str = ""
    release_date: str = ""
    submitter: str = ""
    total_sequence_length: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class TaxonomyRecord(BaseModel):
    taxon_id: int = 0
    scientific_name: str = ""
    common_name: str = ""
    genbank_common_name: str = ""
    lineage: str = ""
    genetic_code: int | None = None
    mito_genetic_code: int | None = None
    rank: str = ""
    division: str = ""
    parent_taxon_id: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class EntrezLink(BaseModel):
    db_to: str = ""
    ids: list[str] = Field(default_factory=list)
    link_name: str = ""


class EntrezLinkSet(BaseModel):
    db_from: str = ""
    id: str = ""
    links: list[EntrezLink] = Field(default_factory=list)


class EntrezClient:
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(
        self,
        email: str = "",
        api_key: str = "",
        tool: str = "openscire",
        timeout: int = 30,
    ) -> None:
        rate = 10.0 if api_key else 3.0
        self._rate_limiter = TokenBucketRateLimiter(rate=rate, burst=2)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )
        self._default_params: dict[str, str] = {
            "tool": tool,
            "email": email,
        }
        if api_key:
            self._default_params["api_key"] = api_key

    # --- Internal HTTP methods ---

    async def _request(self, endpoint: str, params: dict[str, Any]) -> str:
        url = f"{self.BASE_URL}/{endpoint}"
        all_params: dict[str, str] = {
            **self._default_params,
            **{k: str(v) for k, v in params.items()},
        }
        await self._rate_limiter.acquire()
        try:
            response = await self._client.get(url, params=all_params)
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            raise ReferenceError(
                f"Entrez API error: {e.response.status_code} {e.response.text[:200]}",
                source="entrez",
            ) from e
        except httpx.RequestError as e:
            raise ReferenceError(
                f"Entrez request failed: {e}",
                source="entrez",
            ) from e

    async def _request_json(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        text = await self._request(endpoint, params)
        return json.loads(text)

    # --- 4.17.1: Core E-utilities ---

    async def esearch(
        self,
        db: str,
        term: str,
        retmax: int = 20,
        retstart: int = 0,
        usehistory: bool = False,
    ) -> EntrezSearchResult:
        params: dict[str, Any] = {
            "db": db,
            "term": term,
            "retmax": str(retmax),
            "retstart": str(retstart),
            "retmode": "json",
        }
        if usehistory:
            params["usehistory"] = "y"

        data = await self._request_json("esearch.fcgi", params)
        esearchresult = data.get("esearchresult", {})

        return EntrezSearchResult(
            ids=esearchresult.get("idlist", []),
            total_count=int(esearchresult.get("count", 0)),
            retstart=int(esearchresult.get("retstart", 0)),
            webenv=esearchresult.get("webenv", ""),
            query_key=esearchresult.get("querykey", ""),
            db=db,
        )

    async def esummary(
        self,
        db: str,
        ids: list[str],
    ) -> list[EntrezSummary]:
        params: dict[str, Any] = {
            "db": db,
            "id": ",".join(ids),
            "retmode": "json",
        }
        data = await self._request_json("esummary.fcgi", params)
        result = data.get("result", {})
        uid_list = result.get("uids", [])

        summaries: list[EntrezSummary] = []
        for uid in uid_list:
            entry = result.get(str(uid), {})
            summaries.append(EntrezSummary(
                id=str(uid),
                db=db,
                data=entry,
            ))
        return summaries

    async def efetch(
        self,
        db: str,
        ids: list[str],
        rettype: str = "xml",
        retmode: str = "xml",
    ) -> str:
        params: dict[str, Any] = {
            "db": db,
            "id": ",".join(ids),
            "rettype": rettype,
            "retmode": retmode,
        }
        return await self._request("efetch.fcgi", params)

    async def elink(
        self,
        dbfrom: str,
        db: str | None = None,
        ids: list[str] | None = None,
    ) -> list[EntrezLinkSet]:
        if not ids:
            return []
        params: dict[str, Any] = {
            "dbfrom": dbfrom,
            "id": ",".join(ids),
            "retmode": "json",
        }
        if db:
            params["db"] = db

        data = await self._request_json("elink.fcgi", params)
        linksets_data = data.get("linksets", [])

        results: list[EntrezLinkSet] = []
        for ls in linksets_data:
            link_set = EntrezLinkSet(
                db_from=ls.get("dbfrom", dbfrom),
                id=str(ls.get("ids", [""])[0]) if ls.get("ids") else "",
            )
            for link_db in ls.get("linksetdbs", []):
                link_set.links.append(EntrezLink(
                    db_to=link_db.get("dbto", ""),
                    link_name=link_db.get("linkname", ""),
                    ids=[str(lid) for lid in link_db.get("links", [])],
                ))
            results.append(link_set)
        return results

    # --- 4.17.2: Nucleotide search ---

    async def search_nucleotide(
        self,
        query: str,
        retmax: int = 20,
    ) -> EntrezSearchResult:
        return await self.esearch("nucleotide", query, retmax=retmax)

    async def fetch_nucleotide(self, accession: str) -> NucleotideRecord:
        xml_str = await self.efetch(
            "nucleotide",
            [accession],
            rettype="gb",
            retmode="xml",
        )
        return self._parse_genbank_xml(xml_str)

    async def fetch_nucleotide_sequence(self, accession: str) -> str:
        return await self.efetch(
            "nucleotide",
            [accession],
            rettype="fasta",
            retmode="text",
        )

    # --- 4.17.3: Genome assembly search ---

    async def search_assembly(
        self,
        query: str,
        retmax: int = 20,
    ) -> EntrezSearchResult:
        return await self.esearch("assembly", query, retmax=retmax)

    async def fetch_assembly(self, accession: str) -> AssemblyRecord:
        xml_str = await self.efetch(
            "assembly",
            [accession],
            rettype="xml",
            retmode="xml",
        )
        records = self._parse_assembly_set(xml_str)
        if not records:
            msg = f"No assembly found for: {accession}"
            raise ReferenceError(msg, source="entrez")
        return records[0]

    # --- 4.17.4: Taxonomy search ---

    async def search_taxonomy(
        self,
        query: str,
        retmax: int = 20,
    ) -> EntrezSearchResult:
        return await self.esearch("taxonomy", query, retmax=retmax)

    async def fetch_taxonomy(self, taxon_id: int) -> TaxonomyRecord:
        xml_str = await self.efetch(
            "taxonomy",
            [str(taxon_id)],
            rettype="xml",
            retmode="xml",
        )
        records = self._parse_taxon_set(xml_str)
        if not records:
            msg = f"No taxonomy found for: {taxon_id}"
            raise ReferenceError(msg, source="entrez")
        return records[0]

    async def fetch_taxonomy_by_name(self, name: str) -> TaxonomyRecord | None:
        result = await self.search_taxonomy(name, retmax=1)
        if not result.ids:
            return None
        try:
            taxon_id = int(result.ids[0])
            return await self.fetch_taxonomy(taxon_id)
        except (ValueError, IndexError):
            return None

    # --- 4.17.5: Literature cross-reference ---

    async def fetch_linked_records(
        self,
        pubmed_id: str,
        db_to: str | None = None,
    ) -> EntrezLinkSet:
        link_sets = await self.elink("pubmed", db=db_to, ids=[pubmed_id])
        if link_sets:
            return link_sets[0]
        return EntrezLinkSet(db_from="pubmed", id=pubmed_id)

    # --- XML parsing ---

    @staticmethod
    def _parse_genbank_xml(xml_str: str) -> NucleotideRecord:
        root = ET.fromstring(xml_str)
        gbseq = root.find("GBSeq")
        if gbseq is None:
            msg = "No GBSeq element found in GenBank XML"
            raise ReferenceError(msg, source="entrez")

        def _text(tag: str) -> str:
            el = gbseq.find(tag)
            return el.text or "" if el is not None else ""

        gene_name = ""
        feature_table = gbseq.find("GBSeq_feature-table")
        if feature_table is not None:
            for feature in feature_table.findall("GBFeature"):
                key_el = feature.find("GBFeature_key")
                if key_el is not None and key_el.text == "gene":
                    quals = feature.find("GBFeature_quals")
                    if quals is not None:
                        for qual in quals.findall("GBQualifier"):
                            qname = qual.find("GBQualifier_name")
                            qval = qual.find("GBQualifier_value")
                            if qname is not None and qval is not None and qname.text == "gene":
                                gene_name = qval.text or ""

        accession_version = _text("GBSeq_accession-version")
        primary_accession = _text("GBSeq_primary-accession")
        if not accession_version:
            accession_version = primary_accession

        seq_value = _text("GBSeq_sequence")

        return NucleotideRecord(
            accession=primary_accession or _text("GBSeq_locus"),
            accession_version=accession_version,
            length=int(_text("GBSeq_length")) if _text("GBSeq_length") else 0,
            definition=_text("GBSeq_definition"),
            molecule_type=_text("GBSeq_moltype"),
            topology=_text("GBSeq_topology"),
            strandedness=_text("GBSeq_strandedness"),
            organism=_text("GBSeq_organism"),
            gene_name=gene_name,
            sequence=seq_value,
            extra={
                "taxonomy": _text("GBSeq_taxonomy"),
                "comment": _text("GBSeq_comment"),
            },
        )

    @staticmethod
    def _parse_assembly_set(xml_str: str) -> list[AssemblyRecord]:
        root = ET.fromstring(xml_str)
        records: list[AssemblyRecord] = []

        for assembly in root.findall("Assembly"):
            org = assembly.find("Organism")
            organism = ""
            taxon_id: int | None = None
            if org is not None:
                org_sci = org.find("Organism_scientific")
                if org_sci is not None:
                    organism = org_sci.text or ""
                org_tax = org.find("Organism_taxid")
                if org_tax is not None and org_tax.text:
                    taxon_id = int(org_tax.text)

            submitter_el = assembly.find("Submitter")
            submitter = ""
            if submitter_el is not None:
                sf = submitter_el.find("Submitter_full")
                if sf is not None:
                    submitter = sf.text or ""

            total_length: int | None = None
            for stat in assembly.findall("Stat"):
                cat = stat.find("Stat_category")
                val = stat.find("Stat_value")
                if cat is not None and val is not None and cat.text == "total_length":
                    with contextlib.suppress(ValueError, TypeError):
                        total_length = int(val.text or "0")

            date_el = assembly.find("Date")

            records.append(AssemblyRecord(
                assembly_accession=_safe_text(assembly, "Assembly_accession"),
                assembly_name=_safe_text(assembly, "Assembly_name"),
                organism=organism,
                taxon_id=taxon_id,
                assembly_level=_safe_text(assembly, "Assembly_level"),
                assembly_type=_safe_text(assembly, "Assembly_type"),
                genome_representation=_safe_text(assembly, "Genome_representation"),
                release_date=date_el.text or "" if date_el is not None else "",
                submitter=submitter,
                total_sequence_length=total_length,
            ))
        return records

    @staticmethod
    def _parse_taxon_set(xml_str: str) -> list[TaxonomyRecord]:
        root = ET.fromstring(xml_str)
        records: list[TaxonomyRecord] = []

        for taxon in root.findall("Taxon"):
            gc_id: int | None = None
            gc = taxon.find("GeneticCode")
            if gc is not None:
                gcid = gc.find("GCId")
                if gcid is not None and gcid.text:
                    with contextlib.suppress(ValueError, TypeError):
                        gc_id = int(gcid.text)

            mito_gc_id: int | None = None
            mgc = taxon.find("MitoGeneticCode")
            if mgc is not None:
                mgcid = mgc.find("MGCId")
                if mgcid is not None and mgcid.text:
                    with contextlib.suppress(ValueError, TypeError):
                        mito_gc_id = int(mgcid.text)

            tax_id_str = _safe_text(taxon, "TaxId")
            tax_id = int(tax_id_str) if tax_id_str else 0

            records.append(TaxonomyRecord(
                taxon_id=tax_id,
                scientific_name=_safe_text(taxon, "ScientificName"),
                common_name=_safe_text(taxon, "CommonName"),
                genbank_common_name=_safe_text(taxon, "GenbankCommonName"),
                lineage=_safe_text(taxon, "Lineage"),
                genetic_code=gc_id,
                mito_genetic_code=mito_gc_id,
                rank=_safe_text(taxon, "Rank"),
                division=_safe_text(taxon, "Division"),
                parent_taxon_id=(
                    int(_safe_text(taxon, "ParentTaxId"))
                    if _safe_text(taxon, "ParentTaxId")
                    else None
                ),
            ))
        return records

    async def close(self) -> None:
        await self._client.aclose()


def _safe_text(parent: ET.Element, tag: str) -> str:
    el = parent.find(tag)
    return el.text or "" if el is not None else ""

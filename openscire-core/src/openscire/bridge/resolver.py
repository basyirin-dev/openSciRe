# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging

import httpx

from openscire.bridge.rate_limiter import TokenBucketRateLimiter

logger = logging.getLogger(__name__)


class CrossReferenceResolver:
    def __init__(
        self,
        rate_limiter: TokenBucketRateLimiter | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._rate_limiter = rate_limiter or TokenBucketRateLimiter(rate=2.0, burst=1)
        self._client = client or httpx.AsyncClient()

    async def doi_to_pmid(self, doi: str) -> str | None:
        return await self._idconv(doi, target_db="pubmed")

    async def pmid_to_pmcid(self, pmid: str) -> str | None:
        return await self._idconv(pmid, target_db="pmc")

    async def doi_to_pmcid(self, doi: str) -> str | None:
        return await self._idconv(doi, target_db="pmc")

    async def _idconv(self, identifier: str, target_db: str) -> str | None:
        await self._rate_limiter.acquire()
        url = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
        params: dict[str, str] = {
            "ids": identifier,
            "format": "json",
        }
        try:
            resp = await self._client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            records = data.get("records", [])
            for record in records:
                key = "pmcid" if target_db == "pmc" else "pmid"
                value = record.get(key)
                if value:
                    return str(value)
            return None
        except Exception as exc:
            logger.warning("idconv failed for %s -> %s: %s", identifier, target_db, exc)
            return None

    async def pdb_to_uniprot(self, pdb_id: str) -> list[str]:
        await self._rate_limiter.acquire()
        url = f"https://www.ebi.ac.uk/pdbe/api/mappings/{pdb_id.strip().lower()}"
        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
            data = resp.json()
            uniprot_ids: set[str] = set()
            mappings = data.get(pdb_id.strip().lower(), {})
            for uniprot_data in mappings.get("UniProt", {}).values():
                for entry in uniprot_data:
                    identifier = entry.get("identifier") or entry.get("id")
                    if identifier:
                        uniprot_ids.add(str(identifier))
            return sorted(uniprot_ids)
        except Exception as exc:
            logger.warning("PDB->UniProt mapping failed for %s: %s", pdb_id, exc)
            return []

    async def uniprot_to_pdb(self, uniprot_id: str) -> list[str]:
        await self._rate_limiter.acquire()
        url = f"https://www.ebi.ac.uk/pdbe/api/mappings/uniprot/{uniprot_id.strip().upper()}"
        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
            data = resp.json()
            pdb_ids: set[str] = set()
            for uniprot in data.get(uniprot_id.strip().upper(), {}).values():
                pdb_ids.add(uniprot.get("pdb_id", ""))
            return sorted(p for p in pdb_ids if p)
        except Exception as exc:
            logger.warning("UniProt->PDB mapping failed for %s: %s", uniprot_id, exc)
            return []

    async def close(self) -> None:
        await self._client.aclose()

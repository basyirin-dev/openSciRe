# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import BaseModel, Field

from openscire.bridge.confidence import ConfidenceTrace, PropagationStrategy
from openscire.bridge.evidence_label import EvidenceTypeLabel
from openscire.bridge.rate_limiter import TokenBucketRateLimiter
from openscire.exceptions import ReferenceError

logger = logging.getLogger(__name__)

# pLDDT confidence categories as defined by AlphaFold
_PLDDT_VERY_HIGH = 90.0
_PLDDT_CONFIDENT = 70.0
_PLDDT_LOW = 50.0
_PLDDT_VERY_LOW = 0.0

# Default PAE domain clustering threshold in Angstroms
_PAE_DOMAIN_THRESHOLD = 5.0


class AlphaFoldPrediction(BaseModel):
    entry_id: str = ""
    uniprot_accession: str = ""
    uniprot_id: str = ""
    uniprot_description: str = ""
    gene: str = ""
    organism_scientific_name: str = ""
    organism_common_name: str = ""
    tax_id: int = 0
    is_reviewed: bool = False
    is_reference_proteome: bool = False
    sequence: str = ""
    sequence_length: int = 0
    global_metric_value: float = 0.0
    fraction_plddt_very_high: float = 0.0
    fraction_plddt_confident: float = 0.0
    fraction_plddt_low: float = 0.0
    fraction_plddt_very_low: float = 0.0
    latest_version: int = 0
    all_versions: list[int] = Field(default_factory=list)
    model_created_date: str = ""
    pdb_url: str = ""
    cif_url: str = ""
    bcif_url: str = ""
    pae_url: str = ""
    plddt_url: str = ""
    pae_image_url: str = ""
    msa_url: str = ""
    evidence_label: EvidenceTypeLabel = EvidenceTypeLabel.PREDICTED
    extra: dict[str, Any] = Field(default_factory=dict)


class ResidueConfidence(BaseModel):
    residue_number: int = 0
    plddt_score: float = 0.0
    confidence_category: str = ""
    is_disordered: bool = False


class PaeMatrix(BaseModel):
    residue_count: int = 0
    pae_values: list[list[float]] = Field(default_factory=list)
    domain_regions: list[DomainRegion] = Field(default_factory=list)


class DomainRegion(BaseModel):
    start: int = 0
    end: int = 0
    mean_pae: float = 0.0
    size: int = 0


class DisorderedRegion(BaseModel):
    start: int = 0
    end: int = 0
    length: int = 0
    mean_plddt: float = 0.0


class DisorderReport(BaseModel):
    regions: list[DisorderedRegion] = Field(default_factory=list)
    total_disordered_residues: int = 0
    fraction_disordered: float = 0.0


_KNOWN_PROTEOMES: dict[str, str] = {
    "UP000005640_9606": "HUMAN",
    "UP000000589_10090": "MOUSE",
    "UP000000803_7227": "FLY",
    "UP000002311_4932": "YEAST",
    "UP000000625_83333": "COLI",
    "UP000001940_6239": "WORM",
    "UP000000437_7955": "ZEBRAFISH",
    "UP000006548_3702": "ARATH",
    "UP000008816_1280": "STAAU",
    "UP000001584_83332": "MYCTU",
}


def _plddt_category(score: float) -> str:
    if score >= _PLDDT_VERY_HIGH:
        return "VH"
    if score >= _PLDDT_CONFIDENT:
        return "H"
    if score >= _PLDDT_LOW:
        return "L"
    return "VL"


class AlphaFoldClient:
    BASE_URL = "https://alphafold.ebi.ac.uk"

    def __init__(
        self,
        timeout: int = 30,
        rate: float = 5.0,
        burst: int = 2,
        confidence_cutoff: float = 70.0,
    ) -> None:
        self._rate_limiter = TokenBucketRateLimiter(rate=rate, burst=burst)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )
        self._confidence_cutoff = confidence_cutoff

    # --- Internal HTTP ---

    async def _get_json(self, url: str) -> Any:  # noqa: ANN401
        await self._rate_limiter.acquire()
        try:
            response = await self._client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise ReferenceError(
                f"AlphaFold API error: {e.response.status_code} {e.response.text[:200]}",
                source="alphafold",
            ) from e
        except httpx.RequestError as e:
            raise ReferenceError(
                f"AlphaFold request failed: {e}",
                source="alphafold",
            ) from e

    async def _get_bytes(self, url: str) -> bytes:
        await self._rate_limiter.acquire()
        try:
            response = await self._client.get(url)
            response.raise_for_status()
            return response.content
        except httpx.HTTPStatusError as e:
            raise ReferenceError(
                f"AlphaFold download error: {e.response.status_code} {e.response.text[:200]}",
                source="alphafold",
            ) from e
        except httpx.RequestError as e:
            raise ReferenceError(
                f"AlphaFold download failed: {e}",
                source="alphafold",
            ) from e

    # --- 4.18.1: REST API client ---

    async def fetch_prediction(self, uniprot_accession: str) -> list[AlphaFoldPrediction]:
        data = await self._get_json(
            f"{self.BASE_URL}/api/prediction/{uniprot_accession}",
        )
        if not isinstance(data, list):
            msg = f"Unexpected response format for {uniprot_accession}"
            raise ReferenceError(msg, source="alphafold")
        return [self._parse_prediction(item) for item in data]

    async def fetch_prediction_by_accessions(
        self,
        accessions: list[str],
        max_concurrent: int = 5,
    ) -> list[AlphaFoldPrediction]:
        import asyncio

        sem = asyncio.Semaphore(max_concurrent)

        async def _fetch_one(acc: str) -> list[AlphaFoldPrediction]:
            async with sem:
                return await self.fetch_prediction(acc)

        results = await asyncio.gather(
            *[_fetch_one(acc) for acc in accessions],
            return_exceptions=True,
        )
        predictions: list[AlphaFoldPrediction] = []
        for acc, result in zip(accessions, results, strict=False):
            if isinstance(result, Exception):
                logger.warning("Failed to fetch AlphaFold prediction for %s: %s", acc, result)
            else:
                predictions.extend(result)
        return predictions

    async def search_by_gene(
        self,
        gene: str,
        uniprot_client: Any,  # noqa: ANN401
    ) -> list[AlphaFoldPrediction]:
        result = await uniprot_client.search(f"gene:{gene}", size=50)
        accessions = [r.primary_accession for r in result.results]
        return await self.fetch_prediction_by_accessions(accessions)

    # --- 4.18.2: Structure download ---

    async def download_structure(
        self,
        prediction: AlphaFoldPrediction,
        output_path: str | None = None,
        format: str = "pdb",
    ) -> bytes | str:
        url = prediction.pdb_url if format == "pdb" else prediction.cif_url
        if not url:
            msg = f"No {format.upper()} URL available for {prediction.entry_id}"
            raise ReferenceError(msg, source="alphafold")
        content = await self._get_bytes(url)
        if output_path is None:
            return content
        with open(output_path, "wb") as f:
            f.write(content)
        return output_path

    async def download_batch(
        self,
        predictions: list[AlphaFoldPrediction],
        output_dir: str,
        format: str = "pdb",
    ) -> list[str]:
        import os

        paths: list[str] = []
        for pred in predictions:
            ext = ".pdb" if format == "pdb" else ".cif"
            path = os.path.join(output_dir, f"{pred.entry_id}{ext}")
            await self.download_structure(pred, output_path=path, format=format)
            paths.append(path)
        return paths

    # --- 4.18.3: pLDDT confidence propagation ---

    async def fetch_plddt(self, prediction: AlphaFoldPrediction) -> list[ResidueConfidence]:
        if not prediction.plddt_url:
            msg = f"No pLDDT URL for {prediction.entry_id}"
            raise ReferenceError(msg, source="alphafold")
        data = await self._get_json(prediction.plddt_url)
        residue_numbers = data.get("residueNumber", [])
        confidence_scores = data.get("confidenceScore", [])
        categories = data.get("confidenceCategory", [])

        residues: list[ResidueConfidence] = []
        for i in range(len(residue_numbers)):
            score = confidence_scores[i] if i < len(confidence_scores) else 0.0
            cat = categories[i] if i < len(categories) else _plddt_category(score)
            residues.append(
                ResidueConfidence(
                    residue_number=residue_numbers[i],
                    plddt_score=score,
                    confidence_category=cat,
                    is_disordered=score < _PLDDT_LOW,
                )
            )
        return residues

    def get_confidence_trace(self, prediction: AlphaFoldPrediction) -> ConfidenceTrace:
        return ConfidenceTrace(
            value=prediction.global_metric_value / 100.0,
            source="alphafold",
            weight=1.0,
        )

    def get_per_residue_trace(
        self,
        residues: list[ResidueConfidence],
    ) -> ConfidenceTrace:
        children = [
            ConfidenceTrace(
                value=r.plddt_score / 100.0,
                source="alphafold",
                weight=1.0,
            )
            for r in residues
        ]
        return ConfidenceTrace(
            value=0.0,
            source="alphafold",
            weight=1.0,
            children=children,
        ).propagate(PropagationStrategy.WEIGHTED_AVERAGE)

    # --- 4.18.4: PAE data extraction ---

    async def fetch_pae(self, prediction: AlphaFoldPrediction) -> PaeMatrix:
        if not prediction.pae_url:
            msg = f"No PAE URL for {prediction.entry_id}"
            raise ReferenceError(msg, source="alphafold")
        data = await self._get_json(prediction.pae_url)
        if isinstance(data, list) and len(data) > 0:
            matrix = data[0].get("predicted_aligned_error", [])
        else:
            matrix = []

        residue_count = len(matrix)
        pae = PaeMatrix(
            residue_count=residue_count,
            pae_values=matrix,
        )
        pae.domain_regions = self._cluster_domains(matrix)
        return pae

    @staticmethod
    def _cluster_domains(
        matrix: list[list[float]],
        threshold: float = _PAE_DOMAIN_THRESHOLD,
    ) -> list[DomainRegion]:
        if not matrix:
            return []
        n = len(matrix)
        if n == 0:
            return []

        regions: list[DomainRegion] = []
        start = 0
        for i in range(1, n):
            if matrix[i][i - 1] > threshold:
                regions.append(
                    DomainRegion(
                        start=start,
                        end=i - 1,
                        size=i - start,
                        mean_pae=_mean_submatrix(matrix, start, i - 1),
                    )
                )
                start = i
        regions.append(
            DomainRegion(
                start=start,
                end=n - 1,
                size=n - start,
                mean_pae=_mean_submatrix(matrix, start, n - 1),
            )
        )
        return regions

    # --- 4.18.5: Confidence warnings ---

    def check_confidence(
        self,
        prediction: AlphaFoldPrediction,
        cutoff: float | None = None,
    ) -> list[str]:
        cutoff = cutoff if cutoff is not None else self._confidence_cutoff
        warnings: list[str] = []
        overall = prediction.global_metric_value
        if overall < cutoff:
            warnings.append(
                f"Overall pLDDT {overall:.1f} below confidence cutoff {cutoff:.1f}",
            )
        return warnings

    def check_residue_confidence(
        self,
        residues: list[ResidueConfidence],
        cutoff: float = 70.0,
    ) -> list[str]:
        low_conf = [r for r in residues if r.plddt_score < cutoff]
        if not low_conf:
            return []
        n = len(residues)
        frac = len(low_conf) / n * 100 if n > 0 else 0.0
        return [
            f"{len(low_conf)}/{n} residues ({frac:.1f}%) below pLDDT cutoff {cutoff:.1f}",
        ]

    # --- 4.18.6: Disorder flagging ---

    def analyze_disorder(
        self,
        residues: list[ResidueConfidence],
        threshold: float = _PLDDT_LOW,
    ) -> DisorderReport:
        if not residues:
            return DisorderReport()

        regions: list[DisorderedRegion] = []
        start: int | None = None
        run_scores: list[float] = []

        for r in residues:
            if r.plddt_score < threshold:
                if start is None:
                    start = r.residue_number
                run_scores.append(r.plddt_score)
            else:
                if start is not None and run_scores:
                    regions.append(
                        DisorderedRegion(
                            start=start,
                            end=r.residue_number - 1,
                            length=len(run_scores),
                            mean_plddt=sum(run_scores) / len(run_scores),
                        )
                    )
                    start = None
                    run_scores = []

        if start is not None and run_scores:
            regions.append(
                DisorderedRegion(
                    start=start,
                    end=residues[-1].residue_number,
                    length=len(run_scores),
                    mean_plddt=sum(run_scores) / len(run_scores),
                )
            )

        total_disordered = sum(r.length for r in regions)
        n_total = len(residues)
        return DisorderReport(
            regions=regions,
            total_disordered_residues=total_disordered,
            fraction_disordered=total_disordered / n_total if n_total > 0 else 0.0,
        )

    async def fetch_disorder_report(
        self,
        prediction: AlphaFoldPrediction,
    ) -> DisorderReport:
        residues = await self.fetch_plddt(prediction)
        return self.analyze_disorder(residues)

    # --- 4.18.7: Bulk download ---

    @staticmethod
    def get_proteome_download_url(
        taxon_id: int,
        proteome_id: str,
        version: str = "latest",
    ) -> str:
        key = f"{proteome_id}_{taxon_id}"
        suffix = _KNOWN_PROTEOMES.get(key, f"{taxon_id}_PROTEOME")
        return (
            f"https://ftp.ebi.ac.uk/pub/databases/alphafold/{version}/"
            f"{proteome_id}_{taxon_id}_{suffix}_v{version}.tar"
        )

    @staticmethod
    def list_known_proteomes() -> dict[str, str]:
        return dict(_KNOWN_PROTEOMES)

    async def download_proteome_archive(self, url: str, output_path: str) -> str:
        content = await self._get_bytes(url)
        with open(output_path, "wb") as f:
            f.write(content)
        return output_path

    # --- Response parsing ---

    def _parse_prediction(self, item: dict[str, Any]) -> AlphaFoldPrediction:
        return AlphaFoldPrediction(
            entry_id=item.get("entryId", ""),
            uniprot_accession=item.get("uniprotAccession", ""),
            uniprot_id=item.get("uniprotId", ""),
            uniprot_description=item.get("uniprotDescription", ""),
            gene=item.get("gene", ""),
            organism_scientific_name=item.get("organismScientificName", ""),
            organism_common_name=item.get("organismCommonName", ""),
            tax_id=item.get("taxId", 0),
            is_reviewed=item.get("isUniProtReviewed", False),
            is_reference_proteome=item.get("isUniProtReferenceProteome", False),
            sequence=item.get("sequence", ""),
            sequence_length=len(item.get("sequence", "")),
            global_metric_value=item.get("globalMetricValue", 0.0),
            fraction_plddt_very_high=item.get("fractionPlddtVeryHigh", 0.0),
            fraction_plddt_confident=item.get("fractionPlddtConfident", 0.0),
            fraction_plddt_low=item.get("fractionPlddtLow", 0.0),
            fraction_plddt_very_low=item.get("fractionPlddtVeryLow", 0.0),
            latest_version=item.get("latestVersion", 0),
            all_versions=item.get("allVersions", []),
            model_created_date=item.get("modelCreatedDate", ""),
            pdb_url=item.get("pdbUrl", ""),
            cif_url=item.get("cifUrl", ""),
            bcif_url=item.get("bcifUrl", ""),
            pae_url=item.get("paeDocUrl", ""),
            plddt_url=item.get("plddtDocUrl", ""),
            pae_image_url=item.get("paeImageUrl", ""),
            msa_url=item.get("msaUrl", ""),
            evidence_label=EvidenceTypeLabel.PREDICTED,
            extra={
                "provider_id": item.get("providerId", ""),
                "tool_used": item.get("toolUsed", ""),
                "entity_type": item.get("entityType", ""),
                "is_complex": item.get("isComplex", False),
                "am_annotations_url": item.get("amAnnotationsUrl", ""),
            },
        )

    async def close(self) -> None:
        await self._client.aclose()


def _mean_submatrix(matrix: list[list[float]], start: int, end: int) -> float:
    values: list[float] = []
    for i in range(start, end + 1):
        for j in range(start, end + 1):
            if i < len(matrix) and j < len(matrix[i]):
                values.append(matrix[i][j])
    if not values:
        return 0.0
    return sum(values) / len(values)

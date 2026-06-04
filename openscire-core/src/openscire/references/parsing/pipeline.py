from __future__ import annotations

import logging
import time
from typing import Any

from openscire.references.parsing.figure_extractor import FigureExtractor
from openscire.references.parsing.grobid_client import GrobidClient, GrobidConfig
from openscire.references.parsing.models import ExtractionResult
from openscire.references.parsing.pdf_extractor import PDFExtractor
from openscire.references.parsing.reference_parser import ReferenceParser
from openscire.references.parsing.section_parser import SectionParser

logger = logging.getLogger(__name__)


class PDFParsingPipeline:
    def __init__(self, grobid_config: GrobidConfig | None = None) -> None:
        self._grobid_client: GrobidClient | None = None
        if grobid_config is not None:
            self._grobid_client = GrobidClient(grobid_config)
        self._pdf_extractor = PDFExtractor()
        self._section_parser = SectionParser()
        self._reference_parser = ReferenceParser()
        self._figure_extractor = FigureExtractor()

    async def parse(
        self,
        pdf_bytes: bytes,
        source_path: str = "",
        resolve_dois: bool = False,
        doi_resolver: Any | None = None,  # noqa: ANN401
    ) -> ExtractionResult:
        start = time.monotonic()
        warnings: list[str] = []
        method = "pdfplumber"

        if self._grobid_client is not None:
            try:
                grobid_article = await self._grobid_client.process_fulltext(pdf_bytes)
                if grobid_article is not None:
                    elapsed = time.monotonic() - start
                    result = ExtractionResult(
                        method="grobid",
                        full_text=grobid_article,
                        extraction_time=elapsed,
                        source_path=source_path,
                    )
                    result.parsed_references = self._reference_parser.extract_from_section(
                        "\n".join(grobid_article.references)
                    )
                    return result
                warnings.append("GROBID unavailable — falling back to pdfplumber")
            except Exception as e:
                warnings.append(f"GROBID processing failed: {e}")
                logger.warning("GROBID fallback: %s", e)

        try:
            extracted = self._pdf_extractor.extract(pdf_bytes)
        except Exception as e:
            elapsed = time.monotonic() - start
            return ExtractionResult(
                method="error",
                extraction_time=elapsed,
                warnings=[f"PDF extraction failed: {e}"],
                source_path=source_path,
            )

        raw_text = extracted["raw_text"]
        pages_data = extracted.get("pages", [])
        page_count = len(pages_data)

        article = self._section_parser.parse(raw_text)

        ref_section_text = self._find_reference_section(article)
        if ref_section_text:
            parsed_refs = self._reference_parser.extract_from_section(ref_section_text)
        else:
            parsed_refs = self._reference_parser.extract_references(raw_text)

        if resolve_dois and parsed_refs:
            try:
                parsed_refs = await self._reference_parser.resolve_dois(parsed_refs, doi_resolver)
            except Exception as e:
                warnings.append(f"DOI resolution failed: {e}")

        figures: list[Any] = []
        try:
            figures = self._figure_extractor.extract(pdf_bytes, raw_text)
        except Exception as e:
            warnings.append(f"Figure extraction failed: {e}")
        article.figures = figures

        elapsed = time.monotonic() - start
        return ExtractionResult(
            method=method,
            full_text=article,
            parsed_references=parsed_refs,
            pages=page_count,
            extraction_time=elapsed,
            warnings=warnings,
            source_path=source_path,
        )

    async def parse_file(
        self,
        path: str,
        resolve_dois: bool = False,
        doi_resolver: Any | None = None,  # noqa: ANN401
    ) -> ExtractionResult:
        with open(path, "rb") as f:
            pdf_bytes = f.read()
        return await self.parse(
            pdf_bytes, source_path=path, resolve_dois=resolve_dois, doi_resolver=doi_resolver
        )

    async def close(self) -> None:
        if self._grobid_client is not None:
            await self._grobid_client.close()

    @staticmethod
    def _find_reference_section(article: Any) -> str:  # noqa: ANN401
        for section in article.sections:
            heading = section.heading.lower().strip(" .:")
            if heading == "references":
                return section.body
        return ""

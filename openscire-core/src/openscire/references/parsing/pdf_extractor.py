from __future__ import annotations

import logging
import time
from typing import Any

from openscire.constants import ErrorCode
from openscire.exceptions import ReferenceError
from openscire.references.parsing.models import PageText

logger = logging.getLogger(__name__)


class PDFExtractor:
    def __init__(self) -> None:
        self._pdfplumber = None

    def _get_pdfplumber(self) -> Any:  # noqa: ANN401
        if self._pdfplumber is None:
            try:
                import pdfplumber  # type: ignore[import-untyped]

                self._pdfplumber = pdfplumber
            except ImportError:
                raise ReferenceError(
                    "pdfplumber is required for PDF extraction",
                    source="pdf_extractor",
                    error_code=ErrorCode.ERR_BASE,
                ) from None
        return self._pdfplumber

    def extract(self, pdf_bytes: bytes) -> dict[str, Any]:
        pdfplumber = self._get_pdfplumber()
        start = time.monotonic()

        try:
            import io

            pdf = pdfplumber.open(io.BytesIO(pdf_bytes))
        except Exception as e:
            raise ReferenceError(
                f"Failed to open PDF: {e}",
                source="pdf_extractor",
                error_code=ErrorCode.REF_PARSE_ERROR,
            ) from e

        if pdf.metadata and pdf.metadata.get("encrypted"):
            pdf.close()
            raise ReferenceError(
                "Encrypted PDF without password is not supported",
                source="pdf_extractor",
                error_code=ErrorCode.REF_PARSE_ERROR,
            )

        pages: list[PageText] = []
        raw_text_parts: list[str] = []
        metadata: dict[str, Any] = {}

        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            tables_raw: list[list[list[str]]] = []
            try:
                tables = page.extract_tables() or []
                for table in tables:
                    table_rows: list[list[str]] = []
                    for row in table:
                        table_rows.append([str(cell or "") for cell in row])
                    tables_raw.append(table_rows)
            except Exception:
                tables_raw = []

            pages.append(
                PageText(
                    page_num=i + 1,
                    text=text,
                    width=float(page.width or 0),
                    height=float(page.height or 0),
                    tables=tables_raw,
                )
            )
            raw_text_parts.append(text)

        if pdf.metadata:
            metadata = dict(pdf.metadata)

        elapsed = time.monotonic() - start
        logger.debug("Extracted %d pages in %.2fs", len(pages), elapsed)

        pdf.close()
        return {
            "pages": pages,
            "metadata": metadata,
            "raw_text": "\n".join(raw_text_parts),
            "elapsed": elapsed,
        }

    def extract_from_path(self, path: str) -> dict[str, Any]:
        with open(path, "rb") as f:
            return self.extract(f.read())

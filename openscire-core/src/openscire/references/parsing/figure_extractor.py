from __future__ import annotations

import logging
import re
from typing import Any

from openscire.constants import ErrorCode
from openscire.exceptions import ReferenceError
from openscire.references.models import ArticleFigure

logger = logging.getLogger(__name__)

_FIGURE_CAPTION = re.compile(
    r"(?:Figure|Fig\.?|Figura|Abbildung|Figuren)\s*(\d+[\.\d]*)\b[.:]?\s*(.*?)(?=\n\s*(?:Figure|Fig\.?|Table|Figura|Abbildung)\s|\Z)",
    re.IGNORECASE | re.DOTALL,
)

_TABLE_CAPTION = re.compile(
    r"(?:Table|Tabelle|Tabla|Tableau)\s*(\d+[\.\d]*)\b[.:]?\s*(.*?)(?=\n\s*(?:Figure|Fig\.?|Table|Tabelle)\s|\Z)",
    re.IGNORECASE | re.DOTALL,
)

_CAPTION_LINE = re.compile(
    r"^\s*(?:Figure|Fig\.?|Table)\s+(\d+[\.\d]*)\b[.:]?\s*(.*)",
    re.IGNORECASE,
)


class FigureExtractor:
    def __init__(self) -> None:
        self._pymupdf = None

    def _get_pymupdf(self) -> Any:  # noqa: ANN401
        if self._pymupdf is None:
            try:
                import fitz  # type: ignore[import-untyped]

                self._pymupdf = fitz
            except ImportError:
                raise ReferenceError(
                    "pymupdf is required for figure extraction",
                    source="figure_extractor",
                    error_code=ErrorCode.ERR_BASE,
                ) from None
        return self._pymupdf

    def extract_images(self, pdf_bytes: bytes) -> list[dict[str, Any]]:
        fitz = self._get_pymupdf()
        images: list[dict[str, Any]] = []
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            raise ReferenceError(
                f"Failed to open PDF for image extraction: {e}",
                source="figure_extractor",
                error_code=ErrorCode.REF_PARSE_ERROR,
            ) from e

        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images(full=True)
            for img_idx, img in enumerate(image_list):
                xref = img[0]
                try:
                    base_image = doc.extract_image(xref)
                    images.append(
                        {
                            "xref": xref,
                            "page_num": page_num + 1,
                            "width": base_image.get("width", 0),
                            "height": base_image.get("height", 0),
                            "image_id": f"page{page_num + 1}_img{img_idx + 1}",
                        }
                    )
                except Exception:
                    logger.debug("Failed to extract image xref %d on page %d", xref, page_num + 1)

        doc.close()
        return images

    def extract_captions(self, text: str) -> list[dict[str, str]]:
        captions: list[dict[str, str]] = []

        for match in _FIGURE_CAPTION.finditer(text):
            label_text = f"Figure {match.group(1)}"
            caption_text = match.group(2).strip() if match.group(2) else ""
            if caption_text:
                captions.append(
                    {
                        "label": label_text,
                        "caption": caption_text,
                    }
                )

        for match in _TABLE_CAPTION.finditer(text):
            label_text = f"Table {match.group(1)}"
            caption_text = match.group(2).strip() if match.group(2) else ""
            if caption_text:
                captions.append(
                    {
                        "label": label_text,
                        "caption": caption_text,
                    }
                )

        return captions

    def extract(self, _pdf_bytes: bytes, raw_text: str) -> list[ArticleFigure]:
        figures: list[ArticleFigure] = []
        seen_labels: set[str] = set()

        captions = self.extract_captions(raw_text)
        for cap in captions:
            label = cap["label"]
            if label.lower() in seen_labels:
                continue
            seen_labels.add(label.lower())
            figures.append(
                ArticleFigure(
                    id=f"fig_{len(figures) + 1}",
                    label=label,
                    caption=cap["caption"],
                )
            )

        if not figures:
            lines = raw_text.split("\n")
            for line in lines:
                match = _CAPTION_LINE.match(line)
                if match:
                    label = f"Figure {match.group(1)}"
                    caption = match.group(2).strip()
                    if label.lower() not in seen_labels:
                        seen_labels.add(label.lower())
                        figures.append(
                            ArticleFigure(
                                id=f"fig_{len(figures) + 1}",
                                label=label,
                                caption=caption,
                            )
                        )

        return figures

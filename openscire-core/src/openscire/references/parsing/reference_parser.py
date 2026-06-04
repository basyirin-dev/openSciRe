from __future__ import annotations

import logging
import re
from typing import Any

from openscire.references.parsing.models import ParsedReference

logger = logging.getLogger(__name__)

_NUMERIC_REF_PREFIX = re.compile(r"^\s*(?:\[(\d+)\]|\((\d+)\)|(\d+)\.)\s*")

_DOI_PATTERN = re.compile(r"(10\.\d{4,}/[-._;()/:$\w]+)", re.IGNORECASE)

_PMID_PATTERN = re.compile(r"\b(?:PMID[:\s]*)?(\d{8})\b")

_ARXIV_PATTERN = re.compile(r"\b(?:arXiv[:\s]*)?(\d{4}\.\d{4,})(?:v\d+)?\b", re.IGNORECASE)

_AUTHOR_YEAR_PREFIX = re.compile(
    r"^([A-Z][a-z]+(?:\s(?:[A-Z]\.?\s?)*[A-Z][a-z]+)*(?:\s+et\s+al\.?)?)\s*[\(\[]?(\d{4})[\)\]]?",
)

_BRACKETED_AUTHOR_PREFIX = re.compile(
    r"^\[(\d+)\]\s*([A-Z][a-z]+)",
)


class ReferenceParser:
    def extract_references(self, text: str) -> list[ParsedReference]:
        lines = text.split("\n")
        refs: list[ParsedReference] = []
        current: ParsedReference | None = None

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            match = _NUMERIC_REF_PREFIX.match(stripped)
            if match:
                if current is not None:
                    refs.append(current)
                num = next(g for g in match.groups() if g is not None)
                current = ParsedReference(
                    index=int(num),
                    raw_text=stripped[match.end() :].strip(),
                )
            else:
                if current is not None and not re.match(
                    r"^\s*(?:Figure|Table|Fig\.|http|www\.)",
                    stripped,
                    re.IGNORECASE,
                ):
                    current.raw_text = current.raw_text + " " + stripped

        if current is not None:
            refs.append(current)

        for ref in refs:
            self._enrich(ref)

        logger.debug("Extracted %d references", len(refs))
        return refs

    def extract_from_section(self, section_text: str) -> list[ParsedReference]:
        return self.extract_references(section_text)

    async def resolve_dois(
        self,
        refs: list[ParsedReference],
        resolver: Any | None = None,  # noqa: ANN401
    ) -> list[ParsedReference]:
        if resolver is None:
            return refs
        for ref in refs:
            if ref.doi:
                try:
                    result = await resolver(ref.doi)
                    if result:
                        ref.title = getattr(result, "title", ref.title)
                        ref.confidence = 0.9
                except Exception:
                    logger.debug("DOI resolution failed for %s", ref.doi)
        return refs

    @staticmethod
    def _enrich(ref: ParsedReference) -> None:
        text = ref.raw_text

        doi_match = _DOI_PATTERN.search(text)
        if doi_match:
            raw_doi = doi_match.group(1)
            ref.doi = raw_doi.rstrip(".,;:)")
            ref.confidence = max(ref.confidence, 0.7)

        pmid_match = _PMID_PATTERN.search(text)
        if pmid_match:
            ref.pmid = pmid_match.group(1)
            ref.confidence = max(ref.confidence, 0.5)

        arxiv_match = _ARXIV_PATTERN.search(text)
        if arxiv_match:
            ref.arxiv_id = arxiv_match.group(1)
            ref.confidence = max(ref.confidence, 0.5)

        author_match = _AUTHOR_YEAR_PREFIX.search(text)
        if author_match:
            ref.authors = author_match.group(1).strip()
            ref.year = int(author_match.group(2))
            if not ref.confidence:
                ref.confidence = 0.4

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

import httpx

from openscire.constants import ErrorCode
from openscire.exceptions import ReferenceError
from openscire.references.models import (
    ArticleFigure,
    ArticleSection,
    FullTextArticle,
    ReferenceAuthor,
)

logger = logging.getLogger(__name__)

_GROBID_BASE = "http://localhost:8070"


class GrobidConfig:
    def __init__(
        self,
        base_url: str = _GROBID_BASE,
        timeout: int = 120,
        batch_size: int = 10,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.batch_size = batch_size


class GrobidClient:
    def __init__(self, config: GrobidConfig | None = None) -> None:
        self._config = config or GrobidConfig()
        self._client = httpx.AsyncClient(
            timeout=self._config.timeout,
            follow_redirects=True,
        )
        self._available: bool | None = None

    async def check_availability(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            response = await self._client.get(
                f"{self._config.base_url}/api/isalive",
                timeout=5.0,
            )
            self._available = response.status_code == 200
        except Exception:
            self._available = False
        return self._available

    async def process_fulltext(self, pdf_bytes: bytes) -> FullTextArticle | None:
        if not await self.check_availability():
            logger.warning("GROBID is not available at %s", self._config.base_url)
            return None

        try:
            files = {"input": ("paper.pdf", pdf_bytes, "application/pdf")}
            response = await self._client.post(
                f"{self._config.base_url}/api/processFulltextDocument",
                files=files,
            )
            response.raise_for_status()
            tei_xml = response.text
            return self._parse_tei(tei_xml)
        except httpx.TimeoutException:
            raise ReferenceError(
                "GROBID request timed out",
                source="grobid",
                error_code=ErrorCode.REF_NETWORK_ERROR,
            ) from None
        except httpx.HTTPStatusError as e:
            raise ReferenceError(
                f"GROBID API error ({e.response.status_code})",
                source="grobid",
                error_code=ErrorCode.REF_NETWORK_ERROR,
            ) from e
        except httpx.RequestError as e:
            raise ReferenceError(
                f"GROBID request failed: {e}",
                source="grobid",
                error_code=ErrorCode.REF_NETWORK_ERROR,
            ) from e

    async def close(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _parse_tei(tei_xml: str) -> FullTextArticle:
        root = ET.fromstring(tei_xml)
        ns = {"tei": "http://www.tei-c.org/ns/1.0"}
        article = FullTextArticle()

        title_el = root.find(".//tei:titleStmt/tei:title", ns)
        if title_el is not None and title_el.text:
            article.title = title_el.text.strip()

        for author_el in root.findall(
            ".//tei:sourceDesc/tei:biblStruct/tei:analytic/tei:author", ns
        ):
            forename = author_el.find("tei:forename", ns)
            surname = author_el.find("tei:surname", ns)
            fname = forename.text.strip() if forename is not None and forename.text else ""
            sname = surname.text.strip() if surname is not None and surname.text else ""
            full = f"{fname} {sname}".strip()
            article.authors.append(ReferenceAuthor(first=fname, last=sname, full=full))

        journal_el = root.find(".//tei:sourceDesc/tei:biblStruct/tei:monogr/tei:title", ns)
        if journal_el is not None and journal_el.text:
            article.journal = journal_el.text.strip()

        abstract_el = root.find(".//tei:profileDesc/tei:abstract", ns)
        if abstract_el is not None:
            abstract_parts: list[str] = []
            for p in abstract_el.findall("tei:p", ns):
                if p.text:
                    abstract_parts.append(p.text.strip())
            article.abstract = "\n".join(abstract_parts)

        for div in root.findall(".//tei:text/tei:body/tei:div", ns):
            head = div.find("tei:head", ns)
            heading = head.text.strip() if head is not None and head.text else ""
            body_parts: list[str] = []
            for p in div.findall("tei:p", ns):
                if p.text:
                    body_parts.append(p.text.strip())
            article.sections.append(
                ArticleSection(
                    heading=heading,
                    body="\n".join(body_parts),
                )
            )

        for ref_el in root.findall(
            ".//tei:text/tei:back/tei:div[@type='references']/tei:listBibl/tei:biblStruct",
            ns,
        ):
            ref_text_parts: list[str] = []
            for elem in ref_el.iter():
                if elem.text:
                    ref_text_parts.append(elem.text.strip())
            ref_text = " ".join(ref_text_parts)
            if ref_text:
                article.references.append(ref_text)

        for fig_el in root.findall(".//tei:figure", ns):
            fig_head = fig_el.find("tei:head", ns)
            fig_label = fig_head.text.strip() if fig_head is not None and fig_head.text else ""
            fig_caption_parts: list[str] = []
            for p in fig_el.findall("tei:figDesc", ns):
                if p.text:
                    fig_caption_parts.append(p.text.strip())
            article.figures.append(
                ArticleFigure(
                    id=f"grobid_fig_{len(article.figures) + 1}",
                    label=fig_label,
                    caption=" ".join(fig_caption_parts),
                )
            )

        return article

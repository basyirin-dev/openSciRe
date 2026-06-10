# SPDX-License-Identifier: Apache-2.0

"""PMC bridge — OA subset download, full-text JATS XML parsing, PMID↔PMCID conversion."""

from __future__ import annotations

import asyncio
import contextlib
import time
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from openscire.exceptions import ReferenceError
from openscire.logging import get_logger
from openscire.references.models import (
    ArticleFigure,
    ArticleSection,
    FullTextArticle,
    ReferenceAuthor,
)

logger = get_logger("openscire.references.bridges.pmc")

OA_BASE = "https://www.ncbi.nlm.nih.gov/pmc/tools/oa-service"
EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
IDCONV_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0"

PMC_NS = {
    "x": "http://www.w3.org/1999/xhtml",
    "": "http://www.w3.org/1999/xhtml",
}


class PMCRateLimiter:
    """Simple asyncio rate limiter for PMC API requests."""

    def __init__(self, requests_per_sec: float = 3.0) -> None:
        self._delay = 1.0 / requests_per_sec
        self._last = 0.0

    async def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        if elapsed < self._delay:
            await asyncio.sleep(self._delay - elapsed)
        self._last = time.monotonic()


class PMCBridge:
    """Bridge to PubMed Central — OA subset download and full-text XML parsing.

    Provides access to full-text articles from PMC via the OA service
    and E-utilities, plus JATS XML parsing into structured FullTextArticle objects.
    """

    def __init__(
        self,
        api_key: str = "",
        email: str = "",
        tool: str = "openscire",
        timeout: int = 120,
    ) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )
        self._api_key = api_key
        self._email = email
        self._tool = tool
        self._rate_limiter = PMCRateLimiter(3.0)

    async def _eutils_get(self, url: str, params: dict[str, str]) -> httpx.Response:
        await self._rate_limiter.wait()
        p: dict[str, str] = {"tool": self._tool}
        if self._email:
            p["email"] = self._email
        if self._api_key:
            p["api_key"] = self._api_key
        p.update(params)
        response = await self._client.get(url, params=p)
        if response.status_code != 200:
            raise ReferenceError(
                f"PMC request failed ({response.status_code})",
                source="pmc",
            )
        return response

    async def search_pmc(self, query: str, max_results: int = 20, retstart: int = 0) -> list[str]:
        """Search PMC articles via E-utilities esearch with db=pmc.

        Args:
            query: PMC search query.
            max_results: Maximum results to return.
            retstart: Starting offset.

        Returns:
            List of PMCID strings (e.g., 'PMC123456').
        """
        params = {
            "db": "pmc",
            "term": query,
            "retmax": str(max_results),
            "retstart": str(retstart),
            "retmode": "xml",
        }
        response = await self._eutils_get(f"{EUTILS_BASE}/esearch.fcgi", params)
        root = ET.fromstring(response.content)
        id_list = root.findall(".//IdList/Id")
        return [f"PMC{id_el.text}" for id_el in id_list if id_el.text]

    async def convert_pmid_to_pmcid(self, pmid: str) -> str | None:
        """Convert a PMID to a PMCID via NCBI's idconv API.

        Args:
            pmid: PubMed identifier.

        Returns:
            PMCID string (e.g., 'PMC123456') or None.
        """
        params = {"ids": pmid, "format": "json"}
        if self._api_key:
            params["api_key"] = self._api_key
        await self._rate_limiter.wait()
        try:
            response = await self._client.get(IDCONV_URL, params=params)
            response.raise_for_status()
            raw: dict[str, Any] = response.json()
            records = raw.get("records", [])
            if records:
                pmcid = records[0].get("pmcid", "")
                if pmcid:
                    return str(pmcid)
        except Exception as exc:
            logger.warning("PMID→PMCID conversion failed for %s: %s", pmid, exc)
        return None

    async def fetch_full_text(self, pmcid: str) -> FullTextArticle | None:
        """Fetch and parse full-text XML for a PMC article.

        Downloads the NXML from PMC's OA service and parses into
        a structured FullTextArticle.

        Args:
            pmcid: PMCID string (e.g., 'PMC123456').

        Returns:
            FullTextArticle with sections, references, and figures,
            or None if not available in OA.
        """
        clean_id = pmcid.replace("PMC", "")

        # Use the oa-service list endpoint to find the file
        params = {"format": "json", "id": clean_id}
        if self._api_key:
            params["api_key"] = self._api_key

        await self._rate_limiter.wait()
        try:
            response = await self._client.get(OA_BASE, params=params)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            records = data.get("records", [])
            if not records:
                logger.info("PMC article %s not found in OA subset", pmcid)
                return None

            record = records[0]
            files = record.get("files", [])
            nxml_url = ""
            for f in files:
                if f.get("format") == "tgz" or f.get("format") == "xml":
                    nxml_url = f.get("fulltext_url", "")
                    break

            if nxml_url:
                await self._rate_limiter.wait()
                xml_resp = await self._client.get(nxml_url)
                xml_resp.raise_for_status()
                return self._parse_article_xml(xml_resp.content)

        except httpx.HTTPStatusError as exc:
            logger.warning("OA download failed for %s: %s", pmcid, exc)
        except Exception as exc:
            logger.warning("Unexpected error fetching %s: %s", pmcid, exc)

        return None

    async def fetch_full_text_by_pmid(self, pmid: str) -> FullTextArticle | None:
        """Fetch full-text for a PMID by first converting to PMCID.

        Args:
            pmid: PubMed identifier.

        Returns:
            FullTextArticle or None.
        """
        pmcid = await self.convert_pmid_to_pmcid(pmid)
        if not pmcid:
            return None
        return await self.fetch_full_text(pmcid)

    @staticmethod
    def _parse_article_xml(xml_data: bytes | str) -> FullTextArticle:  # noqa: C901, PLR0912
        """Parse JATS XML (NXML from PMC) into a FullTextArticle.

        Handles the PMC NXML format which uses a mix of namespaces.
        """
        if isinstance(xml_data, bytes):
            xml_data = xml_data.decode("utf-8", errors="replace")
        root = ET.fromstring(xml_data)

        pmid = ""
        pmcid = ""
        doi = ""
        for aid in root.iter("article-id"):
            aid_type = aid.get("pub-id-type", "")
            text = aid.text or ""
            if aid_type == "pmid":
                pmid = text
            elif aid_type == "pmc":
                pmcid = f"PMC{text}" if not text.startswith("PMC") else text
            elif aid_type == "doi":
                doi = text

        title_el = root.find(".//article-title")
        title = "".join(title_el.itertext()) if title_el is not None else ""

        abstract_el = root.find(".//abstract")
        abstract = ""
        if abstract_el is not None:
            abstract = "".join(abstract_el.itertext())

        authors: list[ReferenceAuthor] = []
        contrib_group = root.find(".//contrib-group")
        if contrib_group is not None:
            for contrib in contrib_group.findall("contrib"):
                if contrib.get("contrib-type") == "author":
                    surname_el = contrib.find("name/surname")
                    given_el = contrib.find("name/given-names")
                    if surname_el is not None:
                        authors.append(
                            ReferenceAuthor(
                                last=surname_el.text or "",
                                first=(given_el.text or "") if given_el is not None else "",
                            )
                        )

        journal_el = root.find(".//journal-title")
        journal = journal_el.text or "" if journal_el is not None else ""

        volume = ""
        vol_el = root.find(".//volume")
        if vol_el is not None:
            volume = vol_el.text or ""
        issue = ""
        iss_el = root.find(".//issue")
        if iss_el is not None:
            issue = iss_el.text or ""

        year = None
        year_el = root.find(".//pub-date/year")
        if year_el is not None and year_el.text:
            with contextlib.suppress(ValueError):
                year = int(year_el.text)

        pages = ""
        fpage = root.find(".//fpage")
        lpage = root.find(".//lpage")
        if fpage is not None:
            pages = fpage.text or ""
            if lpage is not None and lpage.text:
                pages += f"-{lpage.text}"

        sections: list[ArticleSection] = []
        for sec in root.iter("sec"):
            heading_el = sec.find("title")
            heading = heading_el.text or "" if heading_el is not None else ""
            body = "".join(sec.itertext()).strip()
            # Remove heading text from body to avoid duplication
            if heading and body.startswith(heading):
                body = body[len(heading) :].lstrip()
            sections.append(
                ArticleSection(
                    heading=heading,
                    body=body,
                )
            )

        references: list[str] = []
        ref_list = root.find(".//ref-list")
        if ref_list is not None:
            for ref in ref_list.findall("ref"):
                ref_text = "".join(ref.itertext()).strip()
                if ref_text:
                    references.append(ref_text)

        figures: list[ArticleFigure] = []
        for fig in root.iter("fig"):
            label_el = fig.find("label")
            label = label_el.text or "" if label_el is not None else ""
            caption_el = fig.find(".//caption")
            caption = "".join(caption_el.itertext()) if caption_el is not None else ""
            figures.append(
                ArticleFigure(
                    label=label,
                    caption=caption,
                    id=fig.get("id", ""),
                )
            )

        license_text = ""
        license_el = root.find(".//license-p")
        if license_el is not None:
            license_text = "".join(license_el.itertext())

        return FullTextArticle(
            pmid=pmid,
            pmcid=pmcid,
            doi=doi,
            title=title,
            authors=authors,
            journal=journal or "",
            year=year,
            volume=volume,
            issue=issue,
            pages=pages,
            abstract=abstract,
            sections=sections,
            references=references,
            figures=figures,
            license=license_text,
        )

    async def close(self) -> None:
        await self._client.aclose()

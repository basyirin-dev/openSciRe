# SPDX-License-Identifier: Apache-2.0

"""PubMed E-utilities bridge — search, fetch summaries/details, PMID↔DOI resolution."""

from __future__ import annotations

import asyncio
import time
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from openscire.exceptions import ReferenceError
from openscire.logging import get_logger
from openscire.references.mesh import extract_mesh_from_efetch_root
from openscire.references.models import (
    PubMedSearchResult,
    ReferenceAuthor,
    ReferenceItem,
    ReferenceSource,
)

logger = get_logger("openscire.references.bridges.pubmed")

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ESEARCH_URL = f"{EUTILS_BASE}/esearch.fcgi"
EFETCH_URL = f"{EUTILS_BASE}/efetch.fcgi"
ESUMMARY_URL = f"{EUTILS_BASE}/esummary.fcgi"
ELINK_URL = f"{EUTILS_BASE}/elink.fcgi"


class NCBIRateLimiter:
    """Simple asyncio-based rate limiter for NCBI E-utilities.

    NCBI requires max 3 requests/second without an API key,
    or 10 requests/second with a valid API key.
    """

    def __init__(self, api_key: str = "") -> None:
        # 0.34s = ~3/s, 0.1s = 10/s
        self._delay = 0.34 if not api_key else 0.1
        self._last = 0.0

    async def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        if elapsed < self._delay:
            await asyncio.sleep(self._delay - elapsed)
        self._last = time.monotonic()


class PubMedBridge:
    """Bridge to the NCBI PubMed E-utilities API.

    Provides search (esearch), summary (esummary), detail (efetch),
    and bidirectional PMID↔DOI resolution.

    PubMed is a search database, not a collection-based reference manager.
    This bridge intentionally does not extend ReferenceBridge.
    """

    def __init__(
        self,
        api_key: str = "",
        email: str = "",
        tool: str = "openscire",
        timeout: int = 30,
    ) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )
        self._api_key = api_key
        self._email = email
        self._tool = tool
        self._rate_limiter = NCBIRateLimiter(api_key)

    def _params(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        p: dict[str, str] = {"tool": self._tool}
        if self._email:
            p["email"] = self._email
        if self._api_key:
            p["api_key"] = self._api_key
        if extra:
            p.update(extra)
        return p

    async def _get(self, url: str, params: dict[str, str]) -> httpx.Response:
        await self._rate_limiter.wait()
        response = await self._client.get(url, params=params)
        if response.status_code != 200:
            raise ReferenceError(
                f"E-utilities request failed ({response.status_code}): {response.text[:200]}",
                source="pubmed",
            )
        return response

    async def search(
        self,
        query: str,
        max_results: int = 20,
        retstart: int = 0,
        db: str = "pubmed",
    ) -> PubMedSearchResult:
        """Search PubMed via esearch.fcgi.

        Args:
            query: PubMed search query (e.g., 'crispr[title] AND 2023[dp]').
            max_results: Maximum PMIDs to return (1-100000).
            retstart: Starting offset for pagination.
            db: Database to search ('pubmed' or 'pmc').

        Returns:
            PubMedSearchResult with PMIDs, total count, and history server keys.
        """
        params = self._params(
            {
                "db": db,
                "term": query,
                "retmax": str(max_results),
                "retstart": str(retstart),
                "retmode": "xml",
                "usehistory": "y",
            }
        )
        response = await self._get(ESEARCH_URL, params)
        root = ET.fromstring(response.content)

        id_list = root.findall(".//IdList/Id")
        pmids = [id_el.text for id_el in id_list if id_el.text]

        count_el = root.find(".//Count")
        total_count = int(count_el.text) if count_el is not None and count_el.text else 0

        webenv_el = root.find(".//WebEnv")
        webenv = webenv_el.text or "" if webenv_el is not None else ""

        qk_el = root.find(".//QueryKey")
        query_key = qk_el.text or "" if qk_el is not None else ""

        return PubMedSearchResult(
            pmids=pmids,
            total_count=total_count,
            webenv=webenv,
            query_key=query_key,
            retstart=retstart,
        )

    async def fetch_summary(
        self, pmids: str | list[str]
    ) -> list[ReferenceItem]:
        """Fetch document summaries via esummary.fcgi (fast, lightweight).

        Uses JSON format. Returns ReferenceItems with core metadata.
        MeSH terms are NOT included in summaries — use fetch_detail for those.
        """
        if isinstance(pmids, str):
            pmids = [pmids]
        if not pmids:
            return []

        params = self._params(
            {
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "json",
            }
        )
        response = await self._get(ESUMMARY_URL, params)
        data: dict[str, Any] = response.json()

        result = data.get("result", {})
        uids = result.get("uids", [])

        items: list[ReferenceItem] = []
        for uid in uids:
            entry = result.get(str(uid), {})
            item = self._parse_summary(uid, entry)
            if item is not None:
                items.append(item)
        return items

    async def fetch_detail(
        self, pmids: str | list[str]
    ) -> list[ReferenceItem]:
        """Fetch full article metadata via efetch.fcgi with XML.

        Returns ReferenceItems with MeSH terms, publication types,
        full author list, and all identifiers.
        """
        if isinstance(pmids, str):
            pmids = [pmids]
        if not pmids:
            return []

        params = self._params(
            {
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "xml",
            }
        )
        response = await self._get(EFETCH_URL, params)
        return self._parse_efetch_xml(response.content)

    async def fetch_medline(self, pmids: str | list[str]) -> str:
        """Fetch raw MEDLINE-format records via efetch.fcgi.

        Args:
            pmids: One or more PMIDs.

        Returns:
            Raw MEDLINE tagged text (can be parsed by MedlineImporter).
        """
        if isinstance(pmids, str):
            pmids = [pmids]
        if not pmids:
            return ""

        params = self._params(
            {
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "text",
                "rettype": "medline",
            }
        )
        response = await self._get(EFETCH_URL, params)
        return response.text

    async def resolve_pmid_to_doi(self, pmid: str) -> str | None:
        """Resolve a PMID to its DOI.

        Uses three strategies in fallback order:
        1. efetch XML — <ArticleId IdType="doi">
        2. esummary JSON — elocationid field
        3. elink — cross-database linkout

        Args:
            pmid: PubMed identifier.

        Returns:
            DOI string, or None if not found.
        """
        # Strategy 1: efetch XML
        try:
            params = self._params({"db": "pubmed", "id": pmid, "retmode": "xml"})
            response = await self._get(EFETCH_URL, params)
            root = ET.fromstring(response.content)
            for aid in root.iter("ArticleId"):
                if aid.get("IdType") == "doi" and aid.text:
                    return aid.text.strip()
        except Exception:
            pass

        # Strategy 2: esummary JSON
        try:
            params = self._params({"db": "pubmed", "id": pmid, "retmode": "json"})
            response = await self._get(ESUMMARY_URL, params)
            data: dict[str, Any] = response.json()
            entry: dict[str, Any] = data.get("result", {}).get(pmid, {})
            elocationid: str = entry.get("elocationid", "")
            if elocationid and "doi" in elocationid.lower():
                return elocationid.replace("doi: ", "").replace("doi:", "").strip()
        except Exception:
            pass

        # Strategy 3: elink
        try:
            params = self._params(
                {"dbfrom": "pubmed", "db": "doi", "id": pmid, "retmode": "xml"}
            )
            response = await self._get(ELINK_URL, params)
            root = ET.fromstring(response.content)
            for link in root.iter("Link"):
                id_el = link.find("Id")
                if id_el is not None and id_el.text:
                    return id_el.text.strip()
        except Exception:
            pass

        return None

    async def resolve_doi_to_pmid(self, doi: str) -> str | None:
        """Resolve a DOI to a PubMed ID (PMID).

        Searches PubMed with the DOI as query.

        Args:
            doi: Digital Object Identifier.

        Returns:
            PMID string, or None if not found.
        """
        try:
            result = await self.search(f"{doi}[doi]", max_results=1)
            if result.pmids:
                return result.pmids[0]
        except Exception:
            pass
        return None

    async def close(self) -> None:
        await self._client.aclose()

    def _parse_summary(self, uid: str, entry: dict[str, Any]) -> ReferenceItem | None:  # noqa: PLR0912
        """Parse an esummary JSON entry into a ReferenceItem."""
        title = entry.get("title", "") or entry.get("source", "")
        if isinstance(title, list):
            title = " ".join(title)

        authors: list[ReferenceAuthor] = []
        for a in entry.get("authors", []):
            if isinstance(a, dict):
                name = a.get("name", "")
                if name:
                    parts = name.split()
                    if len(parts) >= 2:
                        authors.append(
                            ReferenceAuthor(last=parts[0].rstrip(","), first=" ".join(parts[1:]))
                        )
                    else:
                        authors.append(ReferenceAuthor(full=name))

        doi = ""
        elocationid = entry.get("elocationid", "")
        if elocationid and "doi" in elocationid.lower():
            doi = elocationid.replace("doi: ", "").replace("doi:", "").strip()

        pages = entry.get("pages", "")
        volume = entry.get("volume", "")
        issue = entry.get("issue", "")
        journal = entry.get("source", "") or entry.get("fulljournalname", "")
        year = entry.get("pubdate", "")
        year_num = None
        if year:
            import re as _re
            m = _re.match(r"(\d{4})", str(year))
            if m:
                year_num = int(m.group(1))

        return ReferenceItem(
            id=uid,
            source=ReferenceSource.pubmed,
            doi=doi,
            title=str(title),
            authors=authors,
            journal=str(journal),
            year=year_num,
            volume=str(volume),
            issue=str(issue),
            pages=str(pages),
            url=f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
            item_type="journal_article",
            extra={"pmid": uid},
        )

    @staticmethod
    def _parse_efetch_xml(xml_data: bytes | str) -> list[ReferenceItem]:  # noqa: PLR0912, C901
        """Parse PubMed efetch XML into ReferenceItems."""
        if isinstance(xml_data, bytes):
            xml_data = xml_data.decode("utf-8", errors="replace")
        root = ET.fromstring(xml_data)

        items: list[ReferenceItem] = []
        for article in root.iter("PubmedArticle"):
            try:
                item = _parse_one_article(article)
                if item is not None:
                    items.append(item)
            except Exception as exc:
                logger.warning("Failed to parse PubMed article: %s", exc)
        return items


def _parse_one_article(article: ET.Element) -> ReferenceItem | None:  # noqa: C901, PLR0912
    """Parse a single PubmedArticle element into a ReferenceItem."""
    medline = article.find(".//MedlineCitation")
    if medline is None:
        return None

    pmid_el = medline.find("PMID")
    pmid = pmid_el.text or "" if pmid_el is not None else ""

    article_el = medline.find("Article")
    if article_el is None:
        return None

    title_el = article_el.find("ArticleTitle")
    title = "".join(title_el.itertext()) if title_el is not None else ""

    abstract_el = article_el.find("Abstract")
    abstract = ""
    if abstract_el is not None:
        parts = [ "".join(at.itertext()) for at in abstract_el.findall("AbstractText") ]
        abstract = " ".join(parts)

    authors: list[ReferenceAuthor] = []
    author_list = article_el.find("AuthorList")
    if author_list is not None:
        for au in author_list.findall("Author"):
            last_el = au.find("LastName")
            first_el = au.find("ForeName")
            if last_el is not None:
                authors.append(
                    ReferenceAuthor(
                        last=last_el.text or "",
                        first=first_el.text or "" if first_el is not None else "",
                    )
                )

    journal_el = article_el.find("Journal")
    journal = ""
    volume = ""
    issue = ""
    year_num = None
    pages_str = ""
    if journal_el is not None:
        title_el = journal_el.find("Title")
        if title_el is not None:
            journal = title_el.text or ""
        vol_el = journal_el.find("JournalIssue/Volume")
        if vol_el is not None:
            volume = vol_el.text or ""
        issue_el = journal_el.find("JournalIssue/Issue")
        if issue_el is not None:
            issue = issue_el.text or ""
        pub_date = journal_el.find("JournalIssue/PubDate")
        if pub_date is not None:
            year_el = pub_date.find("Year")
            if year_el is not None and year_el.text:
                year_num = int(year_el.text)

    pagination = article_el.find("Pagination/MedlinePgn")
    if pagination is not None:
        pages_str = pagination.text or ""

    doi = ""
    article_ids = article.find(".//ArticleIdList")
    if article_ids is not None:
        for aid in article_ids.findall("ArticleId"):
            if aid.get("IdType") == "doi" and aid.text:
                doi = aid.text.strip()
                break

    mesh_terms = extract_mesh_from_efetch_root(medline)

    pub_types: list[str] = []
    pt_list = article_el.find("PublicationTypeList")
    if pt_list is not None:
        pub_types = [pt.text for pt in pt_list.findall("PublicationType") if pt.text]

    language_el = medline.find("Language")
    language = language_el.text if language_el is not None else ""

    keywords: list[str] = []
    keyword_list = medline.find("KeywordList")
    if keyword_list is not None:
        keywords = [kw.text for kw in keyword_list.findall("Keyword") if kw.text]

    extra: dict[str, object] = {}
    if mesh_terms:
        extra["mesh_terms"] = [m.model_dump() for m in mesh_terms]
    if pub_types:
        extra["publication_types"] = pub_types
    if language:
        extra["language"] = language
    if pmid:
        extra["pmid"] = pmid

    return ReferenceItem(
        id=pmid,
        source=ReferenceSource.pubmed,
        doi=doi,
        title=title,
        authors=authors,
        journal=journal,
        year=year_num,
        volume=volume,
        issue=issue,
        pages=pages_str,
        abstract=abstract,
        keywords=keywords + [m.descriptor for m in mesh_terms],
        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
        item_type="journal_article",
        extra=extra,
    )

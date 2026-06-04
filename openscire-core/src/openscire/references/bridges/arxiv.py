# SPDX-License-Identifier: Apache-2.0

"""arXiv API v2 client — search, fetch, full-text source, and DOI resolution."""

from __future__ import annotations

import asyncio
import gzip
import io
import re
import tarfile
import time
import xml.etree.ElementTree as ET

import httpx

from openscire.exceptions import ReferenceError
from openscire.logging import get_logger
from openscire.references.models import (
    ArXivSearchResult,
    ReferenceAuthor,
    ReferenceItem,
    ReferenceSource,
)

logger = get_logger("openscire.references.bridges.arxiv")

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ARXIV_SOURCE_URL = "https://arxiv.org/e-print"

ARXIV_CATEGORIES: dict[str, str] = {
    "cs.AI": "Artificial Intelligence",
    "cs.AR": "Hardware Architecture",
    "cs.CC": "Computational Complexity",
    "cs.CE": "Computational Engineering, Finance, and Science",
    "cs.CL": "Computation and Language",
    "cs.CR": "Cryptography and Security",
    "cs.CV": "Computer Vision and Pattern Recognition",
    "cs.CY": "Computers and Society",
    "cs.DB": "Databases",
    "cs.DC": "Distributed, Parallel, and Cluster Computing",
    "cs.DS": "Data Structures and Algorithms",
    "cs.IR": "Information Retrieval",
    "cs.IT": "Information Theory",
    "cs.LG": "Machine Learning",
    "cs.NE": "Neural and Evolutionary Computing",
    "cs.RO": "Robotics",
    "cs.SE": "Software Engineering",
    "cs.SI": "Social and Information Networks",
    "math.OC": "Optimization and Control",
    "math.ST": "Statistics Theory",
    "physics.bio-ph": "Biological Physics",
    "q-bio.BM": "Biomolecules",
    "q-bio.GN": "Genomics",
    "q-bio.QM": "Quantitative Methods",
    "q-fin.CP": "Computational Finance",
    "q-fin.ST": "Statistical Finance",
    "stat.AP": "Applications",
    "stat.CO": "Computation",
    "stat.ME": "Methodology",
    "stat.ML": "Machine Learning (Statistics)",
}

ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS = "http://arxiv.org/schemas/atom"
OPENSEARCH_NS = "http://a9.com/-/spec/opensearch/1.1/"

SORT_OPTIONS = {"relevance", "lastUpdatedDate", "submittedDate"}


def is_valid_arxiv_category(category: str) -> bool:
    """Check if a category string is a known arXiv category."""
    return category in ARXIV_CATEGORIES or bool(
        re.match(r"^[a-z-]+(\.[A-Za-z-]+)?$", category)
    )


def arxiv_category_name(category: str) -> str:
    """Return the human-readable name for an arXiv category, or the category itself."""
    return ARXIV_CATEGORIES.get(category, category)


class ArXivRateLimiter:
    """Simple asyncio-based rate limiter for arXiv API.

    arXiv recommends no more than 1 request per 3 seconds.
    """

    def __init__(self, min_interval: float = 3.5) -> None:
        self._delay = min_interval
        self._last = 0.0

    async def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        if elapsed < self._delay:
            await asyncio.sleep(self._delay - elapsed)
        self._last = time.monotonic()


class ArXivClient:
    """Client for the arXiv API (OAI-PMH / Atom interface).

    Provides search, multi-ID fetch, LaTeX source retrieval,
    and arXiv↔DOI resolution.

    arXiv is a preprint repository, not a collection-based reference manager.
    This bridge intentionally does not extend ReferenceBridge.
    """

    def __init__(
        self,
        email: str = "",
        tool: str = "openscire",
        timeout: int = 30,
    ) -> None:
        user_agent = f"{tool}/0.1"
        if email:
            user_agent += f" (mailto:{email})"
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            headers={"User-Agent": user_agent},
        )
        self._email = email
        self._tool = tool
        self._rate_limiter = ArXivRateLimiter()

    async def search(
        self,
        search_query: str,
        max_results: int = 10,
        start: int = 0,
        sort_by: str = "relevance",
        sort_order: str = "descending",
    ) -> ArXivSearchResult:
        """Search arXiv articles via the query API.

        Args:
            search_query: arXiv search query syntax
                (e.g., 'au:smith AND ti:transformer', 'cat:cs.LG', 'all:deep learning').
            max_results: Maximum results to return.
            start: Starting offset for pagination.
            sort_by: Sort field ('relevance', 'lastUpdatedDate', 'submittedDate').
            sort_order: Sort direction ('ascending', 'descending').

        Returns:
            ArXivSearchResult with IDs and metadata.
        """
        if sort_by not in SORT_OPTIONS:
            sort_by = "relevance"
        if sort_order not in ("ascending", "descending"):
            sort_order = "descending"

        params: dict[str, str | int] = {
            "search_query": search_query,
            "max_results": max_results,
            "start": start,
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }
        root = await self._fetch_feed(params)
        items = self._parse_atom_response(root)
        total_count = self._parse_total_results(root)
        arxiv_ids = [i.id for i in items]
        return ArXivSearchResult(
            arxiv_ids=arxiv_ids,
            total_count=total_count,
            start=start,
        )

    async def fetch_by_id(
        self, arxiv_ids: str | list[str]
    ) -> list[ReferenceItem]:
        """Fetch papers by their arXiv IDs.

        Uses the id_list parameter for efficient batch retrieval.

        Args:
            arxiv_ids: Single arXiv ID string or list of IDs.

        Returns:
            List of ReferenceItems.
        """
        if isinstance(arxiv_ids, str):
            arxiv_ids = [arxiv_ids]
        if not arxiv_ids:
            return []

        params: dict[str, str | int] = {
            "id_list": ",".join(arxiv_ids),
            "max_results": len(arxiv_ids),
        }
        root = await self._fetch_feed(params)
        return self._parse_atom_response(root)

    async def search_by_category(
        self,
        category: str,
        max_results: int = 10,
        start: int = 0,
        sort_by: str = "submittedDate",
    ) -> ArXivSearchResult:
        """Search arXiv papers in a specific category."""
        return await self.search(
            search_query=f"cat:{category}",
            max_results=max_results,
            start=start,
            sort_by=sort_by,
        )

    async def search_by_author(
        self,
        author: str,
        max_results: int = 10,
        start: int = 0,
    ) -> ArXivSearchResult:
        """Search arXiv papers by author."""
        return await self.search(
            search_query=f'au:"{author}"',
            max_results=max_results,
            start=start,
        )

    async def search_by_date_range(
        self,
        start_date: str,
        end_date: str,
        search_query: str = "",
        max_results: int = 100,
        start: int = 0,
    ) -> ArXivSearchResult:
        """Search arXiv papers within a date range (submittedDate).

        Args:
            start_date: ISO date string (e.g., '2024-01-01').
            end_date: ISO date string (e.g., '2024-12-31').
            search_query: Optional additional query to combine with date filter.
            max_results: Maximum results.
            start: Pagination offset.

        Returns:
            ArXivSearchResult.
        """
        date_query = f"submittedDate:[{start_date} TO {end_date}]"
        if search_query:
            date_query = f"({search_query}) AND {date_query}"
        return await self.search(
            search_query=date_query,
            max_results=max_results,
            start=start,
            sort_by="submittedDate",
        )

    async def search_all(
        self, search_query: str, max_results: int = 1000
    ) -> list[ReferenceItem]:
        """Paginate through all search results.

        Fetches in chunks of 100 to stay within arXiv rate limits.

        Args:
            search_query: arXiv search query.
            max_results: Maximum results to return (capped at 30000 by arXiv).

        Returns:
            Full list of ReferenceItems.
        """
        chunk_size = 100
        all_items: list[ReferenceItem] = []
        start = 0
        while start < max_results:
            result = await self.search(
                search_query=search_query,
                max_results=chunk_size,
                start=start,
            )
            if not result.arxiv_ids:
                break
            batch = await self.fetch_by_id(result.arxiv_ids)
            all_items.extend(batch)
            start += chunk_size
            if len(batch) < chunk_size:
                break
        return all_items[:max_results]

    async def fetch_multiple(
        self, arxiv_ids: list[str]
    ) -> list[ReferenceItem]:
        """Fetch multiple papers by IDs, splitting into batches of 50."""
        if not arxiv_ids:
            return []
        all_items: list[ReferenceItem] = []
        for i in range(0, len(arxiv_ids), 50):
            batch = arxiv_ids[i : i + 50]
            items = await self.fetch_by_id(batch)
            all_items.extend(items)
        return all_items

    async def fetch_source(self, arxiv_id: str) -> bytes:
        """Download the LaTeX/PDF source for an arXiv paper.

        Args:
            arxiv_id: arXiv paper ID (e.g., '2401.12345' or '1234.56789').

        Returns:
            Raw bytes of the source (may be tar.gz, gz, or plain text).

        Raises:
            ReferenceError: If the source cannot be retrieved.
        """
        url = f"{ARXIV_SOURCE_URL}/{arxiv_id}"
        await self._rate_limiter.wait()
        response = await self._client.get(url)
        if response.status_code != 200:
            raise ReferenceError(
                f"arXiv source download failed ({response.status_code}): {arxiv_id}",
                source="arxiv",
            )
        return response.content

    @staticmethod
    def extract_tex_files(source_bytes: bytes) -> list[tuple[str, str]]:
        """Extract .tex files from arXiv source archive.

        Handles tar.gz archives and single-file gzip/plain inputs.

        Args:
            source_bytes: Raw bytes from fetch_source().

        Returns:
            List of (filename, content) tuples for each .tex file.
        """
        tex_files: list[tuple[str, str]] = []

        # Try tar.gz
        try:
            with tarfile.open(fileobj=io.BytesIO(source_bytes), mode="r:*") as tar:
                for member in tar.getmembers():
                    if member.isfile() and member.name.endswith(".tex"):
                        f = tar.extractfile(member)
                        if f is not None:
                            content = f.read().decode("utf-8", errors="replace")
                            tex_files.append((member.name, content))
                if tex_files:
                    return tex_files
        except (tarfile.TarError, OSError):
            pass

        # Try single gzip file
        try:
            decompressed = gzip.decompress(source_bytes)
            text = decompressed.decode("utf-8", errors="replace")
            return [("main.tex", text)]
        except (gzip.BadGzipFile, OSError):
            pass

        # Plain text fallback
        try:
            text = source_bytes.decode("utf-8", errors="replace")
            return [("main.tex", text)]
        except UnicodeDecodeError:
            return []

    async def resolve_arxiv_to_doi(self, arxiv_id: str) -> str | None:
        """Resolve an arXiv ID to its DOI (when available).

        Fetches the paper metadata and extracts the DOI from the Atom feed.

        Args:
            arxiv_id: arXiv paper ID.

        Returns:
            DOI string, or None if not found.
        """
        items = await self.fetch_by_id(arxiv_id)
        if items:
            doi = items[0].doi
            return doi if doi else None
        return None

    async def resolve_doi_to_arxiv(self, doi: str) -> str | None:
        """Resolve a DOI to an arXiv ID.

        Searches arXiv using the DOI.

        Args:
            doi: Digital Object Identifier.

        Returns:
            arXiv ID, or None if not found.
        """
        try:
            result = await self.search(f"doi:{doi}", max_results=1)
            if result.arxiv_ids:
                return result.arxiv_ids[0]
        except Exception:
            pass
        return None

    async def close(self) -> None:
        await self._client.aclose()

    async def _fetch_feed(self, params: dict[str, str | int]) -> ET.Element:
        """Fetch and parse the Atom feed from the arXiv API."""
        str_params: dict[str, str] = {k: str(v) for k, v in params.items()}
        await self._rate_limiter.wait()
        response = await self._client.get(ARXIV_API_URL, params=str_params)
        if response.status_code != 200:
            raise ReferenceError(
                f"arXiv API request failed ({response.status_code}): {response.text[:200]}",
                source="arxiv",
            )
        return ET.fromstring(response.content)

    @staticmethod
    def _parse_total_results(root: ET.Element) -> int:
        """Extract total result count from the Atom feed."""
        total_el = root.find(f"{{{OPENSEARCH_NS}}}totalResults")
        if total_el is not None and total_el.text and total_el.text.isdigit():
            return int(total_el.text)
        return 0

    @staticmethod
    def _parse_atom_response(root: ET.Element) -> list[ReferenceItem]:
        """Parse arXiv Atom feed into ReferenceItems."""
        items: list[ReferenceItem] = []
        for entry in root.findall(f"{{{ATOM_NS}}}entry"):
            try:
                item = _parse_one_entry(entry)
                if item is not None:
                    items.append(item)
            except Exception as exc:
                logger.warning("Failed to parse arXiv entry: %s", exc)
        return items


def _parse_one_entry(entry: ET.Element) -> ReferenceItem | None:  # noqa: C901, PLR0912
    """Parse a single Atom <entry> into a ReferenceItem."""
    id_el = entry.find(f"{{{ATOM_NS}}}id")
    if id_el is None or not id_el.text:
        return None

    full_id = id_el.text.strip()
    arxiv_id = full_id.replace("http://arxiv.org/abs/", "").replace("https://arxiv.org/abs/", "")

    title_el = entry.find(f"{{{ATOM_NS}}}title")
    title = ""
    if title_el is not None and title_el.text:
        title = title_el.text.strip()
        # arXiv wraps titles in newlines
        title = " ".join(title.split())

    summary_el = entry.find(f"{{{ATOM_NS}}}summary")
    abstract = ""
    if summary_el is not None and summary_el.text:
        abstract = summary_el.text.strip()

    authors: list[ReferenceAuthor] = []
    for author_el in entry.findall(f"{{{ATOM_NS}}}author"):
        name_el = author_el.find(f"{{{ATOM_NS}}}name")
        if name_el is not None and name_el.text:
            full_name = name_el.text.strip()
            parts = full_name.rsplit(" ", 1)
            if len(parts) == 2:
                authors.append(ReferenceAuthor(first=parts[0], last=parts[1], full=full_name))
            else:
                authors.append(ReferenceAuthor(full=full_name))

    published_el = entry.find(f"{{{ATOM_NS}}}published")
    year: int | None = None
    if published_el is not None and published_el.text:
        m = re.match(r"(\d{4})", published_el.text.strip())
        if m:
            year = int(m.group(1))

    doi = ""
    doi_el = entry.find(f"{{{ARXIV_NS}}}doi")
    if doi_el is not None and doi_el.text:
        doi = doi_el.text.strip()

    categories: list[str] = []
    for cat in entry.findall(f"{{{ATOM_NS}}}category"):
        term = cat.get("term", "")
        if term:
            categories.append(term)

    primary_cat = ""
    primary_el = entry.find(f"{{{ARXIV_NS}}}primary_category")
    if primary_el is not None:
        primary_cat = primary_el.get("term", "")

    comment = ""
    comment_el = entry.find(f"{{{ARXIV_NS}}}comment")
    if comment_el is not None and comment_el.text:
        comment = comment_el.text.strip()

    journal_ref = ""
    journal_el = entry.find(f"{{{ARXIV_NS}}}journal_ref")
    if journal_el is not None and journal_el.text:
        journal_ref = journal_el.text.strip()

    url = f"https://arxiv.org/abs/{arxiv_id}"

    extra: dict[str, object] = {}
    if categories:
        extra["categories"] = categories
    if primary_cat:
        extra["primary_category"] = primary_cat
    if comment:
        extra["comment"] = comment
    if journal_ref:
        extra["journal_ref"] = journal_ref

    return ReferenceItem(
        id=arxiv_id,
        source=ReferenceSource.arxiv,
        doi=doi,
        title=title,
        authors=authors,
        year=year,
        journal=journal_ref,
        abstract=abstract,
        keywords=categories,
        url=url,
        item_type="article",
        extra=extra,
    )

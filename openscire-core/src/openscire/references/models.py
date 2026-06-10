# SPDX-License-Identifier: Apache-2.0

"""Unified data models for reference items, collections, and attachments."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ReferenceSource(StrEnum):
    zotero = "zotero"
    mendeley = "mendeley"
    pubmed = "pubmed"
    pmc = "pmc"
    arxiv = "arxiv"
    bibtex = "bibtex"
    ris = "ris"
    csl_json = "csl_json"
    endnote_xml = "endnote_xml"
    semantic_scholar = "semantic_scholar"
    openalex = "openalex"
    scielo = "scielo"


class DedupMatchMethod(StrEnum):
    doi_exact = "doi_exact"
    title_fuzzy = "title_fuzzy"
    author_year = "author_year"


class ReferenceAuthor(BaseModel):
    first: str = ""
    last: str = ""
    full: str = ""
    affiliation: str = ""


class ReferenceAttachment(BaseModel):
    id: str
    filename: str
    content_type: str = ""
    size_bytes: int = 0
    url: str = ""


class ReferenceCollection(BaseModel):
    id: str
    name: str
    source: ReferenceSource
    parent_id: str = ""
    item_count: int = 0


class ReferenceItem(BaseModel):
    id: str
    source: ReferenceSource
    source_collection_id: str = ""
    doi: str = ""
    title: str = ""
    authors: list[ReferenceAuthor] = Field(default_factory=list)
    journal: str = ""
    year: int | None = None
    volume: str = ""
    issue: str = ""
    pages: str = ""
    publisher: str = ""
    original_language: str = ""
    retraction_status: str = ""
    abstract: str = ""
    keywords: list[str] = Field(default_factory=list)
    url: str = ""
    attachments: list[ReferenceAttachment] = Field(default_factory=list)
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    date_added: datetime | None = None
    date_modified: datetime | None = None
    item_type: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class MeshTerm(BaseModel):
    descriptor: str = ""
    qualifier: str = ""
    ui: str = ""


class ArticleSection(BaseModel):
    heading: str = ""
    body: str = ""


class ArticleFigure(BaseModel):
    id: str = ""
    caption: str = ""
    label: str = ""


class FullTextArticle(BaseModel):
    pmid: str = ""
    pmcid: str = ""
    doi: str = ""
    title: str = ""
    authors: list[ReferenceAuthor] = Field(default_factory=list)
    journal: str = ""
    year: int | None = None
    volume: str = ""
    issue: str = ""
    pages: str = ""
    abstract: str = ""
    sections: list[ArticleSection] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    mesh_terms: list[MeshTerm] = Field(default_factory=list)
    figures: list[ArticleFigure] = Field(default_factory=list)
    raw_text: str = ""
    license: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class DedupResult(BaseModel):
    item: ReferenceItem
    duplicate_of: ReferenceItem | None = None
    confidence: float = 0.0
    match_method: DedupMatchMethod | None = None


class SyncState(BaseModel):
    source: ReferenceSource
    bridge_id: str
    last_sync: datetime | None = None
    last_version: int = 0
    sync_token: str = ""


class PubMedSearchResult(BaseModel):
    pmids: list[str] = Field(default_factory=list)
    total_count: int = 0
    webenv: str = ""
    query_key: str = ""
    retstart: int = 0


class ArXivSearchResult(BaseModel):
    arxiv_ids: list[str] = Field(default_factory=list)
    total_count: int = 0
    start: int = 0


class SemanticScholarSearchResult(BaseModel):
    paper_ids: list[str] = Field(default_factory=list)
    total_count: int = 0
    offset: int = 0
    next_offset: int | None = None


class CitationGraphEntry(BaseModel):
    citing_paper: ReferenceItem | None = None
    cited_paper: ReferenceItem | None = None
    contexts: list[str] = Field(default_factory=list)
    is_influential: bool = False


class PaperRecommendation(BaseModel):
    paper_id: str
    score: float = 0.0


class OpenAlexSearchResult(BaseModel):
    work_ids: list[str] = Field(default_factory=list)
    total_count: int = 0
    page: int = 1
    per_page: int = 25


class OALocation(BaseModel):
    """A single OA location from Unpaywall."""

    url_for_pdf: str | None = None
    url_for_landing_page: str = ""
    url: str = ""
    host_type: str = ""
    is_best: bool = False
    license: str | None = None
    version: str = ""
    oa_date: str | None = None
    repository_institution: str | None = None
    endpoint_id: str | None = None
    pmh_id: str | None = None


class UnpaywallResult(BaseModel):
    """Result of an Unpaywall DOI resolution for OA status and locations."""

    doi: str = ""
    doi_url: str = ""
    title: str = ""
    genre: str = ""
    is_oa: bool = False
    oa_status: str = ""
    has_repository_copy: bool = False
    best_oa_location: OALocation | None = None
    first_oa_location: OALocation | None = None
    oa_locations: list[OALocation] = Field(default_factory=list)
    journal_name: str = ""
    journal_issns: str = ""
    journal_issn_l: str = ""
    journal_is_oa: bool = False
    journal_is_in_doaj: bool = False
    publisher: str = ""
    published_date: str = ""
    year: int | None = None
    pdf_url: str = ""
    data_standard: int = 2
    updated: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)

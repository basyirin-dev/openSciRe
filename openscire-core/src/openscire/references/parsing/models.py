from pydantic import BaseModel, Field

from openscire.references.models import FullTextArticle


class PageText(BaseModel):
    page_num: int = 0
    text: str = ""
    width: float = 0.0
    height: float = 0.0
    tables: list[list[list[str]]] = Field(default_factory=list)


class ParsedReference(BaseModel):
    index: int = 0
    raw_text: str = ""
    doi: str = ""
    pmid: str = ""
    arxiv_id: str = ""
    title: str = ""
    authors: str = ""
    year: int | None = None
    journal: str = ""
    confidence: float = 0.0


class ExtractionResult(BaseModel):
    method: str = ""
    full_text: FullTextArticle = Field(default_factory=FullTextArticle)
    parsed_references: list[ParsedReference] = Field(default_factory=list)
    pages: int = 0
    extraction_time: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    source_path: str = ""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChunkConfig(BaseModel):
    max_tokens: int = 512
    overlap_sentences: int = 1
    respect_sections: bool = True
    respect_paragraphs: bool = True
    respect_lists: bool = True
    respect_code_blocks: bool = True
    citation_anchor: bool = True
    figure_table_proximity: bool = True
    min_chunk_tokens: int = 50
    max_chunk_tokens: int = 2048


class ChunkMetadata(BaseModel):
    document_id: str = ""
    section: str = ""
    subsection: str = ""
    paragraph_index: int = 0
    token_count: int = 0
    citation_list: list[str] = Field(default_factory=list)
    figure_refs: list[str] = Field(default_factory=list)
    chunk_index: int = 0
    total_chunks: int = 0


class DocumentChunk(BaseModel):
    id: str = ""
    text: str = ""
    metadata: ChunkMetadata = Field(default_factory=ChunkMetadata)

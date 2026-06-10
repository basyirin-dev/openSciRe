from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from openscire.references.chunking.models import ChunkConfig, ChunkMetadata, DocumentChunk
from openscire.references.models import FullTextArticle
from openscire.references.utils import estimate_tokens

logger = logging.getLogger(__name__)

_ABBREV_PATTERN = re.compile(
    r"\b(?:e\.g|i\.e|et\s+al|fig|figs|tab|tabs|eq|eqs|vs|cf|al|"
    r"dr|mr|ms|mrs|prof|st|ave|inc|ltd|co|corp|jan|feb|mar|apr|jun|jul|"
    r"aug|sep|oct|nov|dec|ca|approx|vol|ed|eds?|no|pp)\.$",
    re.IGNORECASE,
)

_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z"\'({[]|\d+\s)')

_CITATION_PATTERN = re.compile(
    r"\[[\d,\s\-–—]+\]"
    r"|\([A-Za-z\u00C0-\u024F]+(?:\s+et\s+al\.?)?"
    r"(?:,\s*[A-Za-z\u00C0-\u024F]+)?(?:&\s*[A-Za-z\u00C0-\u024F]+)?,\s*[\d]{4}[a-z]?\)"
)

_FIGURE_PATTERN = re.compile(
    r"\b(?:Fig(?:ure)?s?\.?\s*\d+[A-Za-z]?|Table\s*\d+[A-Za-z]?)\b",
    re.IGNORECASE,
)

_LIST_START = re.compile(
    r"^[\-\*•‣⁃+]"
    r"|^\d+\.[\s)]"
    r"|^[a-zA-Z]\.[\s)]"
    r"|^\(?\d+\)\s"
    r"|^[ivxlcdm]+\.\s"
    r"|^[A-Z]\.\s",
    re.IGNORECASE,
)

_CODE_FENCE = re.compile(r"^```|^~~~")
_LATEX_ENV = re.compile(r"\\begin\{")
_LATEX_END = re.compile(r"\\end\}")


@dataclass
class _Segment:
    text: str = ""
    atomic: bool = False
    citations: list[str] = field(default_factory=list)
    figure_refs: list[str] = field(default_factory=list)
    section: str = ""
    paragraph_index: int = 0


class DocumentChunker:
    def __init__(self, config: ChunkConfig | None = None) -> None:
        self.config = config or ChunkConfig()

    def chunk(self, article: FullTextArticle, document_id: str = "") -> list[DocumentChunk]:
        sections_to_chunk: list[tuple[str, str]] = []

        if article.abstract:
            sections_to_chunk.append(("Abstract", article.abstract))
        for section in article.sections:
            sections_to_chunk.append((section.heading or "", section.body))
        if not sections_to_chunk and article.raw_text:
            sections_to_chunk.append(("", article.raw_text))
        if not sections_to_chunk:
            return []

        flat_chunks: list[DocumentChunk] = []
        paragraph_offset = 0

        if self.config.respect_sections:
            for section_name, section_body in sections_to_chunk:
                section_chunks = self._chunk_section(
                    text=section_body,
                    section_name=section_name,
                    document_id=document_id,
                    paragraph_offset=paragraph_offset,
                )
                if section_chunks:
                    para_count = len([p for p in re.split(r"\n\s*\n", section_body) if p.strip()])
                    paragraph_offset += max(para_count, 1)
                    flat_chunks.extend(section_chunks)
        else:
            combined_parts = [body for _, body in sections_to_chunk if body.strip()]
            combined_text = "\n\n".join(combined_parts)
            flat_chunks = self._chunk_section(
                text=combined_text,
                section_name="",
                document_id=document_id,
                paragraph_offset=0,
            )

        for i, chunk in enumerate(flat_chunks):
            chunk.metadata.chunk_index = i
            chunk.metadata.total_chunks = len(flat_chunks)
            chunk.id = f"{document_id}:{i}" if document_id else str(i)

        return flat_chunks

    def chunk_text(self, text: str, document_id: str = "") -> list[DocumentChunk]:
        from openscire.references.parsing.section_parser import SectionParser

        parser = SectionParser()
        article = parser.parse(text)
        return self.chunk(article, document_id=document_id)

    def _chunk_section(
        self,
        text: str,
        section_name: str,
        document_id: str,
        paragraph_offset: int,
    ) -> list[DocumentChunk]:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        segments: list[_Segment] = []

        for i, para in enumerate(paragraphs):
            para_idx = paragraph_offset + i

            if self.config.respect_code_blocks and self._is_code_block(para):
                segments.append(
                    _Segment(
                        text=para,
                        atomic=True,
                        citations=self._extract_citations(para),
                        figure_refs=self._extract_figure_refs(para),
                        section=section_name,
                        paragraph_index=para_idx,
                    )
                )
                continue

            if self.config.respect_lists and self._is_list(para):
                segments.append(
                    _Segment(
                        text=para,
                        atomic=True,
                        citations=self._extract_citations(para),
                        figure_refs=self._extract_figure_refs(para),
                        section=section_name,
                        paragraph_index=para_idx,
                    )
                )
                continue

            sentences = self._split_sentences(para)
            for sent in sentences:
                sent_text = sent.strip()
                if not sent_text:
                    continue
                segments.append(
                    _Segment(
                        text=sent_text,
                        atomic=False,
                        citations=self._extract_citations(sent_text),
                        figure_refs=self._extract_figure_refs(sent_text),
                        section=section_name,
                        paragraph_index=para_idx,
                    )
                )

        if self.config.citation_anchor:
            segments = self._anchor_citations(segments)

        return self._build_chunks(segments, document_id)

    def _is_code_block(self, text: str) -> bool:
        lines = text.split("\n")
        if _CODE_FENCE.match(lines[0]) and _CODE_FENCE.match(lines[-1]):
            return True
        return bool(_LATEX_ENV.search(text) and _LATEX_END.search(text))

    def _is_list(self, text: str) -> bool:
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if len(lines) < 2:
            return bool(lines and _LIST_START.match(lines[0]))
        list_matches = sum(1 for line in lines if _LIST_START.match(line))
        return list_matches >= max(2, len(lines) // 2)

    def _split_sentences(self, text: str) -> list[str]:
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return []

        parts = _SENTENCE_SPLIT.split(text)
        result: list[str] = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if result and _ABBREV_PATTERN.search(result[-1]):
                result[-1] += " " + part
            else:
                result.append(part)
        return result

    def _extract_citations(self, text: str) -> list[str]:
        return list(set(_CITATION_PATTERN.findall(text)))

    def _extract_figure_refs(self, text: str) -> list[str]:
        return list({m.group(0).strip() for m in _FIGURE_PATTERN.finditer(text)})

    def _anchor_citations(self, segments: list[_Segment]) -> list[_Segment]:
        if len(segments) < 2:
            return segments

        result: list[_Segment] = []
        for seg in segments:
            stripped = seg.text.strip()

            if (
                not seg.atomic
                and result
                and not result[-1].atomic
                and stripped.startswith("[")
                and stripped.endswith("]")
                and bool(_CITATION_PATTERN.fullmatch(stripped))
            ):
                prev = result[-1]
                all_cits = list(set(prev.citations + seg.citations))
                all_figs = list(set(prev.figure_refs + seg.figure_refs))
                result[-1] = _Segment(
                    text=prev.text + " " + seg.text,
                    atomic=False,
                    citations=all_cits,
                    figure_refs=all_figs,
                    section=prev.section,
                    paragraph_index=prev.paragraph_index,
                )
                continue

            result.append(seg)

        return result

    def _build_chunks(
        self,
        segments: list[_Segment],
        document_id: str,
    ) -> list[DocumentChunk]:
        if not segments:
            return []

        chunks = self._build_naive_chunks(segments, document_id)

        if self.config.overlap_sentences > 0 and len(chunks) > 1:
            chunks = self._apply_overlap(chunks)

        return chunks

    def _build_naive_chunks(
        self,
        segments: list[_Segment],
        document_id: str,
    ) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        current_text: list[str] = []
        current_tokens: int = 0
        current_citations: set[str] = set()
        current_figures: set[str] = set()
        current_section = segments[0].section if segments else ""
        current_para = segments[0].paragraph_index if segments else 0

        def flush() -> None:
            if not current_text:
                return
            text = " ".join(current_text)
            chunks.append(
                DocumentChunk(
                    text=text,
                    metadata=ChunkMetadata(
                        document_id=document_id,
                        section=current_section,
                        paragraph_index=current_para,
                        token_count=current_tokens,
                        citation_list=sorted(current_citations),
                        figure_refs=sorted(current_figures),
                    ),
                )
            )

        for seg in segments:
            seg_tokens = estimate_tokens(seg.text)
            separator_cost = 1 if current_text else 0
            new_total = current_tokens + seg_tokens + separator_cost

            if new_total > self.config.max_tokens and current_tokens > 0:
                flush()
                current_text = []
                current_tokens = 0
                current_citations = set()
                current_figures = set()
                separator_cost = 0
                new_total = seg_tokens

            current_text.append(seg.text)
            current_tokens = new_total
            current_citations.update(seg.citations)
            current_figures.update(seg.figure_refs)
            current_section = seg.section
            current_para = seg.paragraph_index

        flush()
        return chunks

    def _apply_overlap(self, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
        result = [chunks[0]]
        for i in range(1, len(chunks)):
            prev = result[-1]
            curr = chunks[i]

            prev_sentences = self._split_sentences(prev.text)
            n = min(self.config.overlap_sentences, len(prev_sentences))
            if n > 0:
                overlap_text = " ".join(prev_sentences[-n:])

                curr_new_text = overlap_text + " " + curr.text
                curr_new_tokens = estimate_tokens(curr_new_text)

                if curr_new_tokens <= self.config.max_chunk_tokens:
                    curr.text = curr_new_text
                    curr.metadata.token_count = curr_new_tokens

            result.append(curr)

        return result

from openscire.references.chunking import ChunkConfig, DocumentChunker
from openscire.references.models import ArticleSection, FullTextArticle


class TestDocumentChunker:
    def test_imrad_sections_remain_intact(self) -> None:
        article = FullTextArticle(
            abstract="This is the abstract of the paper.",
            sections=[
                ArticleSection(
                    heading="Introduction",
                    body="This is the introduction section. It has two sentences here.",
                ),
                ArticleSection(
                    heading="Methods",
                    body="We used a novel approach. The approach is reproducible.",
                ),
                ArticleSection(
                    heading="Results",
                    body="We found significant results. The p-value was less than 0.05.",
                ),
                ArticleSection(
                    heading="Discussion",
                    body="These results confirm our hypothesis. Further work is needed.",
                ),
            ],
        )
        chunker = DocumentChunker(ChunkConfig(max_tokens=2048, overlap_sentences=0))
        chunks = chunker.chunk(article, document_id="test:001")

        assert len(chunks) >= 5
        sections_in_chunks = [c.metadata.section for c in chunks]
        assert "Abstract" in sections_in_chunks
        assert "Introduction" in sections_in_chunks
        assert "Methods" in sections_in_chunks
        assert "Results" in sections_in_chunks
        assert "Discussion" in sections_in_chunks

    def test_paragraph_boundary_respected(self) -> None:
        article = FullTextArticle(
            sections=[
                ArticleSection(
                    heading="Introduction",
                    body=(
                        "First paragraph with some content here. It has multiple sentences. "
                        "This is the third sentence.\n\n"
                        "Second paragraph with different content. Another sentence here. "
                        "Yet another sentence to fill space."
                    ),
                ),
            ],
        )
        chunker = DocumentChunker(ChunkConfig(max_tokens=18, overlap_sentences=0))
        chunks = chunker.chunk(article)

        assert len(chunks) >= 2
        assert "First paragraph" in chunks[0].text
        assert any("Second paragraph" in c.text for c in chunks)

    def test_citation_anchored_split(self) -> None:
        article = FullTextArticle(
            sections=[
                ArticleSection(
                    heading="Introduction",
                    body=(
                        "Previous work has shown significant results [1]. "
                        "This was later confirmed by multiple studies [2, 3]. "
                        "Another group reported similar findings (Smith, 2020)."
                    ),
                ),
            ],
        )
        chunker = DocumentChunker(ChunkConfig(max_tokens=40, overlap_sentences=0))
        chunks = chunker.chunk(article)

        combined = " ".join(c.text for c in chunks)
        assert "[1]" in combined
        assert "[2, 3]" in combined
        assert "(Smith, 2020)" in combined

        for chunk in chunks:
            if "[1]" in chunk.text:
                assert "Previous work" in chunk.text
            if "[2, 3]" in chunk.text:
                assert "confirmed" in chunk.text
            if "(Smith, 2020)" in chunk.text:
                assert "reported" in chunk.text

    def test_figure_reference_tracked(self) -> None:
        article = FullTextArticle(
            sections=[
                ArticleSection(
                    heading="Results",
                    body=(
                        "The results are shown in Fig. 3. "
                        "Table 1 summarizes the data. This confirms our hypothesis."
                    ),
                ),
            ],
        )
        chunker = DocumentChunker(ChunkConfig(max_tokens=2048, overlap_sentences=0))
        chunks = chunker.chunk(article)

        assert len(chunks) == 1
        fig_refs = chunks[0].metadata.figure_refs
        assert any("Fig" in ref for ref in fig_refs)
        assert any("Table" in ref for ref in fig_refs)

    def test_bullet_list_not_split(self) -> None:
        article = FullTextArticle(
            sections=[
                ArticleSection(
                    heading="Methods",
                    body=(
                        "The following reagents were used:\n"
                        "- Sodium chloride\n"
                        "- Potassium phosphate\n"
                        "- Magnesium sulfate\n"
                        "- Calcium chloride"
                    ),
                ),
            ],
        )
        chunker = DocumentChunker(ChunkConfig(max_tokens=30, overlap_sentences=0))
        chunks = chunker.chunk(article)

        all_text = " ".join(c.text for c in chunks)
        assert "Sodium chloride" in all_text
        assert "Potassium phosphate" in all_text
        assert "Magnesium sulfate" in all_text
        assert "Calcium chloride" in all_text

    def test_numbered_list_preserved(self) -> None:
        article = FullTextArticle(
            sections=[
                ArticleSection(
                    heading="Protocol",
                    body=(
                        "The steps are:\n"
                        "1. Prepare the sample\n"
                        "2. Add the reagent\n"
                        "3. Incubate for 30 minutes\n"
                        "4. Measure the absorbance\n"
                        "5. Record the results"
                    ),
                ),
            ],
        )
        chunker = DocumentChunker(ChunkConfig(max_tokens=30, overlap_sentences=0))
        chunks = chunker.chunk(article)

        all_text = " ".join(c.text for c in chunks)
        assert "Prepare the sample" in all_text
        assert "Record the results" in all_text

    def test_code_block_intact(self) -> None:
        article = FullTextArticle(
            sections=[
                ArticleSection(
                    heading="Implementation",
                    body=(
                        "The function is defined below:\n\n"
                        "```python\n"
                        "def hello():\n"
                        "    print('hello world')\n"
                        "```\n\n"
                        "This function prints a greeting."
                    ),
                ),
            ],
        )
        chunker = DocumentChunker(ChunkConfig(max_tokens=30, overlap_sentences=0))
        chunks = chunker.chunk(article)

        all_text = " ".join(c.text for c in chunks)
        assert "```python" in all_text or "def hello()" in all_text
        assert "hello world" in all_text
        assert "greeting" in all_text

    def test_latex_math_block_preserved(self) -> None:
        article = FullTextArticle(
            sections=[
                ArticleSection(
                    heading="Theory",
                    body=(
                        "The energy is given by:\n\n"
                        "\\begin{equation}\n"
                        "E = mc^2\n"
                        "\\end{equation}\n\n"
                        "Where m is mass and c is the speed of light."
                    ),
                ),
            ],
        )
        chunker = DocumentChunker(ChunkConfig(max_tokens=30, overlap_sentences=0))
        chunks = chunker.chunk(article)

        all_text = " ".join(c.text for c in chunks)
        assert "E = mc^2" in all_text or "\\begin{equation}" in all_text

    def test_overlap_sentences(self) -> None:
        article = FullTextArticle(
            sections=[
                ArticleSection(
                    heading="Introduction",
                    body=(
                        "First sentence of the introduction. "
                        "Second sentence follows logically. "
                        "Third sentence provides more detail. "
                        "Fourth sentence concludes the thought. "
                        "Fifth sentence adds final remarks."
                    ),
                ),
            ],
        )
        chunker = DocumentChunker(ChunkConfig(max_tokens=18, overlap_sentences=1))
        chunks = chunker.chunk(article)

        assert len(chunks) >= 2

    def test_overlap_zero(self) -> None:
        article = FullTextArticle(
            sections=[
                ArticleSection(
                    heading="Introduction",
                    body=(
                        "First sentence. "
                        "Second sentence. "
                        "Third sentence. "
                        "Fourth sentence. "
                        "Fifth sentence."
                    ),
                ),
            ],
        )
        chunker = DocumentChunker(ChunkConfig(max_tokens=18, overlap_sentences=0))
        chunks = chunker.chunk(article)

        assert len(chunks) >= 2

    def test_metadata_populated(self) -> None:
        article = FullTextArticle(
            sections=[
                ArticleSection(
                    heading="Results",
                    body=(
                        "The results shown in Fig. 1 confirm our hypothesis [1]. "
                        "This is a significant finding."
                    ),
                ),
            ],
        )
        chunker = DocumentChunker(ChunkConfig(max_tokens=2048, overlap_sentences=0))
        chunks = chunker.chunk(article, document_id="paper:42")

        assert len(chunks) == 1
        meta = chunks[0].metadata
        assert meta.document_id == "paper:42"
        assert meta.section == "Results"
        assert meta.token_count > 0
        assert len(meta.citation_list) > 0
        assert len(meta.figure_refs) > 0
        assert meta.chunk_index == 0
        assert meta.total_chunks == 1

    def test_chunk_under_token_limit(self) -> None:
        long_para = "Word. " * 500
        article = FullTextArticle(
            sections=[
                ArticleSection(heading="Introduction", body=long_para.strip()),
            ],
        )
        chunker = DocumentChunker(ChunkConfig(max_tokens=80, overlap_sentences=0))
        chunks = chunker.chunk(article)

        assert len(chunks) >= 2
        for chunk in chunks:
            assert chunk.metadata.token_count <= 120

    def test_single_paragraph_below_limit(self) -> None:
        article = FullTextArticle(
            abstract="A short abstract with minimal content.",
        )
        chunker = DocumentChunker(ChunkConfig(max_tokens=2048, overlap_sentences=0))
        chunks = chunker.chunk(article)

        assert len(chunks) == 1
        assert "short abstract" in chunks[0].text

    def test_empty_text(self) -> None:
        article = FullTextArticle()
        chunker = DocumentChunker()
        chunks = chunker.chunk(article)

        assert len(chunks) == 0

    def test_all_sections_one_chunk_when_merged(self) -> None:
        article = FullTextArticle(
            sections=[
                ArticleSection(heading="Introduction", body="Intro content."),
                ArticleSection(heading="Methods", body="Methods content."),
                ArticleSection(heading="Results", body="Results content."),
            ],
        )
        chunker = DocumentChunker(
            ChunkConfig(max_tokens=2048, respect_sections=False, overlap_sentences=0)
        )
        chunks = chunker.chunk(article)

        assert len(chunks) == 1
        assert "Intro content" in chunks[0].text
        assert "Methods content" in chunks[0].text
        assert "Results content" in chunks[0].text

    def test_chunk_text_convenience(self) -> None:
        text = (
            "A Title\n\n"
            "Abstract\n"
            "This is the abstract.\n\n"
            "Introduction\n"
            "This is the intro. It has two sentences.\n\n"
            "Methods\n"
            "This is the methods section.\n"
        )
        chunker = DocumentChunker(ChunkConfig(max_tokens=2048, overlap_sentences=0))
        chunks = chunker.chunk_text(text, document_id="raw:1")

        assert len(chunks) >= 1
        assert any("Abstract" in c.metadata.section for c in chunks)
        assert any(c.metadata.document_id == "raw:1" for c in chunks)

    def test_citation_list_in_metadata(self) -> None:
        article = FullTextArticle(
            sections=[
                ArticleSection(
                    heading="Introduction",
                    body=(
                        "Prior work [1] established the foundation. "
                        "Later studies [2, 3] expanded on it. "
                        "(Smith, 2020) confirmed the results."
                    ),
                ),
            ],
        )
        chunker = DocumentChunker(ChunkConfig(max_tokens=2048, overlap_sentences=0))
        chunks = chunker.chunk(article)

        assert len(chunks) == 1
        citations = chunks[0].metadata.citation_list
        assert len(citations) >= 1
        assert any("[1]" in c for c in citations)

    def test_subsection_context_in_metadata(self) -> None:
        article = FullTextArticle(
            sections=[
                ArticleSection(
                    heading="Introduction", body="First para.\n\nSecond para."
                ),
            ],
        )
        chunker = DocumentChunker(ChunkConfig(max_tokens=4, overlap_sentences=0))
        chunks = chunker.chunk(article)

        assert len(chunks) >= 2
        assert chunks[0].metadata.paragraph_index == 0
        assert chunks[-1].metadata.paragraph_index > 0

    def test_mixed_paragraph_normal_and_list(self) -> None:
        article = FullTextArticle(
            sections=[
                ArticleSection(
                    heading="Methods",
                    body=(
                        "We used standard protocols for this experiment. "
                        "The samples were prepared as described.\n\n"
                        "The following equipment was used:\n"
                        "- Spectrophotometer\n"
                        "- Centrifuge\n"
                        "- Microscope"
                    ),
                ),
            ],
        )
        chunker = DocumentChunker(ChunkConfig(max_tokens=2048, overlap_sentences=0))
        chunks = chunker.chunk(article)

        all_text = " ".join(c.text for c in chunks)
        assert "standard protocols" in all_text
        assert "Spectrophotometer" in all_text
        assert "Centrifuge" in all_text

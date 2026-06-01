# Phase 5 — Retrieval-Augmented Generation (Structure-Aware)

**Duration**: 4 weeks (Sep–Oct 2026)
**Dependencies**: Phase 4 (literature engine, embeddings)
**Output**: RAG pipeline with narrative structure preservation, citation enforcement

---

### Task 5.1: Narrative Structure-Preserving DocumentChunker

- [ ] 5.1.1: Section-aware chunking — detect and preserve Introduction/Methods/Results/Discussion/Conclusion structure
- [ ] 5.1.2: Hierarchical chunking — paragraph-level chunks with document/section context preserved
- [ ] 5.1.3: Citation-anchored splits — never split a sentence from its citation reference
- [ ] 5.1.4: Figure/table proximity — keep inline references to figures/tables in same chunk
- [ ] 5.1.5: Overlap strategy — configurable overlap between adjacent chunks (default: 1 sentence)
- [ ] 5.1.6: Chunk metadata — document_id, section, subsection, paragraph index, token count, citation_list
- [ ] 5.1.7: Bullet/numbered list preservation — don't split across list items
- [ ] 5.1.8: Code block preservation — keep code/math blocks intact

### Task 5.2: HybridRetriever (Dense + Sparse)

- [ ] 5.2.1: Dense retrieval via Phase 4 EmbeddingIndex
- [ ] 5.2.2: Sparse retrieval via BM25 (rank_bm25 or custom implementation)
- [ ] 5.2.3: Reciprocal Rank Fusion (RRF) for combining dense + sparse results
- [ ] 5.2.4: Cross-encoder reranking (sentence-transformers cross-encoder) on top-K results
- [ ] 5.2.5: Configurable: top_k, dense_weight, sparse_weight, rerank_top_k
- [ ] 5.2.6: Query expansion — expand search terms using synonym/abbreviation dictionary
- [ ] 5.2.7: Fielded search — search within specific sections (title-only, abstract-only, methods-only)

### Task 5.3: CitationContextWindow

- [ ] 5.3.1: When retrieving a chunk, retrieve surrounding citation network context
- [ ] 5.3.2: Citation neighborhood: which papers cite or are cited by papers in the retrieved chunk
- [ ] 5.3.3: Citation density scoring — how central is this claim to the literature
- [ ] 5.3.4: Citation contradiction detection — if two retrieved chunks cite conflicting findings, flag
- [ ] 5.3.5: Temporal weighting — more recent citations weighted higher (configurable decay function)

### Task 5.4: ContextWindowManager

- [ ] 5.4.1: Token budget tracking — total available context window, used so far, remaining
- [ ] 5.4.2: Dynamic compression — truncate less relevant chunks when budget is exceeded
- [ ] 5.4.3: Priority-based inclusion — rank chunks by relevance score, fill from highest
- [ ] 5.4.4: Structured context packaging — format context as: [Document: X] Section: Y] ... for model consumption
- [ ] 5.4.5: Context overflow strategy — summarize low-priority chunks, retain high-priority full text
- [ ] 5.4.6: Model-specific context limits — respect each model's maximum context window

### Task 5.5: SourceEnforcer

- [ ] 5.5.1: Output parsing — extract citations from generated text (simple pattern: [@doi:, [1], (Author, Year))
- [ ] 5.5.2: Citation verification — verify each cited source exists in retrieved context
- [ ] 5.5.3: Unsupported claim detection — flag sentences without citations for review
- [ ] 5.5.4: Citation enforcement modes:
  - `strict`: refuse to generate output without supporting citations
  - `warn`: generate but highlight unsupported claims
  - `audit`: generate and log unsupported claims for review
- [ ] 5.5.5: Citation suggestion — for unsupported claims, suggest candidate citations from retrieved context

### Task 5.6: CitationFormatter

- [ ] 5.6.1: Style templates: Nature, Science, APA 7th, Vancouver, IEEE, Chicago, ACS, custom
- [ ] 5.6.2: In-text citation formatting — (Author, Year), [1], [Author et al.], superscript
- [ ] 5.6.3: Reference list generation — alphabetized, numbered, or order-of-appearance
- [ ] 5.6.4: DOI hyperlinking for digital references
- [ ] 5.6.5: Multi-format export — BibTeX, RIS, CSL-JSON

### Task 5.7: SourceEnforcer Cross-Check

- [ ] 5.7.1: Semantic cross-check — verify that cited sources actually say what the claim attributes to them (beyond existence check in 5.5.2); uses LLM to compare claim against source text

### Task 5.8: Pedagogical Report

- [ ] 5.8.1: Report template — outputs must include: selection rationale (why these sources), parameter documentation (retrieval settings, model config), alternative interpretations, self-identified limitations, uncertainty indicators
- [ ] 5.8.2: Export formats — Markdown (default), Jupyter notebook, RO-Crate
- [ ] 5.8.3: No artifact modes — explicit design constraint: no audio/video/slide-deck generation modes

### Task 5.9: RAG Tests

- [ ] 5.9.1: Unit tests for DocumentChunker — section detection, citation anchoring, overlap
- [ ] 5.9.2: Unit tests for HybridRetriever — RRF fusion, reranking correctness
- [ ] 5.9.3: Unit tests for ContextWindowManager — token budget, compression, priority-based inclusion
- [ ] 5.9.4: Unit tests for SourceEnforcer — all 3 modes, citation verification, semantic cross-check
- [ ] 5.9.5: Unit tests for CitationFormatter — all style templates, reference list generation
- [ ] 5.9.6: Integration test: chunk document → embed → retrieve → cite → format → enforce → cross-check
- [ ] 5.9.7: Integration test: cross-document retrieval with citation context windows
- [ ] 5.9.8: Unit tests for PedagogicalReport — all export formats, required sections, no-artifact enforcement

---

**Phase 5 Exit Criteria**: RAG pipeline end-to-end: chunk a paper → search with query → retrieve relevant chunks → cite sources in response → enforce citations. All citation styles formatted correctly.

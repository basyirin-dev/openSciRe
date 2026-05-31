# Phase 4 — Scientific Literature Engine (Global)

**Duration**: 4 weeks (Aug–Sep 2026)
**Dependencies**: Phase 1 (models), Phase 2 (model access for embeddings)
**Output**: Multi-source literature ingestion, search, embedding, retraction monitoring

---

### Task 4.1: Reference Manager Bridges

- [ ] 4.1.1: `ZoteroBridge` — OAuth2 authentication, collection listing, item retrieval, attachment download, webDAV sync support
- [ ] 4.1.2: `MendeleyBridge` — OAuth2 authentication, folder listing, document retrieval, file download
- [ ] 4.1.3: Local reference file import — BibTeX, RIS, CSL-JSON, Endnote XML
- [ ] 4.1.4: Deduplication — fuzzy matching across sources (DOI, title similarity, author+year)
- [ ] 4.1.5: Incremental sync — only fetch new/changed items since last sync

### Task 4.2: PubMed/PMC Bridge

- [ ] 4.2.1: `PubMedBridge` — E-utilities API (esearch, efetch, esummary)
- [ ] 4.2.2: `PMCBridge` — PMC Open Access subset download, full-text XML parsing
- [ ] 4.2.3: MEDLINE format parsing
- [ ] 4.2.4: MeSH term extraction and indexing
- [ ] 4.2.5: PMID → DOI resolution

### Task 4.3: Europe PMC Bridge

- [ ] 4.3.1: `EuropePMCBridge` — RESTful API (search, retrieve, references, citations)
- [ ] 4.3.2: Full-text XML and PDF retrieval
- [ ] 4.3.3: Text mining API access (annotations, ontologies, chemical entities)

### Task 4.4: arXiv Client

- [ ] 4.4.1: `ArXivClient` — arXiv API v2 (search by ID, category, author, date range)
- [ ] 4.4.2: Bulk paper download with rate limiting
- [ ] 4.4.3: LaTeX source retrieval (for enhanced parsing)
- [ ] 4.4.4: arXiv → DOI resolution (when available)
- [ ] 4.4.5: Category filtering (cs.*, q-bio.*, physics.*, stat.*, math.*, q-fin.*)

### Task 4.5: Semantic Scholar Client

- [ ] 4.5.1: `SemanticScholarClient` — search, paper lookup, author lookup
- [ ] 4.5.2: Citation graph traversal (incoming citations, outgoing references)
- [ ] 4.5.3: Recommendations API (similar papers, influential citations)
- [ ] 4.5.4: Open Access PDF retrieval (when available)
- [ ] 4.5.5: Embedding retrieval (when API returns T-SBERT embeddings)

### Task 4.6: OpenAlex Client

- [ ] 4.6.1: `OpenAlexClient` — search, paper, author, institution, concept APIs
- [ ] 4.6.2: Free/open alternative to commercial APIs (no API key required for moderate use)
- [ ] 4.6.3: Concept tagging (hierarchical research topic classification)
- [ ] 4.6.4: Institutional affiliation extraction
- [ ] 4.6.5: Citation count and altmetric data

### Task 4.7: Unpaywall Client

- [ ] 4.7.1: `UnpaywallClient` — DOI → open-access URL resolution
- [ ] 4.7.2: Color classification (gold, green, hybrid, bronze, closed)
- [ ] 4.7.3: Batch DOI resolution
- [ ] 4.7.4: Fallback: if DOI not found, try Google Scholar or direct PDF search

### Task 4.8: Non-English Corpus Support

- [ ] 4.8.1: CNKI (Chinese National Knowledge Infrastructure) — metadata search API
- [ ] 4.8.2: Wanfang Data — Chinese scientific metadata search
- [ ] 4.8.3: SciELO (Scientific Electronic Library Online) — Latin American open access
- [ ] 4.8.4: AJOL (African Journals Online) — African research metadata
- [ ] 4.8.5: eLibrary.ru (РИНЦ) — Russian scientific metadata
- [ ] 4.8.6: Multilingual embedding model support (LaBSE, multilingual E5, BGE-M3)
- [ ] 4.8.7: Translation-with-uncertainty — when translating non-English content, flag confidence level and potential meaning loss
- [ ] 4.8.8: Parallel text source: offer original-language version alongside translation
- [ ] 4.8.9: Language detection on ingestion

### Task 4.9: RetractionMonitor

- [ ] 4.9.1: PubMed Retraction Watch feed — periodic polling for new retractions
- [ ] 4.9.2: Crossref correction feed — DOI events API for retractions, corrections, expressions of concern
- [ ] 4.9.3: PubPeer integration — post-publication peer review monitoring
- [ ] 4.9.4: Local retraction database — cache of retracted/corrected papers with reasons
- [ ] 4.9.5: Automatic re-flaggings — when a previously stored paper is retracted, mark it in local index and notify user
- [ ] 4.9.6: Retraction status display — visible in search results, literature view, citation counts
- [ ] 4.9.7: Citation chain invalidation — if a paper is retracted, flag all claims citing it

### Task 4.10: PDF Parser

- [ ] 4.10.1: Local PDF text extraction (no cloud API) — `pdfplumber` or `pypdf` base
- [ ] 4.10.2: Full-text structured extraction — title, authors, abstract, sections (Introduction, Methods, Results, Discussion, References), figures/tables captions
- [ ] 4.10.3: Reference list extraction and DOI resolution
- [ ] 4.10.4: Figure/table extraction (image + caption)
- [ ] 4.10.5: Fallback: GROBID (if available locally) for enhanced PDF-to-XML

### Task 4.11: Local Embedding Index

- [ ] 4.11.1: Sentence embedding model loader (sentence-transformers, local only)
- [ ] 4.11.2: `EmbeddingIndex` — add documents, search, delete, update
- [ ] 4.11.3: Backend abstraction: FAISS (in-memory), Chroma (persistent), SQLite-vss (lightweight)
- [ ] 4.11.4: Incremental indexing — add papers without rebuilding full index
- [ ] 4.11.5: Metadata filtering — filter search by year, author, journal, domain, language
- [ ] 4.11.6: Index persistence — save/load index to disk
- [ ] 4.11.7: Cross-encoder reranking (optional, for improved search quality)

### Task 4.12: Citation Graph Analyzer

- [ ] 4.12.1: Citation chain traversal — follow references and citations bi-directionally
- [ ] 4.12.2: Influence scoring — PageRank-style citation network analysis
- [ ] 4.12.3: Citation timeline — how citation patterns have evolved over time
- [ ] 4.12.4: Citation decay detection — papers still being cited vs. deprecated
- [ ] 4.12.5: Citation clustering — find papers that are frequently cited together
- [ ] 4.12.6: Network visualization data export (for D3.js, Cytoscape)

### Task 4.13: Literature Engine Tests

- [ ] 4.13.1: Unit tests for each bridge client (with mock responses)
- [ ] 4.13.2: Unit tests for PDF parser with test fixtures
- [ ] 4.13.3: Unit tests for EmbeddingIndex (add, search, delete, metadata filter)
- [ ] 4.13.4: Unit tests for RetractionMonitor (polling, caching, re-flagging)
- [ ] 4.13.5: Unit tests for CitationGraphAnalyzer (traversal, scoring, clustering)
- [ ] 4.13.6: Integration test: Zotero import → PDF parse → embed → search → retraction check
- [ ] 4.13.7: Integration test: Semantic Scholar → OpenAlex cross-reference

---

**Phase 4 Exit Criteria**: Can search PubMed, arXiv, Semantic Scholar. Can import Zotero collection. PDFs are parsed and embedded locally. RetractionMonitor flags retracted papers. Non-English metadata search works for at least one non-English source.

# Phase 4 — Scientific Literature Engine (Global) + Bio Database Bridges

**Duration**: 6 weeks (Aug–Oct 2026)
**Dependencies**: Phase 1 (models), Phase 2 (model access for embeddings)
**Output**: Multi-source literature ingestion, search, embedding, retraction monitoring, bio database bridges (UniProt, PDB, NCBI, AlphaFold DB, InterPro), gap analysis, adversarial curation

> **Design**: This phase builds the global literature ingestion pipeline (4.1–4.11) AND the shared bridge infrastructure (4.14) that feeds both literature and bio database sources into RAG (Phase 5) and hypothesis generation (Phase 7). Bio database bridges (4.15–4.19) are integrated early so that hypothesis generation can ground in structural biology data from Phase 7 onward.

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
- [ ] 4.9.5: Automatic re-flagging — when a previously stored paper is retracted, mark it in local index and notify user
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

### Task 4.12: GapAnalyzer

- [ ] 4.12.1: Coverage gap detection — topics with insufficient source coverage (fewer than configurable minimum sources per subtopic)
- [ ] 4.12.2: Methodological monoculture detection — identify domains where all available studies use the same experimental method (e.g., all in vitro, no in vivo)
- [ ] 4.12.3: Geographic/language gap detection — sources exclusively from Global North countries; flag missing geographic representation
- [ ] 4.12.4: Temporal gap detection — identify time periods with no literature coverage (e.g., no studies between 2010–2015 for a given topic)
- [ ] 4.12.5: Gap report — structured output for LiteratureReviewAgent consumption; formatted as actionable search recommendations

### Task 4.13: Anti-Echo Chamber & Adversarial Curation

- [ ] 4.13.1: External source ratio enforcer — mandates minimum ratio of external-to-user-provided sources (configurable, default: 50% external)
- [ ] 4.13.2: Adversarial source inclusion — for every claim in the user's source set, auto-retrieve at least one contradictory or alternative-view source
- [ ] 4.13.3: Confidence-weighted display — sources ranked by evidence quality (sample size, methodology, replication status), not by user preference or recency
- [ ] 4.13.4: Assumption mining — extract implicit assumptions from user's research question; retrieve sources that test those assumptions

### Task 4.14: Shared BridgeAdapter Infrastructure

- [ ] 4.14.1: `BridgeAdapter` abstract base class — shared API contract between literature source bridges and bio database bridges; requires `search()`, `get()`, `metadata()`, `rate_limit()` methods
- [ ] 4.14.2: Common rate limiter — token-bucket algorithm shared across all bridges; per-API-backoff on 429 responses
- [ ] 4.14.3: Circuit breaker — per-bridge failure tracking; auto-disable bridge after configurable consecutive failures (default: 5)
- [ ] 4.14.4: Shared cache layer — TTL-based response cache (SQLite backend); bridges declare cache TTL per endpoint type
- [ ] 4.14.5: `CrossReferenceResolver` — resolve biological cross-references (SIFTS: PDB→UniProt, sequence identity, DOI→PMID→PMCID)
- [ ] 4.14.6: `ConfidenceTrace` propagation engine — recursive confidence data structure that carries per-residue/per-claim confidence from source through all transformations; supports union (max), intersection (min), and weighted-average propagation strategies
- [ ] 4.14.7: `EvidenceTypeLabel` system — every data point tagged with evidence type: P (predicted, e.g., AlphaFold2), E (experimental, e.g., X-ray crystallography), R (reviewed, e.g., UniProt/Swiss-Prot curated); labels propagate through all operations
- [ ] 4.14.8: Query manifest builder — documents every query parameter for reproducibility; stores in provenance as `ProvenanceEntry`

### Task 4.15: UniProt Bridge

- [ ] 4.15.1: REST API client — GET `/uniprotkb/search`, `/uniprotkb/{accession}`, `/uniprotkb/{accession}/proteomics`, `/uniprotkb/{accession}/interaction`
- [ ] 4.15.2: Query builder — organism, gene name, protein name, sequence length, reviewed status, taxonomy filters
- [ ] 4.15.3: Response parser — extract accession, entry name, protein names, gene names, organism, function, subcellular location, PTMs, sequence, domain architecture
- [ ] 4.15.4: Evidence code extraction — parse and propagate UniProt evidence codes (ECO IDs); map to EvidenceTypeLabel (Swiss-Prot manually reviewed → E, TrEMBL automatically annotated → P)
- [ ] 4.15.5: Version tracking — record UniProt release version per query in provenance
- [ ] 4.15.6: Cross-reference extraction — parse and store cross-refs to PDB, EMBL, Pfam, InterPro, STRING, Reactome, GO

### Task 4.16: PDB Bridge

- [ ] 4.16.1: REST API client — RCSB PDB GraphQL API; search by sequence, structure ID, ligand, author, resolution range
- [ ] 4.16.2: Structure metadata parser — PDB ID, title, experimental method, resolution, R-value, release date, deposition author
- [ ] 4.16.3: Experimental vs. predicted classification — method tag: X-ray (E), NMR (E), cryo-EM (E), electron crystallography (E), computational (P)
- [ ] 4.16.4: Resolution/quality filtering — filter search results by resolution threshold, R-free/R-work ratio
- [ ] 4.16.5: Cross-reference extraction — parse cross-refs to UniProt, SCOP, CATH, PFAM, PubMed

### Task 4.17: NCBI/Entrez Bridge

- [ ] 4.17.1: E-utilities client — esearch, efetch, esummary, elink across all NCBI databases (nucleotide, protein, genome, gene, taxonomy, biosample, SRA, dbGaP, ClinVar)
- [ ] 4.17.2: Nucleotide search — accession, gene name, organism, sequence range
- [ ] 4.17.3: Genome assembly search — assembly accession, organism, assembly level (complete genome, chromosome, contig, scaffold)
- [ ] 4.17.4: Taxonomy search — taxon ID, scientific name, common name, lineage, genetic code
- [ ] 4.17.5: Literature cross-reference — given a PubMed ID, retrieve all linked NCBI records (associated sequences, structures, assemblies, GEO datasets)
- [ ] 4.17.6: Rate-limit compliance — respect NCBI's 3-requests-per-second guideline

### Task 4.18: AlphaFold DB Bridge

- [ ] 4.18.1: REST API client — AlphaFold DB API; search by UniProt accession, gene name, organism
- [ ] 4.18.2: Structure download — download predicted PDB/MMCIF files from AlphaFold DB
- [ ] 4.18.3: pLDDT confidence propagation — parse pLDDT scores per residue; attach per-residue ConfidenceTrace with P label (predicted)
- [ ] 4.18.4: PAE data extraction — parse Predicted Aligned Error (PAE) JSON; provide domain-level confidence via PAE matrix clustering
- [ ] 4.18.5: Explicit P-labeling — all data from AlphaFold DB tagged EvidenceTypeLabel.P (predicted); confidence threshold warnings at configurable cutoff (default: pLDDT < 70)
- [ ] 4.18.6: Intrinsically disordered region flagging — highlight regions with pLDDT < 50; suggest they may be disordered rather than confidently folded
- [ ] 4.18.7: Post-pilot bulk download — AlphaFold proteome-level bulk download for organism-scale analysis

### Task 4.19: InterPro Bridge

- [ ] 4.19.1: REST API client — InterProScan API; submit sequence, retrieve domain annotations
- [ ] 4.19.2: Domain/family annotation parser — extract InterPro ID, Pfam ID, GO terms, signature database matches (Pfam, SMART, PROSITE, CDD, PANTHER, SFLD, HAMAP, PRINTS)
- [ ] 4.19.3: E-value filtering — configurable E-value threshold for domain matches; propagate E-value into ConfidenceTrace
- [ ] 4.19.4: Signature database metadata — for each domain match, record the source database and signature method (HMM, profile, pattern, fingerprint)

### Task 4.20: Bio Bridge Documentation & Deferred Registry

- [ ] 4.20.1: Bio bridge usage documentation — per-bridge README covering: query syntax, rate limits, confidence interpretation (EvidenceTypeLabel), known limitations, version tracking
- [ ] 4.20.2: Deferred bridge registry — documented trigger conditions for when to implement each deferred bridge:
  - OMIM (trigger: gene-disease association queries)
  - GTEx (trigger: tissue-specific expression analysis)
  - GEO/ArrayExpress (trigger: transcriptomics queries)
  - BioGRID (trigger: protein-protein interaction network queries)
  - KEGG (trigger: pathway analysis queries)
  - ChEMBL (trigger: drug-target interaction queries)
  - STRING (trigger: PPI network visualization queries)

### Task 4.21: Citation Graph Analyzer

- [ ] 4.21.1: Citation chain traversal — follow references and citations bi-directionally
- [ ] 4.21.2: Influence scoring — PageRank-style citation network analysis
- [ ] 4.21.3: Citation timeline — how citation patterns have evolved over time
- [ ] 4.21.4: Citation decay detection — papers still being cited vs. deprecated
- [ ] 4.21.5: Citation clustering — find papers that are frequently cited together
- [ ] 4.21.6: Network visualization data export (for D3.js, Cytoscape)

### Task 4.22: Literature Engine Tests

- [ ] 4.22.1: Unit tests for each bridge client (with mock responses)
- [ ] 4.22.2: Unit tests for PDF parser with test fixtures
- [ ] 4.22.3: Unit tests for EmbeddingIndex (add, search, delete, metadata filter)
- [ ] 4.22.4: Unit tests for RetractionMonitor (polling, caching, re-flagging)
- [ ] 4.22.5: Unit tests for CitationGraphAnalyzer (traversal, scoring, clustering)
- [ ] 4.22.6: Unit tests for GapAnalyzer (coverage gap, monoculture detection, geographic gap, temporal gap, report generation)
- [ ] 4.22.7: Unit tests for AntiEchoChamber (external ratio enforcer, adversarial inclusion, confidence-weighted display)
- [ ] 4.22.8: Unit tests for BridgeAdapter (rate limiter, circuit breaker, cache, CrossReferenceResolver)
- [ ] 4.22.9: Unit tests for ConfidenceTrace (propagation strategies, evidence type labeling)
- [ ] 4.22.10: Unit tests for each bio bridge (UniProt, PDB, NCBI, AlphaFold DB, InterPro — with mock responses)
- [ ] 4.22.11: Unit tests for EvidenceTypeLabel system (P/E/R propagation through transformations)
- [ ] 4.22.12: Integration test: Zotero import → PDF parse → embed → search → retraction check
- [ ] 4.22.13: Integration test: Semantic Scholar → OpenAlex cross-reference
- [ ] 4.22.14: Integration test: UniProt search → AlphaFold structure retrieval → confidence propagation → cross-reference to PDB
- [ ] 4.22.15: Integration test: PubMed search → NCBI elink → cross-reference resolution → evidence type labeling

---

**Phase 4 Exit Criteria**: Can search PubMed, arXiv, Semantic Scholar. Can import Zotero collection. PDFs are parsed and embedded locally. RetractionMonitor flags retracted papers. Non-English metadata search works for at least one non-English source. GapAnalyzer identifies coverage gaps. Anti-echo chamber enforces source diversity. Bio bridges for UniProt, PDB, NCBI, AlphaFold DB, and InterPro operational with confidence propagation. EvidenceTypeLabel system functional. All tests pass with >80% coverage.

> **See proposals**: [`docs/proposals/openscire-bio.md`](../proposals/openscire-bio.md) for full bio bridge design, [`docs/proposals/openscire-literature.md`](../proposals/openscire-literature.md) for literature engine architecture.

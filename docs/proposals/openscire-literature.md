# openscire-literature — Multi-Source Literature Insights with Narrative-Preserving RAG and Adversarial Curation

## I. Overview & Motivation

openscire-literature is OpenSciRe's "What is known?" engine — a multi-source literature retrieval, synthesis, contradiction detection, and adversarial curation system built on first-principles epistemic humility. It is the structural replacement for Google's NotebookLM, reframed (and renamed) as "Literature Insights" within the Gemini for Science triad. Where NotebookLM is a content-generation tool that happens to ingest PDFs, openscire-literature is a critical-reading infrastructure that happens to generate structured reports.

Google's NotebookLM synthesizes user-uploaded corpora into tables, audio overviews, slide decks, and chat interfaces. Its fundamental flaws are architectural, not incremental:

- **Closed epistemic universe**: NotebookLM can only see what the user uploads. It cannot alert the user to missing papers, detect corpus bias, or draw connections to un-uploaded literature [06_notebooklm.md](../../critiques/06_notebooklm.md):§1.
- **RAG fragmentation destroys narrative arc**: Scientific papers are holistic arguments. RAG chunking rips them into fragments and reassembles them via similarity search, violating the author's intentional structure and the reader's need for narrative coherence [06_notebooklm.md](../../critiques/06_notebooklm.md):§2.
- **No methodological evaluation**: NotebookLM synthesizes claims without assessing how they were produced — sample sizes, control groups, statistical validity. It is bibliometrically thick and methodologically thin [06_notebooklm.md](../../critiques/06_notebooklm.md):§8.
- **Temporal blindness**: The corpus is a synchronic snapshot with no retraction awareness, no historical context, and no diachronic tracking of conceptual evolution [06_notebooklm.md](../../critiques/06_notebooklm.md):§9.
- **Echo chamber design**: The tool accommodates the user's framing, confirms their corpus selection, and never challenges assumptions. It is a sycophant, not a critic [06_notebooklm.md](../../critiques/06_notebooklm.md):§22.
- **Commodification of reading**: Audio overviews, infographics, and slide decks transform knowledge into content, understanding into consumption, and the researcher into a spectator [06_notebooklm.md](../../critiques/06_notebooklm.md):§26, §45.

openscire-literature inverts every one of these defaults. It builds on an open multi-source corpus (not user-upload-only), preserves narrative structure through section-aware chunking (not context-window fragments), employs adversarial curation (not echo chamber accommodation), maintains retraction-aware temporal tracking (not synchronic blindness), and generates pedagogical, provenance-traced reports (not consumable artifacts). It is designed for **capacitation** — equipping the researcher to think, judge, and critique — not for **content delivery**.

Within the broader OpenSciRe ecosystem, openscire-literature feeds literature synthesis and gap identification into openscire-hypothesis (Phase 6-7), contextualizes computational results from openscire-sandbox against existing knowledge, and routes all retrievals through the shared provenance DAG with full temporal and parametric audit trails.

---

## II. Literature Engine (Phase 4)

The Literature Engine is the ingestion and retrieval substrate. Unlike NotebookLM, which waits for the user to upload documents, openscire-literature proactively bridges multiple scientific knowledge sources, both open and user-authorized.

### A. Multi-Source Retrieval

Each source is accessed via a per-source adapter implementing a common `SourceAdapter` interface with `search()`, `fetch()`, `get_metadata()`, and `stream()` methods. Adapters operate independently; if one source is unavailable, others continue serving results without degradation.

| Source | Retrieval Method | Coverage | Authentication |
|--------|-----------------|----------|----------------|
| PubMed / PMC | E-utilities API (esearch, efetch, esummary) | 36M+ citations, full-text PMC OA subset | None (rate-limited) |
| Europe PMC | REST API (search, retrieve, references, citations) | 42M+ records, full-text XML & PDF | None (rate-limited) |
| arXiv | API v2 (search by ID, category, author, date range) | 2.5M+ preprints, LaTeX source | None |
| Semantic Scholar | REST API (search, paper lookup, citation graph, recommendations) | 210M+ papers, citation graph, open-access PDFs | API key (free) |
| OpenAlex | REST API (search, paper, author, institution, concept) | 250M+ works, hierarchical concept tags, open | None (moderate use) |
| Unpaywall | DOI → OA URL resolution | 40M+ DOIs, color classification | Email (rate-tier) |
| Zotero | OAuth2, WebDAV sync | User's personal library | OAuth2 |
| Mendeley | OAuth2 | User's personal library | OAuth2 |
| Crossref | REST API, DOI Event API (corrections, retractions) | 150M+ DOIs, event stream | None |
| CNKI | Metadata search API | Chinese scientific literature (~60M records) | Institutional |
| Wanfang Data | Metadata search API | Chinese scientific literature | Institutional |
| SciELO | REST API | Latin American open access (1.5M+ articles) | None |
| AJOL | Metadata search (REST) | African research (500+ journals) | None |
| eLibrary.ru (РИНЦ) | Metadata search API | Russian scientific literature | Institutional |

#### Source Adapter Pattern

```python
class SourceAdapter(ABC):
    @abstractmethod
    async def search(self, query: SearchQuery) -> list[SearchResult]:
        ...

    @abstractmethod
    async def fetch(self, identifier: str) -> Document:
        ...

    @abstractmethod
    def get_metadata(self) -> SourceMetadata:
        ...

    @abstractmethod
    async def stream(self, query: SearchQuery) -> AsyncIterator[SearchResult]:
        ...
```

Graceful degradation is structural: if a source returns a 503, the dispatcher logs the failure, records the gap in provenance, and proceeds with remaining sources. The user is notified of which sources were unreachable.

#### Non-English Source Handling

Non-English sources present structural challenges that NotebookLM's English-dominant architecture ignores. openscire-literature addresses this through:

- **Language detection on ingestion** (fastText-based, local)
- **Multilingual embedding models**: LaBSE, multilingual E5, BGE-M3 for cross-lingual retrieval [phase 4.8.6](../../docs/phases/04_literature_engine.md)
- **Translation-with-uncertainty**: when converting non-English content to English for cross-lingual synthesis, flag confidence level and potential meaning loss [phase 4.8.7](../../docs/phases/04_literature_engine.md)
- **Parallel text display**: original-language content alongside machine-translated version [phase 4.8.8](../../docs/phases/04_literature_engine.md)

This addresses the **linguistic imperialism** gap [06_notebooklm.md](../../critiques/06_notebooklm.md):§28 and the **non-English exclusion** gap [08_miscellaneous.md](../../critiques/08_miscellaneous.md):§22.

### B. Retraction Monitor (Phase 4.9)

Scientific knowledge is diachronic: papers are corrected, retracted, and contested. NotebookLM has no live connection to retraction feeds and will happily synthesize retracted findings as valid [06_notebooklm.md](../../critiques/06_notebooklm.md):§9. openscire-literature's `RetractionMonitor` provides:

- **PubMed Retraction Watch feed polling**: periodic checks for new retractions, expressions of concern, and corrections [phase 4.9.1](../../docs/phases/04_literature_engine.md)
- **Crossref correction feed**: DOI Events API subscription for retractions, corrections, and updates [phase 4.9.2](../../docs/phases/04_literature_engine.md)
- **PubPeer integration**: post-publication peer review monitoring [phase 4.9.3](../../docs/phases/04_literature_engine.md)
- **Local retraction database**: cache of retracted/corrected papers with reason codes and dates [phase 4.9.4](../../docs/phases/04_literature_engine.md)
- **Automatic re-flagging**: when a previously ingested paper is retracted, update the local index and queue user notification [phase 4.9.5](../../docs/phases/04_literature_engine.md)
- **Citation chain invalidation**: if Paper A is retracted, every claim, synthesis, or hypothesis artifact that cites Paper A is flagged with a retraction alert [phase 4.9.7](../../docs/phases/04_literature_engine.md)

The last point is architecturally crucial. NotebookLM's citation chains are static — it can produce "synthesis" of retracted literature with full "grounded" citations, creating an illusion of validity from invalid foundations. openscire-literature's citation chain invalidation means that retraction cascades: retract Paper A, and every downstream artifact (hypotheses, reports, gap analyses) that relied on A receives an automatic epistemic downgrade.

### C. Gap Identification

The `LiteratureReviewAgent` performs structural gap analysis across the retrieved corpus:

- **Coverage insufficiency detection**: areas with too few papers to support a confident synthesis. The agent will flag "This claim is supported by only 2 papers" or "No literature found on subtopic X within search scope."
- **Contradiction surface area**: corpus segments where papers directly contradict one another, with no resolution consensus.
- **Temporal coverage analysis**: which time periods are overrepresented or underrepresented. A synthesis restricted to 2020–2025 may miss foundational work from the 1990s.
- **Geographic coverage gaps**: which regions or language communities are absent from the evidence base.
- **Methodological gap detection**: systematic absence of specific study types (e.g., "all available studies are observational; no randomized controlled trials exist for this question").

This directly addresses NotebookLM's inability to see **negative space** — the unasked question, the absent method, the ignored population [06_notebooklm.md](../../critiques/06_notebooklm.md):§7 and the **missing negative capability** — the failure to refuse synthesis when the literature is too contradictory or too thin [06_notebooklm.md](../../critiques/06_notebooklm.md):§41.

---

## III. RAG Architecture (Phase 5)

### A. Narrative-Structure-Preserving Document Chunker (Phase 5.1)

The core technical innovation that distinguishes openscire-literature from every RAG system in the NotebookLM class. Where NotebookLM's chunking serves the LLM's context window (typically 500–1000 tokens of arbitrary document fragments), openscire-literature's chunking serves the **document's intentional structure**.

#### Section-Aware Chunking

The `DocumentChunker` detects and preserves the Introduction / Methods / Results / Discussion / Conclusion structure of scientific papers [phase 5.1.1](../../docs/phases/05_rag.md). A claim from the Discussion is never retrieved without awareness that it comes from the Discussion section, contextualized by the author's interpretive frame.

```python
@dataclass
class Chunk:
    document_id: str
    section: str          # "Introduction", "Methods", "Results", "Discussion", "Conclusion"
    subsection: str | None
    text: str
    citations: list[str]
    embeddings: list[float] | None
    position: int         # sequential position within document
    paragraph_index: int
    token_count: int
```

#### Citation-Anchored Splits

The chunker **never splits a sentence from its citation reference** [phase 5.1.3](../../docs/phases/05_rag.md). If a sentence cites [Smith et al., 2023; Jones, 2024], the entire sentence — including both citations — stays in one chunk. This prevents the interstitial hallucination where a claim is retrieved without its evidentiary anchor, and the generative model fabricates a citation to fill the gap [06_notebooklm.md](../../critiques/06_notebooklm.md):§15.

#### Cross-Chunk Reference Resolution

Inline references to figures, tables, equations, and sections within the same document are resolved to their targets. "As shown in Figure 3" is enriched with the Figure 3 caption and the surrounding Results text. "See Methods Section 2.1" links to the actual Methods chunk.

#### Chunk Overlap Strategy

Configurable overlap (default: one sentence) between adjacent chunks. Enough to preserve discourse connectors ("However," "Therefore," "In contrast") without bloating the index or diluting retrieval precision [phase 5.1.5](../../docs/phases/05_rag.md).

#### Bullet and List Preservation

Lists, numbered steps, and bullet points are never split across chunks. A seven-step protocol in the Methods section remains retrievable as a single coherent unit [phase 5.1.7](../../docs/phases/05_rag.md).

#### Code and Math Block Preservation

LaTeX equations, code blocks, and algorithmic pseudocode are preserved intact within their containing chunk. This directly addresses NotebookLM's inability to handle mathematical formalism [06_notebooklm.md](../../critiques/06_notebooklm.md):§34.

### B. Citation-Anchored Retrieval

Beyond standard semantic retrieval, openscire-literature supports **citation-anchored retrieval**: "find me where this specific paper is discussed or cited." This enables:

- Tracing how a finding has been received, challenged, or supported across the corpus
- Retrieving the specific passage where Smith et al. 2023's methodology is critiqued
- Building citation graphs that show how claims propagate through the literature

The `CitationContextWindow` (Phase 5.3) ensures that when a chunk is retrieved, the surrounding citation network is also surfaced: which papers cite the retrieved chunk's source, which are cited by it, and what the citation density is around that claim [phase 5.3.1](../../docs/phases/05_rag.md).

### C. Source Enforcer (Phase 5.5)

NotebookLM produces the **hallucination of synthesis**: correctly cited atomic claims that collectively assert a relationship no individual paper supports [06_notebooklm.md](../../critiques/06_notebooklm.md):§15. The `SourceEnforcer` is a structural defense against this.

**Operating modes:**

| Mode | Behavior | Use Case |
|------|----------|----------|
| `strict` | Refuse to generate output unless every claim has a supporting citation in retrieved context | Publication-ready synthesis |
| `warn` | Generate output but highlight unsupported claims with visual warning | Exploratory research |
| `audit` | Generate output and log unsupported claims for post-hoc review | Internal memos, lab notebooks |

**Core functions:**

1. **Output parsing**: extract all citations from generated text (supports `[@doi:...]`, `[1]`, `(Author, Year)`, superscript styles) [phase 5.5.1](../../docs/phases/05_rag.md)
2. **Citation verification**: confirm each cited source exists in the retrieved context [phase 5.5.2](../../docs/phases/05_rag.md)
3. **Unsupported claim detection**: flag sentences lacking citations [phase 5.5.3](../../docs/phases/05_rag.md)
4. **Cross-check**: verify that the claimed content actually appears in the cited source — not just that the citation exists, but that the source supports the specific claim [phase 3.7.5](../../docs/phases/03_ethics_layer.md)
5. **Citation suggestion**: for unsupported claims, propose candidate citations from the retrieved context [phase 5.5.5](../../docs/phases/05_rag.md)

This addresses the **interstitial hallucination** gap [06_notebooklm.md](../../critiques/06_notebooklm.md):§15, the **missing citation provenance in artifacts** gap [06_notebooklm.md](../../critiques/06_notebooklm.md):§17, and the **attribution ambiguity** gap [06_notebooklm.md](../../critiques/06_notebooklm.md):§24.

### D. Embedding Strategy

openscire-literature uses a hybrid retrieval architecture that combines dense and sparse methods, avoiding the similarity-search biases of pure vector retrieval [06_notebooklm.md](../../critiques/06_notebooklm.md):§16.

| Component | Model / Algorithm | Purpose |
|-----------|------------------|---------|
| Dense embeddings | sentence-transformers (all-MiniLM-L6-v2, SciBERT-NLI, etc.) | Semantic similarity retrieval |
| Cross-encoder reranker | sentence-transformers cross-encoder/ms-marco-MiniLM-L-6-v2 | Precision reranking of top-K results |
| Sparse retrieval | BM25 (rank_bm25 or custom) | Lexical matching fallback; handles out-of-vocabulary terms |
| Fusion | Reciprocal Rank Fusion (RRF) | Combines dense + sparse scores [phase 5.2.3](../../docs/phases/05_rag.md) |

**Backend abstraction** [phase 4.11](../../docs/phases/04_literature_engine.md):

| Backend | Persistence | Use Case |
|---------|-------------|----------|
| FAISS | In-memory | High-speed search on corpora < 1M chunks |
| Chroma | Persistent on disk | Long-running lab deployments |
| SQLite-vss | Embedded, lightweight | Single-user / laptop use |

All embedding and retrieval runs locally. No API calls to external embedding services. This is a hard architectural constraint: openscire-literature must function fully offline, with no cloud dependency for core retrieval operations.

---

## IV. Epistemic Layer

### A. Evidence Quality Assessment

NotebookLM treats all sources with equal hermeneutical respect — Nature and a predatory journal receive the same treatment [06_notebooklm.md](../../critiques/06_notebooklm.md):§39. openscire-literature evaluates evidence quality across multiple dimensions:

| Dimension | Metric | Source |
|-----------|--------|--------|
| Methodology quality | Study design tier (RCT > cohort > case-control > case series > expert opinion) | Extracted from full-text or inferred from MeSH terms |
| Sample size | N and power analysis (where reported) | Full-text extraction |
| Control appropriateness | Matched controls? Placebo? Historical? | Abstract + Methods |
| Citation impact | Citation count (with temporal normalization) | OpenAlex, Semantic Scholar |
| Venue reputation | Journal-level metrics (with caveats: no proxy for article quality) | Journal metadata |
| Source diversity | Number of independent research groups supporting a finding | Citation graph analysis |
| Temporal recency | Year of publication, replication currency | Metadata |
| Retraction status | Clean / corrected / expression of concern / retracted | RetractionMonitor |

The quality assessment is **displayed alongside every claim**, never hidden. A claim from a small underpowered study in a low-tier journal is flagged as such, even if it appears in a "confident" synthesis.

### B. Temporal Awareness

NotebookLM treats the corpus as a synchronic snapshot; openscire-literature is diachronic by design [06_notebooklm.md](../../critiques/06_notebooklm.md):§9.

- **Corpus versioning**: every document has an `ingestion_date`, and when retractions or corrections occur, the corpus version is updated. Users can query "what did we know in 2023?" vs. "what do we know now?"
- **Concept evolution tracking**: terms are tracked across time. When "inflammation" means something different in 1990 vs. 2026, the system surfaces this shift rather than collapsing it into a single vector [06_notebooklm.md](../../critiques/06_notebooklm.md):§10.
- **Retraction timeline**: retraction events are displayed alongside the original publication date, with before/after synthesis comparisons.
- **Temporal weighting**: configurable decay function that weights more recent citations higher in relevance scoring [phase 5.3.5](../../docs/phases/05_rag.md).

### C. Contradiction Detection

A critical capability NotebookLM entirely lacks: surfacing disagreements across sources rather than smoothing over them [06_notebooklm.md](../../critiques/06_notebooklm.md):§41.

The `ContradictionDetector`:
1. Identifies pairs of claims that address the same question but reach different conclusions
2. Extracts the supporting evidence for each side
3. Presents **both sides with equal structural weight** — never privileging one over the other
4. Labels the **resolution status**: resolved (replicated), contested (active debate), unresolved (insufficient evidence to adjudicate)
5. Explicitly refuses forced resolution: if the evidence does not support a consensus, the output says so

This directly addresses NotebookLM's **table-ification of narrative knowledge** — papers reduced to rows lose their argumentative texture, including disagreements with other papers [06_notebooklm.md](../../critiques/06_notebooklm.md):§4.

### D. Gap Identification

The `GapAnalyzer` operationalizes the concept of **negative knowledge** — what the literature does *not* address [06_notebooklm.md](../../critiques/06_notebooklm.md):§7.

| Gap Type | Detection Method | Example Output |
|----------|-----------------|----------------|
| Coverage insufficiency | Threshold-based: fewer than N papers on subtopic | "This question has only 3 known studies; synthesis confidence is low." |
| Methodological monoculture | Dominance of one study design | "All 12 studies on this topic are observational. No RCT was found." |
| Geographic exclusion | Affiliation analysis of author locations | "The evidence base is 94% Global North. No African or South Asian data." |
| Temporal blind spot | Publication year distribution | "No study on this question was published between 2005 and 2015." |
| Language exclusion | Language tag analysis | "All retrieved papers are in English. Known Chinese-language literature on this topic was not accessed." |

---

## V. Adversarial Curation & Serendipity

### A. Contradiction-Driven Exploration

Where NotebookLM accommodates the user's framing [06_notebooklm.md](../../critiques/06_notebooklm.md):§23, openscire-literature actively disrupts it. The `FalsificationAgent` performs:

- **Assumption mining**: extract the user's implicit assumptions from their query and search history, then search for literature that contradicts each assumption.
- **Counter-evidence surfacing**: for every claim in a synthesis, the agent searches for counter-claims from different research groups, different methodologies, or different theoretical frameworks.
- **Debate reconstruction**: find papers that explicitly cite and critique one another, reconstructing the argumentative structure of the field.

This is structural Popperian design: the system is built to **facilitate falsification**, not just verification. It directly addresses NotebookLM's absence of **hermeneutical suspicion** [06_notebooklm.md](../../critiques/06_notebooklm.md):§6 and missing **Socratic function** [06_notebooklm.md](../../critiques/06_notebooklm.md):§23.

### B. Serendipity Injection

NotebookLM is anti-serendipitous by design — retrieval is always goal-directed, answering the user's query [06_notebooklm.md](../../critiques/06_notebooklm.md):§38. openscire-literature builds serendipity into the architecture:

- **Cross-domain analogy**: when the user asks about Topic X, randomly sample concepts from unrelated fields (configurable probability). "You asked about immunotherapy, but here's something from materials science that uses a similar mechanism."
- **Contradiction-driven tangents**: when a contradiction is detected, the system can propose exploring the minority position further.
- **Configurable serendipity level**: `none` (strictly query-relevant), `low` (occasional tangent), `medium` (one unrelated suggestion per synthesis), `high` (deliberate boundary-crossing).

The serendipity engine cross-references with openscire-hypothesis (Phase 6-7), allowing hypothesis generation to be seeded by unexpected literature connections.

### C. Anti-Echo Chamber Design

Structural constraints that prevent the user from constructing an epistemic echo chamber:

1. **Cannot restrict to self-selected corpus only**: if the user uploads a corpus via Zotero, the system must also include at least one external source (PubMed, arXiv, Semantic Scholar) in the synthesis. The mix ratio is user-configurable but must be >0 external.
2. **Automatic adversarial source inclusion**: the `FalsificationAgent` automatically identifies and includes sources that challenge the dominant finding in the corpus.
3. **Confidence-weighted display**: every finding includes an explicit confidence score (derived from evidence quality assessment), counter-evidence presence, and source diversity metrics. High-certainty claims from a monoculture of sources are displayed with appropriate caveats.

This structurally prevents the **echo chamber effect** [06_notebooklm.md](../../critiques/06_notebooklm.md):§22 and the **confirmation bias amplification** that results from purely user-curated corpora.

---

## VI. Artifact Generation

### A. Structured, Provenance-Traced Reports (NOT Podcasts / Slide-Decks)

openscire-literature **does not generate audio overviews, slide decks, or infographics**. These are deliberately excluded on principle: they treat knowledge as content to be consumed and accelerate the commodification of scientific reading [06_notebooklm.md](../../critiques/06_notebooklm.md):§18, §19, §26.

Instead, openscire-literature produces:

- **Structured research reports** in Markdown (default), with full citation chains linking every claim to its supporting evidence
- **RO-Crate exports** for archiving and sharing with full provenance metadata
- **Jupyter notebook export** for interactive exploration of the synthesis alongside retrieved data
- **PDF export** for institutional reporting, grant applications, and manuscript preparation

### B. Pedagogical Design

Every report is explicitly pedagogical. It documents:

1. **Why sources were selected**: the search strategy, source mix, and inclusion/exclusion criteria
2. **What parameters and strategies were used**: retrieval parameters, embedding model, reranker, serendipity level, evidence quality thresholds
3. **Alternative interpretations**: contradictory findings and unresolved debates are surfaced, not hidden
4. **Self-identified limitations**: the report flags its own epistemic boundaries — "This synthesis is limited to English-language publications," "No RCTs were available for this question," "The evidence base is geographically skewed toward North America"
5. **Uncertainty indicators**: every major claim is accompanied by a confidence indicator rendered as a visual bar or explicit statement

This addresses the **deskilling of literature review** [06_notebooklm.md](../../critiques/06_notebooklm.md):§12, the **commodification of reading** [06_notebooklm.md](../../critiques/06_notebooklm.md):§26, and the **epistemic opacity** of NotebookLM's artifacts [06_notebooklm.md](../../critiques/06_notebooklm.md):§17.

---

## VII. Gap Closure Map

### A. Direct Gaps from critiques/06_notebooklm.md

| Gap Domain | Specific Gap from Critique | § | OpenSciRe Mitigation |
|---|---|---|---|
| Epistemological | Source-grounding as epistemic prison | §1 | Open multi-source engine (PubMed, arXiv, Semantic Scholar, OpenAlex, etc.); automatic external source inclusion; gap identification |
| Epistemological | RAG fragmentation destroys narrative arc | §2 | Narrative-Structure-Preserving DocumentChunker (Phase 5.1); section-aware; citation-anchored splits |
| Epistemological | Confusion of source-grounding with truth | §3 | SourceEnforcer (Phase 5.5) verifies claims against actual source content; EvidenceQualityAssessment |
| Epistemological | Table-ification of narrative knowledge | §4 | Structured reports preserve narrative and argumentative structure; contradiction display; no forced tabular reduction |
| Epistemological | Chat interface as epistemic transactionalism | §5 | No chat-only interface; pedagogical reports explain process; dwelling is supported, not replaced |
| Epistemological | Absence of hermeneutical suspicion | §6 | FalsificationAgent; contradiction detection; funding-source awareness; adversarial curation |
| Epistemological | Loss of the negative space | §7 | GapAnalyzer identifies coverage, methodological, geographic, and temporal gaps |
| Methodological | Missing methodological evaluation layer | §8 | EvidenceQualityAssessment: study design tier, sample size, controls, statistics |
| Methodological | Temporal blindness and retraction amnesia | §9 | RetractionMonitor (Phase 4.9); temporal corpus versioning; chronological metadata; citation chain invalidation |
| Methodological | Inability to track conceptual evolution | §10 | Temporal awareness; concept drift detection; evolution-of-understanding tracking |
| Methodological | Absence of intertextual depth | §11 | CitationContextWindow (Phase 5.3); argumentative lineage reconstruction; contradiction detection |
| Methodological | Deskilling of literature review | §12 | Pedagogical report design; anti-deskilling UI; explains selection, parameters, and limitations |
| Methodological | Chat as substitute for close reading | §13 | Reports link to primary texts; no "chat with your corpus" shortcut that bypasses reading |
| Technical | Context window illusion | §14 | Narrative-preserving chunking preserves document structure; ContextWindowManager (Phase 5.4) with token budget tracking |
| Technical | Hallucination of synthesis (interstitial) | §15 | SourceEnforcer: citation verification + claim cross-check + unsupported claim flagging |
| Technical | Similarity search bias | §16 | Hybrid dense + sparse retrieval (BM25 + embeddings, RRF fusion); multi-source offsets single-corpus bias |
| Technical | Missing citation provenance in artifacts | §17 | Every claim linked to source evidence; RO-Crate export with full provenance DAG |
| Technical | Multimodal artifact superficiality | §18 | No audio/video/slide-deck generation; structured reports with full citation chains; pedagogical design |
| Technical | Audio overview as simulacrum | §19 | Deliberately excluded — see §18 |
| Technical | Environmental cost of content generation | §20 | No artifact generation that requires separate model inference; local-only embedding and retrieval |
| Human-AI | Asymmetry of curatorial labor | §21 | User retains control over source configuration, but automated multi-source bridging reduces curation burden |
| Human-AI | Echo chamber effect | §22 | Anti-echo chamber design: mandatory external source inclusion; adversarial curation; FalsificationAgent |
| Human-AI | Missing Socratic function | §23 | Contradiction detection; alternative viewpoint surfacing; assumption mining; no forced consensus |
| Human-AI | Attribution ambiguity in co-creation | §24 | Full provenance trace; every output documents source of each claim; authorship taxonomy in metadata |
| Human-AI | Interface as cognitive prosthesis | §25 | Pedagogical design assists rather than replaces; anti-deskilling philosophy in UI and report structure |
| Ethical | Commodification of scientific reading | §26 | Knowledge presented as structured argument for capacitation, not consumable content |
| Ethical | Enclosure of the reading process | §27 | Fully local-first; no cloud dependency for core pipeline; open-source Apache 2.0 |
| Ethical | Linguistic imperialism | §28 | Non-English source support (CNKI, SciELO, AJOL, eLibrary.ru); multilingual embeddings; translation-with-uncertainty |
| Ethical | Paywall and access inequality | §29 | Unpaywall bridge for open-access resolution; open-source sources prioritized; no pay-to-synthesize gate |
| Ethical | Acceleration of superficial science | §30 | Mandatory uncertainty display; gap identification; pedagogical reports that resist false consensus |
| Domain | Inability to ingest non-textual science | §31 | PDF parser extracts figure/table captions with proximity preservation; code/math block preservation |
| Domain | Code and data repository blindness | §32 | Integration with openscire-sandbox for computational reproducibility; GitHub bridge (future) |
| Domain | Static corpus problem | §33 | RetractionMonitor for live updates; incremental sync for reference managers; corpus versioning |
| Domain | Inability to handle mathematical formalism | §34 | LaTeX-aware chunking; math/code block preservation; equations kept intact in chunks |
| Temporal | Speed-bias, loss of incubation | §35 | Mandatory uncertainty display; no "quick answer" mode; deliberate structural friction via EvidenceQualityAssessment |
| Temporal | Missing longitudinal reading memory | §36 | Provenance DAG logs all queries with timestamps; user intellectual history preserved locally |
| Temporal | Absence of reading as ritual | §37 | Cannot replace reading — structured reports link to primary texts; pedagogical design preserves the reader's relationship to text |
| Comparative | Missing serendipitous discovery | §38 | SerendipityInjector with configurable level; cross-domain analogy; contradiction-driven exploration |
| Comparative | Lack of embodied judgment | §39 | EvidenceQualityAssessment provides structural judgment, though tacit/olfactory judgment remains human domain |
| Comparative | Inability to read against the grain | §40 | FalsificationAgent; adversarial curation; ideology-critique capability through contradiction surfacing |
| Comparative | Missing negative capability in synthesis | §41 | GapAnalyzer refuses synthesis when evidence is insufficient or contradictory; explicit "no consensus possible" output |
| Meta-Gaps | Category error of "Literature Insights" | §42 | Provides rearrangement and gap/silence identification; output labeled as synthesis with caveats, not "insight" |
| Meta-Gaps | Ontological confusion of grounding | §43 | SourceEnforcer cross-checks claims against actual source content; grounding = verification, not containment |
| Meta-Gaps | Absence of "stop" mechanism | §44 | GapAnalyzer and NegativeCapabilityEnforcer refuse false consensus; synthesis blocked on insufficient evidence |
| Meta-Gaps | Consumption ≠ understanding | §45 | Outputs designed for capacitation, not consumption; pedagogical design; no audio/video artifacts |

### B. Cross-Cutting Gaps from Other Critiques

| Gap Domain | Critique Source | OpenSciRe Mitigation |
|---|---|---|
| Epistemology: conflation of synthesis with understanding | [02_philosophy.md](../../critiques/02_philosophy.md):§1 | EvidenceQualityAssessment preserves know-that vs. know-how distinction; tacit knowledge respected as human domain |
| Epistemology: Gettier problem (true belief with false justification) | [02_philosophy.md](../../critiques/02_philosophy.md):§1 | SourceEnforcer cross-checks specific claims against actual source content, not just citation presence |
| Epistemology: situated knowledge, Harawayan objectivity | [02_philosophy.md](../../critiques/02_philosophy.md):§1 | Geographic and language coverage gap analysis; source diversity metrics |
| Epistemology: no theory of scientific judgment (phronesis) | [02_philosophy.md](../../critiques/02_philosophy.md):§1 | EvidenceQualityAssessment provides structured judgment support; human remains the ultimate judge |
| Ontology: computational reduction of being | [02_philosophy.md](../../critiques/02_philosophy.md):§2 | Gap identification preserves non-computable dimensions of scientific questions |
| Ontology: agent ontology fallacy | [02_philosophy.md](../../critiques/02_philosophy.md):§2 | Tool is named "engine," not "co-scientist"; UI avoids anthropomorphization |
| Phenomenology: erasure of productive struggle | [02_philosophy.md](../../critiques/02_philosophy.md):§3 | Pedagogical reports preserve the labor of selection and evaluation; anti-deskilling philosophy |
| Hermeneutics: violence of structured synthesis | [02_philosophy.md](../../critiques/02_philosophy.md):§6 | Contradiction surfacing preserves incommensurability; no forced tabular reduction |
| Philosophy of science: verificationism, not falsification | [02_philosophy.md](../../critiques/02_philosophy.md):§7 | FalsificationAgent actively searches for counter-evidence; Popperian design |
| Philosophy of science: algorithmic fossilization of method | [02_philosophy.md](../../critiques/02_philosophy.md):§7 | Gap identification preserves methodological pluralism; serendipity injects unoptimized discovery |
| Philosophy of science: missing null result mechanism | [02_philosophy.md](../../critiques/02_philosophy.md):§7 | Negative result registry; NullResultArchiver; contradiction detection |
| Philosophy of technology: Gestell / enframing | [02_philosophy.md](../../critiques/02_philosophy.md):§11 | Local-first, open-source architecture resists platform enclosure; pedagogical design resists commodification |
| Structural: linear pipeline fallacy | [03_structural_triad.md](../../critiques/03_structural_triad.md):§1 | Cyclical architecture with feedback to openscire-hypothesis; retraction cascade updates previous syntheses |
| Structural: missing problem-formation stage | [03_structural_triad.md](../../critiques/03_structural_triad.md):§2 | GapAnalyzer identifies open questions and anomalies from literature |
| Structural: missing validation/replication stage | [03_structural_triad.md](../../critiques/03_structural_triad.md):§3 | Citation chain invalidation; retraction monitoring; EvidenceQualityAssessment |
| Structural: data/instrumentation layer absence | [03_structural_triad.md](../../critiques/03_structural_triad.md):§6 | Provenance DAG logs all retrievals; PDF parser extracts structured metadata |
| Structural: missing social/collaborative architecture | [03_structural_triad.md](../../critiques/03_structural_triad.md):§7 | RO-Crate export for sharing; shared provenance DAG (team mode in future phase) |
| Structural: no meta-scientific reflexive layer | [03_structural_triad.md](../../critiques/03_structural_triad.md):§9 | Self-critique in every report: limitations are surfaced, parameters explained |
| Legal/IP: attribution bankruptcy of AI synthesis | [08_miscellaneous.md](../../critiques/08_miscellaneous.md):§4 | Full provenance chain linking every claim to sources; RO-Crate for archival attribution |
| Security: supply chain attack surface | [08_miscellaneous.md](../../critiques/08_miscellaneous.md):§7 | Local-only embedding; no external API dependency for core pipeline; cryptographic verification of DB integrity (future) |
| Security: unpublished data exposure | [08_miscellaneous.md](../../critiques/08_miscellaneous.md):§5 | Fully local-first architecture; no data sent to external servers; user controls data retention |
| Governance: FDA/EMA regulatory chasm | [08_miscellaneous.md](../../critiques/08_miscellaneous.md):§9 | EvidenceQualityAssessment flags non-FDA-validated claims; RiskTier classification (Phase 3.2) |
| Governance: no "Hippocratic Oath" for AI science tools | [08_miscellaneous.md](../../critiques/08_miscellaneous.md):§50 | EthicalFirewall (Phase 3.1) with DURC detection; audit-trail provenance of all firewall decisions |
| Governance: no "slow science" mode | [08_miscellaneous.md](../../critiques/08_miscellaneous.md):§52 | No "quick answer" mode; mandatory evidence quality review; configurable cooling-off period for high-risk queries |
| Sustainability: freemium cliff / missing middle | [08_miscellaneous.md](../../critiques/08_miscellaneous.md):§13 | Fully open-source Apache 2.0; no feature gate between academic and enterprise; self-hostable on commodity hardware |
| Sustainability: grant budget inflation | [08_miscellaneous.md](../../critiques/08_miscellaneous.md):§14 | No API costs for core pipeline; local embedding models; no cloud dependency |
| Sustainability: maintenance funding crisis | [08_miscellaneous.md](../../critiques/08_miscellaneous.md):§15 | Open-source with community governance model; BYOK managed cloud as sustainability layer (per business brief) |
| Education: PhD curriculum obsolescence | [08_miscellaneous.md](../../critiques/08_miscellaneous.md):§16 | Pedagogical design teaches selection and evaluation; does not automate judgment away |
| Education: disappearance of methodological apprenticeship | [08_miscellaneous.md](../../critiques/08_miscellaneous.md):§17 | Reports explain methodology choices; anti-deskilling by design |
| UX: non-coder scientist exclusion | [08_miscellaneous.md](../../critiques/08_miscellaneous.md):§19 | CLI + Python API + planned GUI; zero-code configuration for common operations |
| UX: field science offline requirement | [08_miscellaneous.md](../../critiques/08_miscellaneous.md):§21 | Fully offline-first architecture; local embedding and retrieval; no internet required for core operation |
| FAIR: anti-FAIR by architecture | [08_miscellaneous.md](../../critiques/08_miscellaneous.md):§23 | RO-Crate export; W3C PROV-compatible provenance; open Markdown output; Zenodo/Figshare export bridges (future) |
| FAIR: missing provenance standard | [08_miscellaneous.md](../../critiques/08_miscellaneous.md):§26 | RO-Crate as default export; full provenance DAG in structured metadata |
| Systemic: research agenda homogenization | [08_miscellaneous.md](../../critiques/08_miscellaneous.md):§36 | SerendipityInjector; cross-domain analogy; contradiction-driven exploration resists monoculture |
| Systemic: catastrophic discovery acceleration | [08_miscellaneous.md](../../critiques/08_miscellaneous.md):§37 | RiskTier classification (Phase 3.2); mandatory human checkpoint for high-risk domains (Phase 3.1) |
| Cognitive: automation bias | [08_miscellaneous.md](../../critiques/08_miscellaneous.md):§39 | SourceEnforcer modes provide deliberate friction; manual verification steps for high-stakes queries |
| Cognitive: decision fatigue from option overload | [08_miscellaneous.md](../../critiques/08_miscellaneous.md):§40 | Progressive disclosure of evidence quality; tiered confidence thresholds |
| Cognitive: moral crumple zone | [08_miscellaneous.md](../../critiques/08_miscellaneous.md):§41 | Every output clearly marked as AI-generated; human judgment is structurally required for all conclusions |
| Geopolitical: AI science tools as strategic assets | [08_miscellaneous.md](../../critiques/08_miscellaneous.md):§33 | Fully local-first; no data sovereignty compromise; model weights distributed for sovereign hosting |
| Geopolitical: brain drain acceleration | [08_miscellaneous.md](../../critiques/08_miscellaneous.md):§34 | Local-first means data stays on user's hardware; no IP extraction through cloud processing |
| Meta: no philosophy of limits | [02_philosophy.md](../../critiques/02_philosophy.md):Meta-Gap §1 | NegativeCapabilityEnforcer; refusal to synthesize on insufficient evidence; configurable epistemic limits |
| Meta: confusion of scale with depth | [02_philosophy.md](../../critiques/02_philosophy.md):Meta-Gap §2 | Pedagogical design prioritizes depth of understanding over breadth of artifacts |
| Meta: substitution of process for wisdom | [02_philosophy.md](../../critiques/02_philosophy.md):Meta-Gap §3 | Human remains the final epistemic authority; tool supports, does not replace, judgment |

---

## VIII. Data Models & Architecture

### A. Core Data Models

```python
@dataclass
class Document:
    id: str                          # UUID or content-addressable hash
    source: str                      # "pubmed", "arxiv", "zotero", etc.
    source_id: str                   # PMID, arXiv ID, Zotero item key, etc.
    title: str
    authors: list[Author]
    abstract: str | None
    full_text: str | None
    language: str                    # ISO 639-1 code
    metadata: dict                   # Journal, DOI, PMID, MeSH, keywords, etc.
    retrieval_date: datetime
    embedding_model: str | None      # Which model was used for chunk embeddings
    ingestion_version: int           # Incremented on re-ingestion (e.g., after retraction)
    is_retracted: bool
    retraction_events: list[RetractionEvent]

@dataclass
class Chunk:
    id: str                          # UUID
    document_id: str
    section: str                     # "Introduction", "Methods", "Results", "Discussion", "Conclusion", "Abstract", "Other"
    subsection: str | None
    text: str
    citations: list[str]             # Normalized citation keys
    position: int                    # Sequential position within document
    paragraph_index: int
    token_count: int
    embeddings: list[float] | None
    parent_chunk_id: str | None      # For hierarchical chunking (parent = larger context)

@dataclass
class Citation:
    claim: str                       # The specific claim the citation supports
    source_document: str             # Document ID
    source_chunk: str                # Chunk ID
    supporting_text: str             # The actual text supporting the claim
    confidence: float                # 0.0 – 1.0 (based on EvidenceQualityAssessment)
    verification_status: str         # "verified", "contested", "retracted", "unverifiable"
    verification_date: datetime

@dataclass
class Contradiction:
    id: str
    claim_a: Claim
    claim_b: Claim
    supporting_evidence_a: list[str] # Chunk IDs
    supporting_evidence_b: list[str]
    resolution_status: str           # "resolved", "contested", "unresolved", "incommensurable"
    resolution_date: datetime | None
    methodology_difference: str | None  # If contradiction stems from different methods

@dataclass
class RetractionEvent:
    paper_id: str
    retraction_date: datetime
    notice_url: str
    event_type: str                  # "retraction", "correction", "expression_of_concern", "reinstatement"
    reason: str | None
    affected_artifacts: list[str]    # IDs of all syntheses, reports, etc. that cited this paper
```

### B. Retrieval Architecture

```
User Query
    │
    ▼
Query Decomposition + Expansion
    │
    ├──► Source Adapter Dispatcher
    │       ├──► PubMedAdapter ──► E-utilities API ──► Result Stream
    │       ├──► ArXivAdapter ───► API v2 ──────────► Result Stream
    │       ├──► SemanticScholarAdapter ──► REST API ──► Result Stream
    │       ├──► OpenAlexAdapter ──► REST API ──► Result Stream
    │       ├──► ZoteroAdapter ──► OAuth2 ──► Local Cache
    │       └──► ... (remaining adapters)
    │
    ▼
Result Deduplication (DOI, PMID, title fuzzy match)
    │
    ▼
Document Fetching (full text from OA sources, PDF parsing)
    │
    ▼
Narrative-Structure-Preserving Chunking
    │
    ▼
Embedding (local sentence-transformers) + BM25 Indexing
    │
    ▼
Hybrid Retrieval (dense FAISS + sparse BM25 → RRF fusion)
    │
    ▼
Cross-Encoder Reranking
    │
    ▼
SourceEnforcer Verification
    │
    ▼
Response (Structured Report / Synthesis)
```

### C. Integration with Other Components

| Component | Interface | Data Flow |
|-----------|-----------|-----------|
| openscire-hypothesis | `LiteratureSynthesis` → `HypothesisAgent` | Literature synthesis and gap identification seed hypothesis generation; contradiction maps inform hypothesis testing |
| openscire-sandbox | `ExistingKnowledgeContext` | Computational results from sandbox are contextualized against retrieved literature; literature claims can be flagged for computational validation |
| Provenance DAG | `ProvenanceEvent` | All retrievals, chunkings, embeddings, and syntheses logged with timestamps, model versions, parameters, and source selection criteria |
| EthicalFirewall (Phase 3) | `RiskTier.Query` | Literature queries in high-risk domains (DURC) trigger additional review gates and tier-appropriate processing |
| CarbonBudgetTracker (Phase 3) | `CarbonEvent` | Compute for embeddings, retrieval, and generation tracked per operation and reported in provenance |

---

## IX. Implementation Roadmap

### Phase 4: Literature Engine (Current — see [Phase 4 tasks](../../docs/phases/04_literature_engine.md))

| Component | Weeks | Dependencies | Deliverable |
|-----------|-------|-------------|-------------|
| Reference manager bridges (Zotero, Mendeley) | 2 | None | OAuth2 auth, collection sync, item retrieval |
| PubMed/PMC bridge | 1 | None | E-utilities search, fetch, abstract + full text |
| arXiv bridge | 1 | None | API v2 search, bulk download, LaTeX parsing |
| Semantic Scholar bridge | 1 | None | Citation graph traversal, recommendations |
| OpenAlex bridge | 0.5 | None | Open API search, concept tagging |
| Unpaywall bridge | 0.5 | None | DOI → OA resolution |
| Non-English sources (CNKI, SciELO, etc.) | 2 | None | Metadata search, multilingual embedding support |
| RetractionMonitor | 1.5 | None | PubMed Retraction Watch, Crossref, PubPeer polling |
| PDF parser | 1.5 | None | Section extraction, reference list parsing, LaTeX handling |
| Local embedding index | 1 | None | FAISS/Chroma/SQLite-vss abstraction, incremental indexing |
| Citation graph analyzer | 1.5 | Embedding index | Traversal, influence scoring, clustering |
| Gap analyzer | 1 | RetractionMonitor + CitationGraph | Coverage, methodological, geographic gap detection |
| Tests | 1 | All above | Unit + integration test suites |

**Phase 4 exit criteria**: Can search PubMed, arXiv, Semantic Scholar. Can import Zotero collection. PDFs parsed and embedded locally. RetractionMonitor flags retracted papers. Non-English metadata search works for at least one non-English source.

### Phase 5: RAG Architecture (Current — see [Phase 5 tasks](../../docs/phases/05_rag.md))

| Component | Weeks | Dependencies | Deliverable |
|-----------|-------|-------------|-------------|
| Narrative-Structure-Preserving DocumentChunker | 2 | Phase 4 PDF parser | Section-aware, citation-anchored, list-preserving chunking |
| HybridRetriever (dense + sparse + RRF) | 1.5 | Phase 4 embedding index | BM25 + embedding fusion, cross-encoder reranking |
| CitationContextWindow | 1 | HybridRetriever | Citation neighborhood retrieval, contradiction flagging |
| ContextWindowManager | 1 | CitationContextWindow | Token budget, priority inclusion, structured context packaging |
| SourceEnforcer | 2 | ContextWindowManager | Three enforcement modes, citation verification, cross-check |
| CitationFormatter | 0.5 | None | All major citation styles, reference list generation |
| Tests | 1 | All above | Unit + integration test suites |

**Phase 5 exit criteria**: RAG pipeline end-to-end: chunk paper → search query → retrieve chunks → cite sources → enforce citations. All citation styles formatted correctly.

### Phase 6–7: Integration with openscire-hypothesis

| Component | Timeline | Deliverable |
|-----------|----------|-------------|
| Literature → hypothesis seeding | Phase 6 | Gap identification feeds HypothesisAgent |
| Contradiction maps → hypothesis testing | Phase 6 | ContradictionDetector outputs seed falsification strategies |
| Provenance DAG unification | Phase 7 | Shared provenance across all three engines |
| Cross-domain serendipity → hypothesis generation | Phase 7 | SerendipityInjector outputs seed cross-domain analogies |

---

## X. Competitive Context

### vs. Google NotebookLM

| Dimension | NotebookLM | openscire-literature |
|-----------|-----------|---------------------|
| Source scope | User-upload only | Multi-source open corpus + user library |
| Corpus model | Closed epistemic universe | Open, with gap detection |
| Chunking | Context-window-optimized, architecture opaque | Narrative-structure-preserving, citation-anchored |
| Methodology evaluation | None | EvidenceQualityAssessment (6 dimensions) |
| Temporal awareness | Synchronic snapshot | RetractionMonitor, corpus versioning, evolution tracking |
| Echo chamber | Structural — no adversarial input | Anti-echo chamber by design; mandatory external sources |
| Contradiction | Smoothed over or invisible | Structural surfacing with resolution status |
| Serendipity | None (goal-directed only) | Configurable SerendipityInjector |
| Artifact type | Podcasts, slides, infographics | Structured reports with full provenance |
| Pedagogical design | None — consumable artifacts | Self-limiting, self-explaining reports |
| Architecture | Cloud-only, API-dependent | Fully local-first, offline-capable |
| License | Proprietary | Apache 2.0 |

### vs. Elicit / Scite / Consensus

| Dimension | Elicit / Scite / Consensus | openscire-literature |
|-----------|---------------------------|---------------------|
| Core function | Standalone literature search + keyword extraction | Full synthesis + contradiction detection + adversarial curation |
| RAG approach | Standard chunking for Q&A | Narrative-preserving chunking with citation anchoring |
| Retraction awareness | Limited (Scite tracks corrections) | Full RetractionMonitor with citation chain invalidation |
| Serendipity | None | Configurable cross-domain serendipity |
| Hypothesis integration | Standalone | Feeds directly into openscire-hypothesis engine |
| Provenance | Citation list | Full provenance DAG with RO-Crate export |
| Local-first | No (cloud APIs) | Yes (fully local embedding, retrieval, generation) |
| Open source | No (proprietary) | Apache 2.0 |

### vs. Traditional Literature Review Tools (Zotero, Mendeley)

openscire-literature is not a reference manager replacement — it interfaces *with* reference managers as data sources. It is an AI-assisted layer on top that provides synthesis, contradiction detection, gap analysis, and retraction awareness. Users maintain their existing Zotero or Mendeley libraries; openscire-literature reads from them, enhances them with multi-source bridging, and returns structured syntheses that can be re-imported.

---

## XI. Limitations Acknowledged

Consistent with OpenSciRe's fiduciary posture and the imperative of epistemic humility [AGENTS.md](../../AGENTS.md), the following limitations are explicitly documented:

1. **Non-English source quality varies by region.** CNKI and Wanfang have substantial coverage depth but the quality and granularity of metadata varies. AJOL's coverage is growing but incomplete. Multilingual embedding models (LaBSE, BGE-M3) improve cross-lingual retrieval but are still English-dominant in their training distributions.

2. **Full PDF text analysis limited by paywalls.** Unpaywall resolves ~40% of DOIs to open-access versions. For paywalled content, openscire-literature uses abstracts and metadata only, with a quality-availability tradeoff displayed to the user. There is no Sci-Hub integration — this is a deliberate architectural boundary to avoid legal exposure.

3. **Temporal corpus versioning is deferred to later phases.** The initial implementation treats the index as append-only with retraction flags. Full rollback queries ("what did we know in March 2024?") and cross-version synthesis comparison will require a temporal index architecture that is not yet implemented.

4. **Cross-lingual synthesis is experimental.** Translating findings for comparison across languages is inherently lossy. openscire-literature's translation-with-uncertainty model flags confidence levels, but deep semantic equivalence across languages and disciplinary registers cannot be guaranteed. This is a research limitation, not a fixable bug.

5. **Mathematical reasoning across papers is not attempted.** While LaTeX blocks are preserved in chunking, openscire-literature does not perform symbolic mathematical reasoning across papers. It cannot check whether a theorem in one paper contradicts a lemma in another at the formal level. This remains an open AI research problem.

6. **The FalsificationAgent is limited to literature-based contradiction.** It can surface conflicting findings and missing evidence, but it cannot detect experimental fraud, p-hacking, or methodological misconduct that has not been identified in subsequent literature. The "olfactory sense for quality" of an experienced scientist — the ability to "smell" a bad paper — remains irreducibly human [06_notebooklm.md](../../critiques/06_notebooklm.md):§39.

7. **No cross-modal reasoning.** openscire-literature processes text and text-adjacent content (captions, tables-as-text). It does not reason over images, gel electrophoresis results, microscope slides, or instrument readouts. This is partially addressed by figure/table caption proximity preservation but not by actual vision-language understanding.

8. **Serendipity cannot be forced.** The SerendipityInjector increases the probability of unexpected connections but cannot guarantee them. By definition, engineered serendipity risks becoming predictable. The "aha" moment — the genuinely transformative unexpected insight — remains an emergent property of human cognition that can be facilitated but not manufactured [06_notebooklm.md](../../critiques/06_notebooklm.md):§38.

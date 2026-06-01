# openscire-bio — Open-Source Life Science Database Integration with Ontological Transparency and Confidence Propagation

## I. Overview & Motivation

### What openscire-bio Is

openscire-bio is OpenSciRe's life science database integration layer — a set of open-source, per-database bridge adapters that provide transparent access to UniProt, AlphaFold DB, PDB, InterPro, NCBI, and other public bioinformatics databases. Unlike existing integration approaches that flatten heterogeneous biological data into a single queryable plane, openscire-bio preserves each source's native ontology, propagates confidence scores through multi-step analyses, documents every join condition, and explicitly labels predicted versus experimental data. It is designed to be local-first, cache-aware, and verifiably reproducible.

This component is the domain-specific extension of the OpenSciRe literature engine (`openscire-literature`, documented in [Phase 4](../../docs/phases/04_literature_engine.md)) — extending it from unstructured text (papers, preprints) into structured bioinformatics data (sequences, structures, domains, annotations). It feeds into `openscire-hypothesis` for hypothesis generation informed by real (and honestly-labeled predicted) biological data, and it integrates with the provenance DAG to ensure every query, join, and analysis step is auditable.

### Why It Exists — The Science Skills Vacuum

At Google I/O 2026, Google launched **Science Skills** — a specialized bundle integrating "over 30 major life science databases and tools" into Gemini for Science, available on Google Antigravity and GitHub. The pitch: "perform complex workflows like structural bioinformatics and genomic analyses in minutes rather than hours." [01_overview.md](../../critiques/01_overview.md)

The critique in [07_science_skills.md](../../critiques/07_science_skills.md) excavates **48 distinct gaps** in Science Skills, organized across ten domains. The most critical failures are structural, not cosmetic:

1. **Database-bound ontological reductionism**: Science Skills flattens sequence, structure, function, and evolution into a single commensurable plane, erasing the profound methodological tensions between them. A UniProt sequence annotation, an AlphaFold predicted structure, and an InterPro domain classification are treated as interchangeable data layers in a unified query space. This is not integration — it is ontological violence. [07_science_skills.md §I.1](../../critiques/07_science_skills.md)

2. **Prediction-reality ontological confusion**: AlphaFold structures are prediction repositories, not empirical measurements. Science Skills treats them as interchangeable with experimental PDB structures, dissolving the distinction between model and nature. When a predicted structure (pLDDT confidence scores and all) flows into a binding site analysis without carrying its uncertainty, the researcher receives a synthesis that looks empirical but is statistical. [07_science_skills.md §I.2](../../critiques/07_science_skills.md)

3. **Black-box integration logic**: The joins between 30+ databases — the conditions, conflict-resolution rules, and confidence weighting between sources — are proprietary and opaque. The user sees a unified output but cannot audit how the system resolved contradictory annotations, which cross-references it used, or whether it silently dropped conflicting data. [07_science_skills.md §III.13](../../critiques/07_science_skills.md)

4. **No confidence propagation**: AlphaFold's pLDDT (per-residue confidence) scores are the single most important uncertainty signal in structural bioinformatics. Science Skills uses predicted structures in downstream analyses without propagating these scores. The results appear definitive while being probabilistically fragile. [07_science_skills.md §IV.17](../../critiques/07_science_skills.md)

5. **No provenance, no replication**: Results are temporally unmoored — which database version, which query parameters, which integration logic? Without automated replication packaging, the tool produces irreproducible bioinformatics at scale. [07_science_skills.md §VII.36](../../critiques/07_science_skills.md)

6. **No experimental validation bridge**: The entire system operates in silico. Predicted structures, functional annotations, and genomic analyses are presented as "scientific findings" with no structural pathway to close the loop from in silico prediction to bench verification. [07_science_skills.md §II.7](../../critiques/07_science_skills.md)

These are not edge cases. They are architectural defaults. Science Skills is a database integration layer pretending to be a scientific instrument — it queries fast, synthesizes fluently, and sounds authoritative, but it has no judgment about data quality, no methodological awareness, no uncertainty propagation, and no mechanism to refuse analysis when the data is too sparse or the question requires experimental work. [07_science_skills.md §Synthesis](../../critiques/07_science_skills.md)

### The Core Inversion

openscire-bio inverts every one of these defaults:

- **Per-database bridges** preserve each source's native ontology. Flattening is always explicit, never implicit — and it is documented when it occurs.
- **Confidence propagation** is baked into the data model. pLDDT scores, resolution values, and evidence types flow through every downstream operation. They cannot be stripped.
- **Transparent join logic** means every cross-database query documents what fields were joined, how, and with what assumptions. The code is open source. There is no black box.
- **Explicit prediction vs. experiment labeling** on every data point. Predicted structures are labeled P, experimental structures labeled E, curated annotations labeled R. This label propagates. It cannot be hidden.
- **Graceful degradation**: If UniProt is down, the other bridges continue working. Partial results are labeled as partial. The user knows exactly what they are missing.
- **Local caching and reproducibility**: Every query records which database version, which parameters, and which timestamp. ReproducibilityBundles include version snapshots.

### How It Fits Into OpenSciRe

openscire-bio is not a standalone tool. It is a domain-specific extension of the broader OpenSciRe ecosystem:

- **openscire-literature** (Phase 4): The literature engine provides source adapters for PubMed, arXiv, Zotero, Semantic Scholar, and non-English corpora. openscire-bio adds structured bioinformatics source adapters alongside these, sharing the same adapter pattern architecture. A researcher can ask "find papers about AK2 and retrieve its UniProt annotations and AlphaFold structure" as a single cross-source query. [04_literature_engine.md](../../docs/phases/04_literature_engine.md)

- **openscire-hypothesis** (Phase 5): Hypothesis generation in OpenSciRe is grounded in real data, not just literature patterns. openscire-bio provides the biological evidence layer — actual sequences, actual (or honestly labeled predicted) structures, actual domain annotations — for hypotheses to build upon. When openscire-hypothesis proposes a binding mechanism, it can cite the specific pLDDT confidence across the binding interface.

- **Provenance DAG**: Every bridge query, every join, every confidence score is recorded in the provenance DAG. This enables full reproducibility and auditability — the same standard OpenSciRe applies to literature queries applies to bioinformatics queries.

- **Ethics layer** (Phase 3): The DataSovereigntyChecker, UncertaintyQuantifier, and SourceGrounding modules from the ethics layer apply to bioinformatics data too. Indigenous genomic data in public databases is flagged. Prediction confidence is surfaced. Claims without experimental backing are labeled as such. [03_ethics_layer.md](../../docs/phases/03_ethics_layer.md)

---

## II. Bridge Architecture

### A. Design Principles

1. **Per-database bridges preserve native ontology**: Each bridge speaks the source's own data model. UniProt returns UniProt records with UniProt fields. AlphaFold DB returns predicted structures with pLDDT scores. PDB returns experimental structures with resolution metrics. No implicit flattening. If a downstream analysis requires flattening (e.g., "give me the sequence, structure, and domain annotations for this protein in one table"), the flattening is an explicit operation documented in the query provenance.

2. **Transparent join logic**: Every cross-database query produces a join manifest documenting: which fields were used as join keys, what cross-reference method (exact ID match, sequence similarity, SIFTS mapping), what conflict-resolution rules were applied, and what data was dropped due to missing cross-references. This manifest is a first-class output, not debug logging.

3. **Confidence propagation**: All confidence signals (pLDDT, PAE, resolution, E-value, bitscore, annotation quality flags) are attached to data fields and propagate through operations. Aggregation operations produce confidence distributions, not just point estimates. No confidence signal is ever silently dropped.

4. **Graceful degradation**: Each bridge operates independently. A failure in one bridge does not cascade to others. When a source is unavailable, the system returns results from available bridges with a clear indication of what is missing. Partial results are labeled as partial.

5. **Local caching**: Frequently accessed data is cached locally (SQLite-backed, configurable TTL) to reduce API load, improve response times, and enable basic offline operation for cached data. Cache staleness is tracked and reported.

6. **Version transparency**: Every query records which database release version was used. When a database is updated (UniProt releases monthly, AlphaFold DB expands with new proteomes), the version string changes. Users can compare results across versions.

7. **Open-source bridge code**: Every bridge is implemented in open-source Python, available for audit, fork, and contribution. There is no proprietary middleware. The integration logic is community-verifiable.

### B. Core Bridges (MVP)

#### 1. UniProt Bridge

- **Source**: UniProt REST API (SPARQL, UniProtKB retrieval)
- **Retrieval types**: Protein sequences (canonical and isoforms), curated annotations (function, subcellular location, post-translational modifications), GO terms, cross-references to other databases, keywords, and literature citations
- **Key design decisions**:
  - Returns full UniProt records preserving the native taxonomy (accession, entry name, protein names, gene names, organism, sequence, features, cross-refs)
  - Query construction is transparent: the user sees which UniProt fields are being queried (e.g., "retrieving: accession, sequence, GO terms, PDB cross-refs from UniProtKB/Swiss-Prot review status")
  - Annotations are labeled by evidence type: experimental (ECO:0000269), curatorial (ECO:0000305), computational (ECO:0000250), etc.
  - Version tracking: records the UniProt release string (e.g., "2025_04") in provenance
  - Rate limiting: respects UniProt's rate limits (3 requests/second without API key, higher with) with automatic backoff and retry

- **Data model**:

```
DatabaseRecord(
    source_database="uniprot",
    native_id="P30085",          # UniProt accession
    data_fields={
        "sequence": "MKGL...",
        "protein_name": "Adenylate kinase 2, mitochondrial",
        "gene_name": "AK2",
        "organism": "Homo sapiens",
        "features": [...],
        "go_terms": [...],
    },
    retrieval_date="2026-06-01",
    version="UniProtKB 2025_04",
    confidence_score=1.0,        # Swiss-Prot reviewed: highest curated confidence
    evidence_type="R",           # Reviewed/curated
)
```

- **Provenance output per query**:
  - Source: UniProt REST API v2025_04
  - Query parameters: accession=P30085, fields=accession,sequence,organism,go_id,feature
  - Cross-references returned: PDB (3J1Q, 3N5U), InterPro (IPR000694), Pfam (PF00406)
  - Retrieved at: 2026-06-01T14:30:00Z

#### 2. AlphaFold DB Bridge

- **Source**: AlphaFold Database API (EMBL-EBI)
- **Retrieval types**: Predicted protein structures (CIF format), pLDDT confidence scores (per-residue), PAE (predicted aligned error) matrices
- **CRITICAL DESIGN REQUIREMENTS**:
  - Every predicted structure is **explicitly labeled as predicted (P)**, not experimental. This label cannot be stripped in downstream operations. It is part of the data model.
  - pLDDT scores are **never dropped**. They are attached to each residue position and propagate through any operation that uses residue-level data (binding site analysis, domain mapping, structure comparisons).
  - The bridge surfaces AlphaFold's own caveats: "This is a predicted structure. Intrinsically disordered regions (IDRs) may be misrepresented. See pLDDT reliability per residue."
  - When a protein has both an AlphaFold prediction and an experimental PDB structure, both are returned with their respective labels. The user chooses — or the system defaults to the experimental version with a note.
  - Model version is tracked (e.g., "AlphaFold v4"), since model updates can significantly change predictions.

- **Data model**:

```
DatabaseRecord(
    source_database="alphafold_db",
    native_id="AF-P30085-F1",
    data_fields={
        "structure": <cif_data>,
        "plddt_scores": {1: 0.95, 2: 0.93, ..., 200: 0.45, ...},
        "pae_matrix": [[...]],
        "coverage": "1-233",
        "model_version": "AlphaFold v4",
    },
    retrieval_date="2026-06-01",
    version="AlphaFold DB 2025_03",
    confidence_score=0.73,       # Mean pLDDT across the structure
    evidence_type="P",           # Predicted (NOT experimental)
)
```

- **Knowledge boundary flagging**: Intrinsically disordered regions (pLDDT < 0.5) are flagged explicitly. The system knows what AlphaFold is bad at and says so. [07_science_skills.md §IV.18](../../critiques/07_science_skills.md)

#### 3. PDB (Protein Data Bank) Bridge

- **Source**: RCSB PDB API (RESTful, GraphQL)
- **Retrieval types**: Experimentally determined structures (X-ray crystallography, NMR, cryo-EM), experimental metadata (resolution, R-factor, method, deposition date), ligand information
- **Key design decisions**:
  - Labeled **experimental (E)** — the default for trusted structural biology
  - Resolution and method surfaced explicitly: "Method: X-ray diffraction, Resolution: 2.3 Å"
  - Quality flags: "This structure contains missing residues (residues 145-167 not modeled)"
  - Preferentially returned over AlphaFold when both exist, unless the user explicitly requests predicted
  - Cross-references to UniProt via SIFTS mapping with currency

- **Data model**:

```
DatabaseRecord(
    source_database="pdb",
    native_id="3J1Q",
    data_fields={
        "structure": <mmcif_data>,
        "method": "X-ray diffraction",
        "resolution": 2.3,
        "r_free": 0.22,
        "deposition_date": "2022-03-15",
        "missing_residues": [145, 167],
        "ligands": ["ATP", "MG"],
    },
    retrieval_date="2026-06-01",
    version="PDB 2025_12",
    confidence_score=0.85,       # Based on resolution (2.3Å = good but not atomic)
    evidence_type="E",           # Experimental
)
```

#### 4. NCBI / Entrez Bridge

- **Source**: NCBI E-utilities API
- **Retrieval types**: Nucleotide sequences (GenBank), complete genomes (RefSeq), taxonomy (NCBI Taxonomy), SRA metadata, PubMed cross-references
- **Key design decisions**:
  - Cross-referencing with literature: PMIDs are extracted from NCBI records and linked to the literature engine's PubMed bridge
  - Taxonomy queries support the full NCBI taxonomy tree (not just model organisms)
  - Genome assembly versions tracked explicitly
  - Rate limiting with NCBI's 3-requests-per-second default, plus API key support for higher limits

- **Data model**:

```
DatabaseRecord(
    source_database="ncbi_nucleotide",
    native_id="NC_000007.14",
    data_fields={
        "sequence": "AACTGG...",
        "organism": "Homo sapiens",
        "chromosome": "7",
        "gene_ids": ["AK2", "302"],
        "annotation_release": "109.20211119",
        "assembly": "GRCh38.p14",
    },
    retrieval_date="2026-06-01",
    version="GenBank 2025_06",
    confidence_score=0.95,
    evidence_type="R",           # Reviewed (RefSeq)
)
```

#### 5. InterPro Bridge

- **Source**: InterPro REST API (EBI)
- **Retrieval types**: Protein families, domains, repeats, conserved sites, active sites, and their functional descriptions
- **Key design decisions**:
  - Integration with UniProt data: InterPro annotations are joined to UniProt accessions via the UniProt bridge
  - Domain-level analysis: each domain returned with its own coordinates, signature matches, and confidence
  - Multiple signature databases collapsed into InterPro entries with consensus annotation
  - Matching method documented: "Domain IPR000694 (ADK) detected via Pfam PF00406, E-value: 2.3e-45"

- **Data model**:

```
DatabaseRecord(
    source_database="interpro",
    native_id="IPR000694",
    data_fields={
        "domain_name": "Adenylate kinase",
        "short_name": "ADK",
        "domain_type": "family",
        "matches": [
            {
                "database": "Pfam",
                "accession": "PF00406",
                "evalue": 2.3e-45,
                "location": "29-210",
            }
        ],
        "go_terms": ["ATP binding", "kinase activity"],
    },
    retrieval_date="2026-06-01",
    version="InterPro 98.0",
    confidence_score=0.90,
    evidence_type="R",           # Curated domain definitions
)
```

### C. Deferred Bridges (Post-Pilot)

These are explicitly deferred, not ignored. Each deferred bridge has a documented reason and trigger condition.

| Bridge | Domain | Deferral Reason | Trigger for Implementation |
|--------|--------|-----------------|----------------------------|
| OMIM / ClinVar | Clinical genetics, human phenotypes | Requires additional ethical review architecture; clinical data has consent and privacy constraints that the MVP ethics layer does not handle | Phase 6+ after ethics layer has been battle-tested on non-clinical data |
| GTEx / ENCODE | Functional genomics (expression, regulation) | Largely human-centric; cross-cutting integration with multi-omics is complex and would delay MVP | Post-pilot, when multi-omics support is scoped |
| GEO / ArrayExpress | Gene expression (microarray, RNA-seq) | Heavy data volume; local-first scaling needs evaluation | Post-pilot, with compression and streaming design |
| BioGRID / STRING | Protein-protein interactions | Interaction data has complex confidence metrics (combined scores, experimental evidence codes) that need careful modeling | Post-pilot, interaction network analysis |
| KEGG / Reactome | Pathway databases | Pathway analysis requires dynamic graph traversal, not static query | Post-pilot, pathway analytics |
| ChEMBL / DrugBank | Drug targets, bioactive compounds | Drug discovery integration raises dual-use concerns; needs RiskTier review | Post-pilot, after ethics layer DURC detection is validated |

Each deferred bridge has a **stub adapter** that documents API contact, rate limits, and data model — so the integration path is clear even before implementation.

---

## III. Confidence Propagation Architecture

### A. The Problem — In Concrete Terms

Consider a typical multi-step bioinformatics workflow:

1. Query UniProt for a protein sequence (AK2, accession P30085) → high confidence, Swiss-Prot reviewed
2. Retrieve its predicted structure from AlphaFold DB → pLDDT scores per residue
3. Map predicted structure domains from InterPro → domain boundaries with confidence
4. Analyze a binding site within a low-confidence domain → medium confidence
5. Use binding site to predict drug interactions → low confidence (but presented as "discovery")

Google's Science Skills performs steps 1-4 silently and delivers step 5 as an "insight." The researcher sees a binding mechanism description without knowing that:
- The binding interface spans a region where mean pLDDT = 0.52 (very low)
- The domain assignment in that region conflicts with an alternative domain model from a different method
- The "drug interaction" is a predicted docking onto a predicted structure using an algorithm trained on experimental structures

This is not just missing uncertainty quantification. It is **epistemically dangerous**: the output looks like science but has a hidden fragility that compounds at each step. [07_science_skills.md §VII.34](../../critiques/07_science_skills.md)

### B. OpenSciRe's Solution — Confidence Traces

Every structured data query in openscire-bio includes a **confidence trace**: a recursive data structure that records the confidence provenance for each data point or aggregate.

**Basic confidence trace structure:**

```
ConfidenceTrace:
  - originating_database: str
  - confidence_scores: dict[str, float]  # per-field or per-residue
  - propagation_path: list[str]           # sequence of operations applied
  - evidence_type: str                    # P (predicted), E (experimental), R (reviewed)
  - cumulative_uncertainty: float         # aggregate (method-dependent)
  - caveats: list[str]                    # human-readable warnings
```

**Per-residue propagation (example):**

When an InterPro domain search uses AlphaFold coordinates:

```
Domain prediction for AK2:
  Domain: Adenylate kinase (IPR000694)
  Location: residues 29-210
  Source domain boundaries: curated (InterPro), high confidence

  Underlying structure: AlphaFold (predicted, mean pLDDT: 0.73)
  Confidence trace:
    - pLDDT for residues 29-100: 0.88-0.95 (reliable)
    - pLDDT for residues 101-180: 0.92-0.96 (reliable)
    - pLDDT for residues 181-210: 0.45-0.62 (low confidence loop)

  Impact on analysis:
    Binding site predicted at residues 185-195 (mean pLDDT: 0.52)
    Confidence: LOW — experimental validation strongly recommended
```

**Aggregate confidence (example binding interaction prediction):**

```
Interaction probability (AK2-ATP): 0.78
  Derived from:
  - Protein conformation: AlphaFold (mean pLDDT 0.73) → weight 0.4
  - Binding pocket geometry: site prediction algorithm v2.3 → weight 0.3
  - Electrostatic complementarity: APBS charge calculation → weight 0.3

  Cumulative uncertainty:
    Propagation path: UniProt → AlphaFold → site_prediction → docking
    Effective confidence: 0.58 (degraded from 0.78)
    This accounts for origin uncertainty (pLDDT → pocket predictions → docking)
```

### C. User-Configurable Confidence Thresholds

Users can configure confidence filters globally or per-analysis:

- "Only include results where all contributing data sources have confidence > 0.8"
- "Accept predicted structures but flag them prominently"
- "Exclude results that depend on intrinsically disordered regions"
- "Show all confidence levels, color-coded by evidence type"

These thresholds are recorded in the query provenance and affect reproducibility: "This analysis was run with confidence_threshold=0.7, excluding 23% of candidate residues as below threshold."

### D. What Never Happens

- Confidence scores are never dropped silently.
- Predicted and experimental data are never merged without labeling.
- A low-confidence result is never presented as equivalent to a high-confidence one.
- Aggregation always produces distributions, not just point estimates. "Mean pLDDT: 0.73" comes with "(range: 0.12-0.96, n=233 residues)."

---

## IV. Ontological Transparency

### A. The No-Flattening Principle

Google's Science Skills integrates "over 30 major life science databases" into a unified query space. This is presented as a feature but is ontologically catastrophic: sequence data (UniProt), structural predictions (AlphaFold), experimental measurements (PDB), domain families (InterPro), and genomic contexts (AlphaGenome) are treated as commensurable data layers that can be seamlessly piped together. [07_science_skills.md §I.1](../../critiques/07_science_skills.md)

OpenSciRe inverts this: **flattening is always explicit, never implicit.**

- Each bridge returns data in its source-native structure. UniProt records remain UniProt records. PDB structures remain PDB structures. The ontologies are preserved.
- When a cross-database query requires flattening (e.g., a table that joins UniProt annotations with AlphaFold pLDDT scores and InterPro domain boundaries), the system produces a **flattening manifest** that documents:
  - The source databases involved
  - The join keys and methods used
  - Any loss of information from the original data model
  - Any assumptions made during mapping (e.g., "mapped residues by sequence position, which assumes identical isoform")
- The original unflattened records are always available. The flattened view is a derived artifact, not the canonical representation.

### B. Explicit Cross-Referencing

When openscire-bio bridges between databases (e.g., linking a UniProt accession to a PDB structure), it documents the cross-reference method with all available metadata:

```
CrossReference:
  database_a: "uniprot"
  id_a: "P30085"
  database_b: "pdb"
  id_b: "3J1Q"
  mapping_method: "SIFTS cross-reference"
  mapping_confidence: 0.95
  last_updated: "2025-11-15"
  caveats: [
    "This PDB entry may correspond to a different isoform than UniProt canonical",
    "PDB structure covers residues 29-210 only (missing N-terminal mitochondrial targeting signal)"
  ]
```

When cross-references are ambiguous (e.g., multiple PDB structures map to the same UniProt entry, or no cross-reference exists), the system surfaces the issue rather than silently choosing:

- "No direct cross-reference found between UniProt P30085 and AlphaFold DB. Sequence-based mapping used (100% identity over 233 residues)."
- "Multiple PDB structures map to UniProt P30085: 3J1Q (2.3 Å), 3N5U (2.8 Å), 4X8H (1.9 Å). Returning all with resolution metadata."

### C. Handling Ontological Tensions

Some tensions between database ontologies cannot be resolved by mapping — they are genuine epistemological disagreements:

- **AlphaFold vs. PDB on the same protein**: AlphaFold may predict a stable conformation that differs from a crystallographic structure due to crystal packing or buffer conditions. openscire-bio does not resolve this conflict. It presents both with their respective evidence types and confidence scores, and lets the user — or an explicit analysis step — reconcile them.
- **UniProt vs. RefSeq on sequence annotation**: The same gene may have slightly different canonical sequences between databases due to different isoform selection. openscire-bio documents the conflict and presents both.

This approach — surfacing tensions rather than smoothing them — is philosophically grounded in the epistemology of scientific disagreement. It treats database divergence as information, not noise. [02_philosophy.md §II.1](../../critiques/02_philosophy.md)

---

## V. Epistemic Safety

### A. Prediction vs. Experiment Labeling

Every data point in openscire-bio carries an **evidence type** label:

| Label | Meaning | Sources | Visual |
|-------|---------|---------|--------|
| **R** | Reviewed / Curated | UniProt Swiss-Prot, RefSeq reviewed, InterPro curated entries, PDB structures with published validation reports | Green checkmark |
| **E** | Experimental (unreviewed) | PDB structures in processing, EMBL submissions, GenBank direct submissions | Blue circle |
| **P** | Predicted / Computationally derived | AlphaFold DB, computational annotations, automated genome annotation pipelines | Yellow triangle with warning |

**Critical guarantee**: The evidence type label propagates through all analyses and outputs. It cannot be stripped, overwritten, or hidden. Any output that aggregates R, E, and P data must display the mix and flag predicted components.

This directly addresses the "prediction-reality ontological confusion" gap: the system erects an epistemic fire break between model and nature, and it never dissolves that distinction. [07_science_skills.md §I.2](../../critiques/07_science_skills.md)

### B. Uncertainty Quantification

Beyond the binary P/E/R label, openscire-bio provides continuous uncertainty quantification for all available metrics:

- **Structural data**:
  - AlphaFold: per-residue pLDDT (0-100), PAE matrices, mean pLDDT
  - PDB: resolution (Å), R-free, clash score, Ramachandran outliers
  - Cryo-EM: map resolution (Å), FSC curve
  - NMR: number of restraints, RMSD across models

- **Sequence data**:
  - NCBI: assembly quality metrics (scaffold N50, gap count, QV score)
  - UniProt: evidence codes for each annotation (ECO hierarchy)
  - InterPro: match E-values, domain coverage ratios

- **Derived data**:
  - Confidence propagation calculates effective uncertainty through chains of operations
  - When confidence is unknown, it is marked as "unavailable" rather than assumed high
  - Aggregated analyses include confidence distributions, not just point estimates

### C. Knowledge Boundary Flagging

openscire-bio explicitly flags **knowledge boundaries** — things it cannot tell you:

- "This protein has no experimental structure in PDB. Returning AlphaFold prediction (mean pLDDT: 0.73, evidence type: P)."
- "Intrinsically disordered region (residues 181-210, pLDDT < 0.5). Structural analysis of this region is unreliable."
- "No InterPro match found for residues 1-28 — this region may be poorly characterized or annotation not yet available."
- "This organism (Xenopus tropicalis) has limited UniProt annotation depth. Only core sequence data available."

This is the opposite of Science Skills, which likely never refuses. [07_science_skills.md §X.47](../../critiques/07_science_skills.md)

### D. Reproducibility

Every query produces a **ReproducibilityBundle** — a container with all metadata needed to reproduce the analysis:

```
ReproducibilityBundle:
  - Software version: openscire-bio v0.4.2
  - Python version: 3.12
  - Database versions:
    - UniProtKB: 2025_04
    - AlphaFold DB: 2025_03
    - PDB: 2025_12
    - InterPro: 98.0
  - Query parameters: {full JSON of query}
  - Rate limiting config: {backoff settings, API key presence}
  - Cache: {cache hit/miss, cache TTL}
  - Timestamp: 2026-06-01T14:30:00Z
  - Join manifest: {cross-references used, conflict resolutions}
  - Confidence thresholds: {user config at time of query}
```

This integrates with the broader OpenSciRe provenance DAG (from Phase 1) and the ReproducibilityBundle pattern shared across all OpenSciRe components.

---

## VI. Gap Closure Map

### A. Primary Gaps from 07_science_skills.md

| Gap Domain | Specific Gap from Critique | Critique Source | OpenSciRe Mitigation |
|---|---|---|---|
| Ontological | **§1. Database-bound ontological reductionism**: Flattening sequence/structure/function/evolution into commensurable plane | [07_science_skills.md §I.1](../../critiques/07_science_skills.md) | Per-database bridges preserve native ontology; flattening is explicit with documentation; flattening manifest produced per query |
| Ontological | **§2. Prediction-reality ontological confusion**: AlphaFold treated as interchangeable with PDB | [07_science_skills.md §I.2](../../critiques/07_science_skills.md) | P/E/R evidence type labeling on every data point; AlphaFold explicitly labeled as predicted (P); pLDDT propagated through all downstream steps; experimental (E) preferred when available, with user override |
| Ontological | **§3. Organism-centric epistemic bias**: 30+ databases dominated by model organisms | [07_science_skills.md §I.3](../../critiques/07_science_skills.md) | Multi-source coverage extending beyond model organisms; NCBI Taxonomy bridge supports full tree; knowledge boundary flags for under-annotated species; non-model organism support as explicit design criterion |
| Ontological | **§4. Flattening of biological complexity**: Protein as isolated, decontextualized entity | [07_science_skills.md §I.4](../../critiques/07_science_skills.md) | Acknowledged limitation — cellular context, spatiotemporal dynamics, PTMs, and interactome are beyond current MVP scope. Flagged as knowledge boundary in bridge outputs. Context-aware analysis deferred to post-pilot integration with pathway and interaction databases |
| Ontological | **§5. Absence of negative knowledge**: Databases record what is known, not trial failures | [07_science_skills.md §I.5](../../critiques/07_science_skills.md) | Knowledge boundary flagging acknowledges absence; Negative Result Registry (Phase 3 ethics layer) enables manual recording of failed crystallization attempts, knockout negatives, etc. Stub interface for negative knowledge ingestion |
| Methodological | **§6. Workflow templation trap**: Pre-canned workflow templates hide methodological decisions | [07_science_skills.md §II.6](../../critiques/07_science_skills.md) | No pre-canned workflows — openscire-hypothesis builds custom analysis pipelines; all parameters surfaced transparently; alternatives presented |
| Methodological | **§7. Missing experimental validation bridge**: In silico only, no wet-lab integration | [07_science_skills.md §II.7](../../critiques/07_science_skills.md) | Explicit "in silico only" labeling; "experimental validation recommended" on predicted results; experimental bridge stub (Tier 1 risk) defined but deferred |
| Methodological | **§8. Hidden parameter problem**: E-value thresholds, pLDDT cutoffs set opaquely | [07_science_skills.md §II.8](../../critiques/07_science_skills.md) | All query parameters exposed and documented in provenance; sensitivity analysis can be run by varying parameters; defaults are reasonable but never hidden |
| Methodological | **§9. Absence of null model and control integration**: No mandatory negative controls | [07_science_skills.md §II.9](../../critiques/07_science_skills.md) | Phase 5 (openscire-hypothesis) includes randomized/shuffled control integration; bootstrap confidence estimates where applicable |
| Methodological | **§10. Inability to handle novel data types**: 30 databases cover 2010s biology only | [07_science_skills.md §II.10](../../critiques/07_science_skills.md) | Plugin architecture for new bridges; explicit naming of deferred frontier data types; community-contributed bridge framework for novel data types |
| Technical | **§11. API fragility of 30+ dependencies**: Cascading failure architecture | [07_science_skills.md §III.11](../../critiques/07_science_skills.md) | Per-bridge graceful degradation — each bridge fails independently; partial results labeled as such; local caching buffers against API downtime; circuit breaker pattern with configurable retry/backoff |
| Technical | **§12. Data staleness and versioning crisis**: Which version of database was used? | [07_science_skills.md §III.12](../../critiques/07_science_skills.md) | Database version recorded in every provenance entry; version comparison tools; inflation watch alerts when cached data becomes stale |
| Technical | **§13. Black-box integration logic**: Proprietary join conditions and conflict resolution | [07_science_skills.md §III.13](../../critiques/07_science_skills.md) | Open-source bridge code; transparent join manifests; conflict resolution documented per query; no proprietary middleware |
| Technical | **§14. Platform lock-in (Antigravity vs. GitHub)**: Open code on closed platform | [07_science_skills.md §III.14](../../critiques/07_science_skills.md) | All bridges are local-first; no cloud dependency for basic operation; all code open-source under Apache 2.0; managed tier is convenience, not necessity |
| Technical | **§15. Big data blind spot**: 30-database schema chokes on real big data | [07_science_skills.md §III.15](../../critiques/07_science_skills.md) | Acknowledged limitation — local-first architecture limits scale for petabyte-scale genomics; stream processing for moderate-sized datasets; cloud backend deferred for enterprise tier (if/when funded) |
| Technical | **§16. Format Tower of Babel**: Hundreds of biological data formats | [07_science_skills.md §III.16](../../critiques/07_science_skills.md) | Core bridges handle native formats (CIF, mmCIF, FASTA, GenBank); format conversion libraries (BioPython, PyMOL) can be used alongside; extensible parser plugin point |
| Domain-specific | **§17. AlphaFold confidence NOT propagated**: pLDDT dropped in downstream analysis | [07_science_skills.md §IV.17](../../critiques/07_science_skills.md) | pLDDT scores propagated through ALL downstream analyses; per-residue confidence traces; aggregate confidence includes pLDDT distributions; pLDDT can never be dropped in the data model |
| Domain-specific | **§18. Intrinsically disordered protein blind spot**: AlphaFold misrepresents IDRs as structured | [07_science_skills.md §IV.18](../../critiques/07_science_skills.md) | IDR regions flagged explicitly (pLDDT < 0.5); structural analysis of IDRs warned against; knowledge boundary: "this tool cannot predict IDR function" |
| Domain-specific | **§19. Missing multi-omics integration**: Siloed by omics layer | [07_science_skills.md §IV.19](../../critiques/07_science_skills.md) | Acknowledged deferred — post-pilot scope; plugin architecture will enable multi-omics bridges (transcriptomics, proteomics, metabolomics) |
| Domain-specific | **§20. Clinical/phenotypic chasm**: No OMIM, ClinVar, HPO, gnomAD | [07_science_skills.md §IV.20](../../critiques/07_science_skills.md) | Acknowledged deferred — requires additional ethical review (clinical data consent); flagged in gap report; ethics layer (Phase 3) must handle clinical data before bridge implementation |
| Domain-specific | **§21. Drug discovery and therapeutic translation gap**: No ChEMBL, DrugBank, screening libraries | [07_science_skills.md §IV.21](../../critiques/07_science_skills.md) | Deferred to post-pilot — drug discovery integration raises DURC concerns; ethics layer RiskTier detection must be validated before implementing |
| Domain-specific | **§22. Evolutionary and ecological blind spot**: Static databases, no phylogenetic history | [07_science_skills.md §IV.22](../../critiques/07_science_skills.md) | Acknowledged — phylogenetic reconstruction is a distinct capability outside bridge scope; openscire-hypothesis can design phylogenetic analyses that use bridge data as input |
| Human interface | **§23. Deskilling of bioinformatics expertise**: Workflows run without understanding method | [07_science_skills.md §V.23](../../critiques/07_science_skills.md) | Pedagogical transparency: outputs explain database choices, parameter selections, confidence implications; documentation links to method references; "why this query?" in provenance trace |
| Human interface | **§24. Speed-bias / cognitive compression**: Minutes vs. hours erodes incubation period | [07_science_skills.md §V.24](../../critiques/07_science_skills.md) | Deliberate friction: uncertainty surfaced; multiple analysis paths offered; no "single answer" mode; confidence warnings slow down consumption of unreliable outputs |
| Human interface | **§25. Missing explanation layer**: No explanation of why X was chosen over Y | [07_science_skills.md §V.25](../../critiques/07_science_skills.md) | Full provenance trace; every data point annotated with source, confidence, and evidence type; join manifest explains cross-reference choices; alternative interpretations surfaced in conflict cases |
| Human interface | **§26. Customization ceiling**: Pre-built skills cannot handle novel questions | [07_science_skills.md §V.26](../../critiques/07_science_skills.md) | Open-source; plugin architecture for custom database bridges; API-first design enables custom workflow construction |
| Human interface | **§27. Trust asymmetry**: "30 databases" heuristic masks errors, biases, gaps | [07_science_skills.md §V.27](../../critiques/07_science_skills.md) | Disaggregated trust: per-source, per-entry, per-annotation confidence; evidence type labels (P/E/R); graded skepticism built into data model |
| Ethics/Power | **§28. Data colonialism of database integration**: Northern institutions, global data, Google value extraction | [07_science_skills.md §VI.28](../../critiques/07_science_skills.md) | Open-source, local-first; no proprietary extraction layer; contributions to upstream databases encouraged; IndigenousKnowledgeProtector in ethics layer flags ethically contested data |
| Ethics/Power | **§29. Indigenous genetic data problem**: Databases contain data collected without consent | [07_science_skills.md §VI.29](../../critiques/07_science_skills.md) | DataSovereigntyChecker (Phase 3) flags indigenous/non-consented data; CARE Principles integration; audit trail of access |
| Ethics/Power | **§30. Commodification of public science**: Public data wrapped in proprietary interface | [07_science_skills.md §VI.30](../../critiques/07_science_skills.md) | Open-source interface, not a proprietary one; no monetization of data access; value captured through managed hosting, not data enclosure |
| Ethics/Power | **§31. Rare disease hype cycle**: In silico hypotheses without clinical translation | [07_science_skills.md §VI.31](../../critiques/07_science_skills.md) | Experimental validation bridge flagged; "computational speculation" labeling; clinical translation requires ethics review before implementation |
| Ethics/Power | **§32. Accessibility paradox**: Open label masks digital divide | [07_science_skills.md §VI.32](../../critiques/07_science_skills.md) | Local-first design reduces internet dependency; SQLite-based caching for intermittent connectivity; CLI-first for low-resource environments |
| Provenance | **§33. Missing cross-database provenance graph**: Synthesized output without fine-grained provenance | [07_science_skills.md §VII.33](../../critiques/07_science_skills.md) | Every claim traces to source database, version, query parameters, and retrieval timestamp; provenance DAG integration |
| Provenance | **§34. Lack of uncertainty propagation**: Point estimates mask compounding uncertainty | [07_science_skills.md §VII.34](../../critiques/07_science_skills.md) | Confidence traces through multi-step analyses; distributional outputs (not point estimates); cumulative uncertainty calculation |
| Provenance | **§35. Absence of adversarial validation**: No red teaming, null testing, or synthetic control | [07_science_skills.md §VII.35](../../critiques/07_science_skills.md) | openscire-hypothesis includes adversarial testing: perturb input queries, use decoy sequences, synthetic null data; verification asymmetry tracker |
| Provenance | **§36. Replication packaging failure**: No automated reproducibility bundles | [07_science_skills.md §VII.36](../../critiques/07_science_skills.md) | ReproducibilityBundle per query: locked database versions, parameters, integration logic, and timestamps |
| Temporal | **§37. Snapshot problem vs. living biology**: Analysis immediately outdated | [07_science_skills.md §VIII.37](../../critiques/07_science_skills.md) | Temporal monitoring via RetractionWatch pattern: re-check results when database versions update; alert user when new data invalidates previous analysis |
| Temporal | **§38. Inability to handle time-series and dynamic data**: Static databases only | [07_science_skills.md §VIII.38](../../critiques/07_science_skills.md) | Acknowledged — time-series omics, developmental trajectories, and dynamic biology are beyond bridge scope; openscire-hypothesis can coordinate multi-timepoint analyses using bridge snapshots |
| Temporal | **§39. Missing longitudinal project memory**: Episodic transactions, no project tracking | [07_science_skills.md §VIII.39](../../critiques/07_science_skills.md) | Project context through openscire-core — query history, hypothesis evolution, and database version changes tracked across sessions |
| Comparative | **§40. Missing "data smell"**: No intuition for spurious hits, contamination, implausibility | [07_science_skills.md §IX.40](../../critiques/07_science_skills.md) | UncertaintyQuantifier flags anomalous data patterns; cross-reference validation checks for inconsistencies; human-in-the-loop remains essential |
| Comparative | **§41. Lack of methodological creativity**: Cannot invent new methods when existing ones fail | [07_science_skills.md §IX.41](../../critiques/07_science_skills.md) | Plugin architecture enables community-contributed analysis methods; openscire-hypothesis custom pipeline construction; extensible, not templated |
| Comparative | **§42. Inability to "read between the data"**: Database entries treated as authoritative present tense | [07_science_skills.md §IX.42](../../critiques/07_science_skills.md) | Literature citation age surfaced; annotation method dates shown; deprecated or superseded data flagged when version tracking detects change |
| Comparative | **§43. Missing interdisciplinary bridge**: No connection to clinical, ethical, social dimensions | [07_science_skills.md §IX.43](../../critiques/07_science_skills.md) | openscire-bio is explicitly a bioinformatics bridge, not an interdisciplinary platform; cross-referencing with Phase 3 ethics layer, Phase 6 clinical integration |
| Meta | **§44. "Skill" as commodification of expertise**: Bioinformatics as pluggable module | [07_science_skills.md §X.44](../../critiques/07_science_skills.md) | Named "bridge," not "skill" — deliberate semantic choice signaling connection, not replacement; pedagogical transparency preserves disciplinary understanding |
| Meta | **§45. Database quantity ≠ quality**: 30 databases presented as virtue without integration quality | [07_science_skills.md §X.45](../../critiques/07_science_skills.md) | Quality over quantity: core bridges prioritized (5 MVP, ~10 deferred); integration quality metrics (cross-reference currency, conflict frequency, coverage depth) surfaced |
| Meta | **§46. Structural confusion of speed with progress**: Minutes vs. hours = false value proposition | [07_science_skills.md §X.46](../../critiques/07_science_skills.md) | Deliberate uncertainty exposure slows consumption of unreliable outputs; confidence warnings create productive friction; speed is a secondary goal after correctness and transparency |
| Meta | **§47. Absence of "stop" or "refuse" mechanism**: Never refuses analysis | [07_science_skills.md §X.47](../../critiques/07_science_skills.md) | Knowledge boundaries flag: "cannot analyze — insufficient data," "prediction confidence below threshold," "this question requires experimental work"; RefusalEngine (Phase 5 concept) |
| Meta | **§48. Black-boxing of the scientific workbench**: Tools work by incantation | [07_science_skills.md §X.48](../../critiques/07_science_skills.md) | Open-source, inspectable bridge code; mechanical interior visible; provenance shows every gear turning |

### B. Cross-Cutting Gaps from Other Critique Files

| Gap Domain | Specific Gap | Critique Source | OpenSciRe Mitigation |
|---|---|---|---|
| Epistemology | Conflation of information synthesis with understanding | [02_philosophy.md §II.1](../../critiques/02_philosophy.md) | Bridges serve data, not substitute for understanding; pedagogical transparency; non-flattened data model preserves disciplinary distinctness |
| Epistemology | Gettier problem: justified-looking citations that are coincidental | [02_philosophy.md §II.1](../../critiques/02_philosophy.md) | Source verification (Phase 3) checks that cited data exists; confidence propagation surfaces fragility; adversarial validation step |
| Epistemology | Tacit knowledge / knowing-how irreducibility | [02_philosophy.md §II.1](../../critiques/02_philosophy.md) | Acknowledged limitation — openscire-bio cannot replace bioinformatics apprenticeship; confidence warnings preserve space for human judgment |
| Ontology | Computational reduction of being: science as optimization landscape | [02_philosophy.md §II.2](../../critiques/02_philosophy.md) | No "optimization" ontology in bridge outputs — data is presented as data, not as "scores to maximize"; multiple analysis paths offered |
| Phenomenology | Erasure of struggle: friction as pure negativity | [02_philosophy.md §II.3](../../critiques/02_philosophy.md) | Deliberate friction through uncertainty exposure; confidence warnings cannot be skipped; provenance trace requires reading to understand output |
| Phenomenology | Division of cognitive labor: self-hosting fragments attention | [02_philosophy.md §II.3](../../critiques/02_philosophy.md) | Managed tier reduces sysadmin burden for those who want it; but local-first is always available |
| Ethics | Concentration of scientific means of production | [02_philosophy.md §II.4](../../critiques/02_philosophy.md) | Local-first architecture means no gatekeeper controls access to tools; data sovereignty via BYO-infrastructure |
| Ethics | Responsibility gaps: who is liable for dangerous output? | [02_philosophy.md §II.4](../../critiques/02_philosophy.md) | EthicalFirewall (Phase 3) blocks high-risk queries; audit trail in provenance; user retains responsibility for outputs — surfaced in terms |
| Political economy | Value extraction from publicly funded science | [02_philosophy.md §II.5](../../critiques/02_philosophy.md) | All bridge code open-source; no rent extraction from data access; managed tier charges for infrastructure, not data |
| Political economy | BYOK fallacy: tool becomes frontend for proprietary backends | [02_philosophy.md §II.5](../../critiques/02_philosophy.md) | Local models supported via Ollama/vLLM; BYOK is optional, not default; local-first path always available |
| Philosophy of science | Simulation of scientific method: verificationist, not falsificationist | [02_philosophy.md §II.7](../../critiques/02_philosophy.md) | openscire-bio does not simulate method — it provides data; openscire-hypothesis is the hypothesis layer with falsification-aware design |
| Philosophy of science | Conservatism of distributed development: incrementalism over revolution | [02_philosophy.md §II.7](../../critiques/02_philosophy.md) | Plugin architecture enables disruptive bridge designs by third parties; community can build bridges for data types the core team never considered |
| Social philosophy | Epistemic violence of ranking: what is scored as "better" reflects funder priorities | [02_philosophy.md §II.9](../../critiques/02_philosophy.md) | No scoring/ranking of databases in bridge layer; quality metadata surfaced but ranking deferred to user judgment |
| Social philosophy | Digital colonialism of open source: Northern developers, Southern consumers | [02_philosophy.md §II.9](../../critiques/02_philosophy.md) | Non-English corpus bridges (through Phase 4 literature engine) include SciELO, AJOL, CNKI; multilingual support; contributions from Global South researchers welcomed and funded |
| Technology philosophy | Enframing (Gestell): technology defines what science is | [02_philosophy.md §II.11](../../critiques/02_philosophy.md) | openscire-bio is a bridge, not a cage: it connects to databases without defining what questions to ask; multiple ontologies preserved; no hidden teleology |
| Structural | Orphaned Science Skills: no integration with hypothesis/compute tools | [03_structural_triad.md §II.4](../../critiques/03_structural_triad.md) | openscire-bio explicitly integrates with openscire-hypothesis (data → hypothesis) and provenance DAG (traceability); shared adapter pattern with literature engine |
| Structural | Product-driven rather than process-driven: tools define process | [03_structural_triad.md §II.5](../../critiques/03_structural_triad.md) | Process-driven design: bridge adapters are a pattern, not a product; shared architecture with literature source adapters ensures consistency |
| Structural | Missing data/instrumentation layer | [03_structural_triad.md §II.6](../../critiques/03_structural_triad.md) | Data provenance and protocol standardization in bridge architecture; experimental design tool in openscire-hypothesis |
| Structural | Missing ethical/governance structural layer | [03_structural_triad.md §II.13](../../critiques/03_structural_triad.md) | Phase 3 ethics layer integration: EthicalFirewall, DataSovereigntyChecker, RiskTier classification apply to bridge data |
| Structural | Missing negative result and null hypothesis architecture | [03_structural_triad.md §II.10](../../critiques/03_structural_triad.md) | Knowledge boundaries as negative knowledge; Negative Result Registry stub; bridge outputs include "what was not found" |
| Legal/IP | Training data IP contamination | [08_miscellaneous.md §I.2](../../critiques/08_miscellaneous.md) | openscire-bio queries live databases, not training data; no model training on bridge outputs by default; no IP contamination from model weights |
| Legal/IP | Attribution bankruptcy of AI synthesis | [08_miscellaneous.md §I.4](../../critiques/08_miscellaneous.md) | Every bridge query cites the specific source and version; ReproducibilityBundle enables attribution; ORCID integration for human oversight |
| Security | Supply chain attack surface: compromised API → cascading flaw | [08_miscellaneous.md §II.7](../../critiques/08_miscellaneous.md) | Cryptographic verification of database integrity (future: content-addressed data); circuit breaker per bridge; air-gapped mode for sensitive research |
| Governance | No independent certification body | [08_miscellaneous.md §VIII.27](../../critiques/08_miscellaneous.md) | Open-source code enables independent security/methodology audit; no self-certification; community verification model |
| Interoperability | FAIR principles violation | [08_miscellaneous.md §VII.23](../../critiques/08_miscellaneous.md) | RO-Crate/JSON-LD provenance; W3C PROV compatibility; export to Zenodo/Figshare; FAIR by architecture |
| Interoperability | Lock-in to Google's API ecosystem | [08_miscellaneous.md §VII.24](../../critiques/08_miscellaneous.md) | No Google dependency; all bridges connect directly to public APIs; alternative API endpoints configurable |
| Interoperability | Missing provenance standard (W3C PROV, RO-Crate, CWL) | [08_miscellaneous.md §VII.26](../../critiques/08_miscellaneous.md) | RO-Crate provenance packaging; W3C PROV-DM provenance model; CWL-compatible workflow descriptions |
| User experience | Field science offline requirement | [08_miscellaneous.md §VI.21](../../critiques/08_miscellaneous.md) | SQLite-based caching for offline operation; sync-when-connected mode; local-first design reduces internet dependency |
| Systemic risk | Research agenda homogenization: everyone chases same ideas | [08_miscellaneous.md §XI.36](../../critiques/08_miscellaneous.md) | Bridge architecture enables diverse data sources, including non-Western, non-model-organism data; community bridges disrupt default agendas |
| Systemic risk | Catastrophic discovery acceleration | [08_miscellaneous.md §XI.37](../../critiques/08_miscellaneous.md) | RiskTier classification: dual-use or high-risk database queries (e.g., pathogen genomics) require human checkpoints; DURC detection in EthicalFirewall |
| Psychological | Automation bias and complacency | [08_miscellaneous.md §XII.39](../../critiques/08_miscellaneous.md) | Uncertainty exposure as cognitive forcing function; confidence warnings that cannot be dismissed; "what would change if pLDDT were 0.9?" reflection prompt |
| Psychological | Decision fatigue from option overload | [08_miscellaneous.md §XII.40](../../critiques/08_miscellaneous.md) | Progressive disclosure: basic output first, then expand for detail; confidence-based filtering reduces noise; tiered decision trees |
| Scientific integrity | AI-enabled HARKing: temporal boundary between hypothesis and test erased | [08_miscellaneous.md §XIII.43](../../critiques/08_miscellaneous.md) | Provenance DAG timestamps every query; audit trail preserves intellectual chronology; hypothesis → test sequence verifiable |
| Scientific integrity | Deepfake data generation: synthetic datasets as empirical | [08_miscellaneous.md §XIII.45](../../critiques/08_miscellaneous.md) | Evidence type labels (P/E/R) distinguish predicted from experimental; synthetic data watermarking (future); provenance verification |
| Environmental | E-waste from hardware obsolescence | [08_miscellaneous.md §XIV.47](../../critiques/08_miscellaneous.md) | Efficient query design reduces compute; lightweight bridges run on modest hardware; CarbonBudgetTracker (Phase 3) monitors footprint |
| Environmental | Water and energy colonialism | [08_miscellaneous.md §XIV.48](../../critiques/08_miscellaneous.md) | Local-first reduces reliance on large data centers; efficient local caching reduces repeated queries |
| Meta-cross-cutting | Missing "Hippocratic Oath" for AI science developers | [08_miscellaneous.md §XV.50](../../critiques/08_miscellaneous.md) | RESPONSIBLE_DISCLOSURE.md, SECURITY.md, and ethics-by-design architecture; fiduciary tone in all documentation |
| Meta-cross-cutting | No "slow science" mode | [08_miscellaneous.md §XV.52](../../critiques/08_miscellaneous.md) | Deliberate friction via uncertainty exposure; "contemplation mode" where results are presented with mandatory reading time for low-confidence outputs |
| Meta-cross-cutting | Graceful degradation for catastrophic failure | [08_miscellaneous.md §XV.53](../../critiques/08_miscellaneous.md) | Per-bridge circuit breakers; partial results with gap documentation; revert to manual workflow path |
| Meta-cross-cutting | Ultimate human override absence | [08_miscellaneous.md §XV.54](../../critiques/08_miscellaneous.md) | Human-in-the-loop checkpoints (mandatory for Tier 1-2 analyses); all bridge outputs are advisory, not authoritative; no auto-execution of high-risk queries |

---

## VII. Data Models & Architecture

### A. Core Data Models

#### DatabaseRecord

```python
class EvidenceType(Enum):
    PREDICTED = "P"        # Computationally derived (AlphaFold, etc.)
    EXPERIMENTAL = "E"     # Empirically measured (PDB, X-ray, cryo-EM)
    REVIEWED = "R"         # Curated/reviewed (Swiss-Prot, RefSeq reviewed)
    UNAVAILABLE = "U"      # Evidence type unknown

@dataclass
class DatabaseRecord:
    source_database: str            # "uniprot", "alphafold_db", "pdb", "ncbi", "interpro"
    native_id: str                  # Accession in the source database
    data_fields: dict[str, Any]     # Source-native data fields
    retrieval_date: datetime
    version: str                    # Source database release version
    confidence_score: float | None  # Aggregate confidence (source-specific)
    evidence_type: EvidenceType     # P, E, R, or U
    metadata: dict[str, Any]        # Provenance metadata
```

#### CrossReference

```python
@dataclass
class CrossReference:
    database_a: str
    id_a: str
    database_b: str
    id_b: str
    mapping_method: str             # "SIFTS", "sequence_identity", "id_mapping"
    mapping_confidence: float       # 0.0-1.0
    last_updated: datetime
    caveats: list[str]              # Known issues with this mapping
```

#### ConfidenceTrace

```python
@dataclass
class ConfidenceTrace:
    originating_database: str
    confidence_scores: dict[str, float]   # Per-field or per-position
    propagation_path: list[str]           # Operation sequence
    evidence_type: EvidenceType
    cumulative_uncertainty: float | None  # Aggregated
    caveats: list[str]                    # Human-readable warnings
```

#### AnalysisStep

```python
@dataclass
class AnalysisStep:
    input_records: list[DatabaseRecord]
    operation: str                  # "domain_mapping", "cross_reference", "structure_align"
    parameters: dict[str, Any]      # Operation-specific parameters
    output_records: list[DatabaseRecord]
    confidence_trace: ConfidenceTrace
    timestamp: datetime
```

### B. Bridge Architecture

Each bridge follows an adapter pattern sharing architecture with openscire-literature source adapters:

```
BridgeAdapter (abstract base)
│
├── UniProtBridge
├── AlphaFoldBridge
├── PDBBridge
├── NCBIBridge
├── InterProBridge
└── (plugin bridges)
```

**Shared interface:**

```python
class BridgeAdapter(ABC):
    @abstractmethod
    async def query(self, params: QueryParams) -> BridgeResult: ...

    @abstractmethod
    async def get_record(self, native_id: str) -> DatabaseRecord: ...

    @abstractmethod
    async def cross_reference(self, record: DatabaseRecord,
                              target_db: str) -> list[CrossReference]: ...

    @property
    @abstractmethod
    def source_name(self) -> str: ...

    @property
    @abstractmethod
    def current_version(self) -> str: ...

    @property
    @abstractmethod
    def status(self) -> BridgeStatus: ...
        # BridgeStatus: ONLINE, DEGRADED, OFFLINE, RATE_LIMITED
```

**BridgeResult includes:**

```python
@dataclass
class BridgeResult:
    records: list[DatabaseRecord]
    cross_references: list[CrossReference]
    confidence_trace: ConfidenceTrace
    query_parameters: dict
    source_version: str
    retrieval_timestamp: datetime
    status: BridgeStatus
    errors: list[str]               # Non-fatal errors during query
    caveats: list[str]              # Knowledge boundary flags
```

**Query builder per database** — each bridge respects the source API's rate limits, query language, and pagination:

- UniProt: SPARQL or REST API with field selection
- AlphaFold DB: REST API with accession-based lookup
- PDB: GraphQL or REST API with structure ID query
- NCBI: E-utilities (esearch, efetch, esummary)
- InterPro: REST API with protein accession lookup

**Response parser with confidence extraction** — each bridge parses the source's response format and extracts confidence-related metadata:

- UniProt: evidence codes (ECO) from annotations
- AlphaFold: pLDDT scores from CIF/JSON, PAE matrices
- PDB: resolution, R-free, validation metrics from mmCIF headers
- NCBI: assembly quality metrics, RefSeq review status
- InterPro: E-values, domain coverage, signature database scores

**Local cache layer:**

```python
@dataclass
class CacheConfig:
    backend: str                    # "sqlite", "duckdb", "memory"
    ttl_seconds: int
    max_entries: int
    offline_mode: bool

@dataclass
class CacheEntry:
    key: str                        # Source + query hash
    result: BridgeResult
    cached_at: datetime
    expires_at: datetime
    version_at_cache: str           # Source version when cached
```

Cache staleness is always surfaced: "Returned cached result from 2026-05-15 (database version at cache: UniProt 2025_03). Current version: 2025_04."

### C. Integration with OpenSciRe Core

```
┌─────────────────────────────────────────────────────────────────┐
│                     openscire-core (Provenance DAG)              │
├──────────────┬───────────────┬───────────────┬───────────────────┤
│ openscire-   │ openscire-bio │ openscire-    │ openscire-        │
│ literature   │ (BIO BRIDGES) │ hypothesis    │ ethics            │
├──────────────┼───────────────┼───────────────┼───────────────────┤
│ PubMed       │ UniProt       │ Hypothesis    │ EthicalFirewall   │
│ arXiv        │ AlphaFold DB  │ generation    │ RiskTier          │
│ Zotero       │ PDB           │ grounded in   │ DataSovereignty   │
│ Semantic     │ NCBI/Entrez   │ real //       │ UncertaintyQuant. │
│ Scholar      │ InterPro      │ labeled data  │ CarbonBudget      │
│ OpenAlex     │ (deferred)    │               │                   │
│ Unpaywall    │               │               │                   │
└──────────────┴───────────────┴───────────────┴───────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │  Local Cache Layer  │
                    │  (SQLite/DuckDB)   │
                    └────────────────────┘
```

**Connections:**

1. **openscire-literature**: Shared adapter pattern architecture. A unified SourceAdapter base class serves both text sources (PubMed, arXiv, etc.) and structured bioinformatics sources (UniProt, PDB, etc.). Cross-source queries can join literature and bioinformatics data: "Find papers that cite PDB structure 3J1Q and retrieve UniProt annotations for its protein."

2. **openscire-hypothesis**: Biological data from bridges serves as evidence for/against hypotheses. When hypothesis generation proposes a binding mechanism, the confidence trace from underlying structural data informs the hypothesis confidence score. Hypotheses based on predicted structures (evidence type P) are automatically assigned lower confidence than those grounded in experimental data (E or R).

3. **Provenance DAG**: Every bridge query creates a provenance node recording source, version, parameters, timestamp, and confidence trace. This enables: reproducing any result, comparing results across database versions, detecting when database updates invalidate previous analyses, and generating ReproducibilityBundles.

4. **Ethics layer (Phase 3)**: Bridge data passes through:
   - DataSovereigntyChecker: flags indigenous or consent-restricted data
   - UncertaintyQuantifier: converts confidence traces to human-readable warnings
   - EthicalFirewall: blocks queries to high-risk databases (e.g., pathogen genome analysis for dual-use proteins) without proper clearance
   - RiskTier classification: analysis involving certain databases (e.g., human clinical variation from deferred OMIM bridge) triggers higher risk tier

---

## VIII. Implementation Roadmap

### Phase 4 Window — Core Bridges (alongside literature engine)

| Bridge | Priority | Dependencies | Estimated Effort |
|--------|----------|-------------|------------------|
| UniProt | P0 | requests library, rate limiting utilities | 2 weeks |
| PDB | P0 | mmCIF parsing (Biopython), REST client | 2 weeks |
| NCBI/Entrez | P0 | Biopython Entrez module, rate limiting | 2 weeks |
| AlphaFold DB | P1 (after PDB — needed to implement P/E distinction) | mmCIF/pLDDT parsing, confidence extraction | 1.5 weeks |
| InterPro | P1 | REST client, E-value parsing | 1.5 weeks |

**Total core bridge effort:** ~9 weeks (can be parallelized across 2-3 developers to ~4 weeks)

**Sub-tasks per bridge:**
1. Implement BridgeAdapter interface
2. Build query builder for source API
3. Build response parser with confidence extraction
4. Implement local caching (shared cache layer)
5. Implement cross-referencing (shared cross-ref resolver)
6. Write provenance logging
7. Write tests (unit + integration with mock API responses)
8. Write bridge documentation

### Shared Infrastructure

| Component | Description | Effort |
|-----------|-------------|--------|
| BridgeAdapter base class | Abstract interface with shared rate limiting, caching, logging | 1 week |
| CrossReferenceResolver | SIFTS mapping, sequence-based mapping, ID mapping | 1.5 weeks |
| ConfidenceTrace propagation | Propagation math, aggregation functions, visualization export | 1.5 weeks |
| Local cache layer | SQLite-backed, configurable TTL, staleness tracking | 1 week |
| Provenance logging | W3C PROV-compatible, RO-Crate export | 1 week |
| Query manifest builder | Join documentation, flattening manifests | 1 week |

### Post-Pilot — Advanced Bridges

| Bridge | Trigger Conditions | Estimated Effort |
|--------|-------------------|------------------|
| OMIM / ClinVar | Ethics layer validated on non-clinical data; consent/privacy architecture reviewed | 3 weeks each |
| GTEx / ENCODE | Multi-omics integration scoped; compression strategy for large datasets | 4 weeks |
| GEO / ArrayExpress | Streaming/download design complete; cloud backend (if needed) available | 4 weeks |
| BioGRID / STRING | Interaction data model designed; confidence metrics mapped | 3 weeks |
| KEGG / Reactome | Pathway graph traversal engine designed | 3 weeks |
| ChEMBL / DrugBank | DURC detection validated; RiskTier classification stable | 3 weeks |

### Continuous

- **Plugin architecture for community bridges**: Standardized bridge packaging, registry, documentation template, and contribution guide (post-pilot)
- **Bridge health monitoring**: Automated API status checks, version change detection, test suite against live and mock endpoints
- **Bridge retirement protocol**: When a source database is deprecated or API changes break compatibility, the bridge enters "archived" status with clear migration guidance

---

## IX. Competitive Context

### vs. Google Science Skills

| Dimension | Google Science Skills | openscire-bio |
|-----------|---------------------|---------------|
| Ontological transparency | Flattens all databases into single queryable plane | Per-database bridges preserve native ontology; flattening is explicit |
| Confidence propagation | pLDDT scores dropped in downstream analyses | pLDDT/PAE propagated through ALL analyses; never stripped |
| Prediction vs. experiment | Predicted and experimental merged without distinction | Evidence type (P/E/R) on every data point; cannot be hidden |
| Integration logic | Proprietary, black box | Open-source, auditable, join manifests documented |
| Source code | Code on GitHub, but integrated logic may be partially proprietary | Fully open-source (Apache 2.0); no proprietary middleware |
| Local-first | No — dependent on Antigravity cloud platform | Yes — SQLite caching, offline-capable, BYO-infrastructure |
| Graceful degradation | Cascading API failure: one DB down = workflow halts | Per-bridge independent failure; partial results labeled as partial |
| Version tracking | Unclear — likely temporal unmooring | Full version provenance in every query |
| Database scope | 30+ databases, including obscure/unstable ones | 5 MVP bridges, ~10 deferred, quality- over quantity-focused |
| Experimental validation bridge | None | "In silico only" labeling; experimental validation recommended on predictions; bridge stub defined |
| Reproducibility | No replication packaging documented | ReproducibilityBundle per query with locked versions |
| Knowledge boundaries | Never refuses | Explicit refusal for low-confidence, insufficient data, or high-risk queries |

Science Skills is a proprietary, cloud-dependent, black-box integration layer that trades ontological fidelity for speed. openscire-bio is an open-source, local-first, transparency-maximizing bridge layer that trades nothing — it surfaces what it knows, what it does not know, and what it cannot know. [07_science_skills.md (all sections)](../../critiques/07_science_skills.md)

### vs. Traditional Bioinformatics Tools (PyMOL, BLAST, Benchling)

openscire-bio is not a replacement for these tools. It is an AI-assisted integration layer that works alongside them:

- **PyMOL / ChimeraX**: openscire-bio provides structured structural data that can be loaded into these visualization tools. It does not replace molecular visualization.
- **BLAST / HMMER**: openscire-bio bridges to NCBI and InterPro, which provide sequence search capabilities. Direct BLAST integration is downstream.
- **Benchling / DNAnexus**: openscire-bio is open-source and local-first, not a commercial platform. It can complement these platforms by providing an auditable, transparent data ingestion path.
- **Biopython / BioPerl**: openscire-bio is a higher-level integration layer that uses Biopython internally for format parsing. It does not replace these libraries — it orchestrates them.

### vs. Commercial Bioinformatics Platforms

| Dimension | Benchling / DNAnexus / Seven Bridges | openscire-bio |
|-----------|--------------------------------------|---------------|
| Cost | Enterprise licensing, per-user fees | Free and open-source |
| Deployment | Cloud-only (SaaS) | Local-first, self-hosted |
| Auditability | Limited — proprietary pipeline logic | Full open-source transparency |
| Data sovereignty | Vendor-controlled | User-controlled (BYO-infrastructure) |
| Community contribution | Closed ecosystem | Plugin architecture for community bridges |
| Confidence propagation | Not a design principle | Core architectural feature |
| Evidence type labeling | Not a design principle | Mandatory for every data point |

---

## X. Limitations Acknowledged

Per the project's fiduciary tone and AGENTS.md requirement to surface epistemic uncertainty, here is an honest accounting of what openscire-bio does NOT do:

1. **Multi-omics integration deferred**: Connecting genotype (genome), transcriptome (RNA-seq), proteome (mass spec), metabolome, and phenotype in a unified analysis is a research program, not a feature set. openscire-bio focuses on protein-centric databases (structure, sequence, domain, annotation) for MVP. Multi-omics integration is explicitly post-pilot scope. [07_science_skills.md §IV.19](../../critiques/07_science_skills.md)

2. **Clinical/phenotypic databases deferred**: OMIM, ClinVar, HPO, and gnomAD require additional ethical review architecture before integration. Clinical data has consent constraints, privacy requirements (HIPAA/GDPR), and dual-use considerations that the Phase 3 ethics layer must fully address before implementation. [07_science_skills.md §IV.20](../../critiques/07_science_skills.md)

3. **Local-first scaling limits**: openscire-bio is designed for individual researchers and small labs (the "missing middle"). For petabyte-scale genomics (thousands of whole genomes, single-cell atlases with millions of cells), local-first architecture hits bandwidth, storage, and compute ceilings. A cloud-backed enterprise tier is deferred until funding materializes. [07_science_skills.md §III.15](../../critiques/07_science_skills.md)

4. **No wet-lab experimental validation bridge**: openscire-bio cannot order primers, run assays, or close the loop from in silico prediction to bench verification. This is a fundamental limitation — computational biology is not biology. All predicted findings carry the flag: "experimental validation recommended." [07_science_skills.md §II.7](../../critiques/07_science_skills.md)

5. **No phylogenetic reconstruction**: Evolutionary inference (tree building, ancestral sequence reconstruction, molecular dating) is a distinct computational capability outside bridge scope. openscire-bio provides sequence data for such analyses but does not perform them. [07_science_skills.md §IV.22](../../critiques/07_science_skills.md)

6. **No spatiotemporal or cellular context**: A protein's function depends on cellular localization, post-translational modifications, interactome context, developmental timing, and environmental conditions. openscire-bio returns database annotations that are largely decontextualized. This is a limitation of the underlying databases, not just the bridge. [07_science_skills.md §I.4](../../critiques/07_science_skills.md)

7. **Plugin ecosystem is post-pilot**: Community-contributed bridges (for format X, database Y, or data type Z) are architecturally supported but not yet built. The plugin interface, registry, documentation template, and governance model are post-pilot scope.

8. **No model organism bias compensation (yet)**: While openscire-bio supports the full NCBI taxonomy and surfaces knowledge boundaries for under-annotated species, it does not structurally compensate for the model organism bias inherent in the underlying databases. A biodiversity-aware data augmentation layer is a research direction, not an MVP feature. [07_science_skills.md §I.3](../../critiques/07_science_skills.md)

9. **No negative knowledge archive**: openscire-bio queries databases that record positive findings. Failed experiments, negative screens, and abandoned targets are structurally absent from the underlying sources. The Negative Result Registry (Phase 3 ethics layer) provides a stub for manual recording, but automated negative knowledge retrieval is not possible. [07_science_skills.md §I.5](../../critiques/07_science_skills.md)

10. **Confidence propagation is heuristic, not rigorous**: The cumulative uncertainty calculations in openscire-bio are pragmatic approximations, not mathematically rigorous error propagation (which would require full covariance knowledge across databases). The confidence trace tells you where uncertainty originates and how it compounds, but it does not provide formal confidence intervals on derived quantities. This is acknowledged in the documentation and surfaced through caveats.

These limitations are not design failures. They are design boundaries — epistemic firebreaks that prevent the tool from overpromising. openscire-bio cannot do everything Science Skills claims to do, but it can do what it does transparently, honestly, and verifiably. That is the tradeoff the project makes, explicitly and unapologetically: **we will know less, but we will know what we know, why we know it, and how uncertain we are.**

---

## XI. Glossary of Abbreviations

| Abbreviation | Full Term |
|---|---|
| PDB | Protein Data Bank |
| pLDDT | Predicted Local Distance Difference Test (AlphaFold confidence metric) |
| PAE | Predicted Aligned Error (AlphaFold metric) |
| IDR | Intrinsically Disordered Region |
| SIFTS | Structure Integration with Function, Taxonomy and Sequences (EBI cross-reference resource) |
| ECO | Evidence Code Ontology |
| HPO | Human Phenotype Ontology |
| GO | Gene Ontology |
| OMIM | Online Mendelian Inheritance in Man |
| ClinVar | Clinical Variant database |
| DURC | Dual-Use Research of Concern |
| FAIR | Findable, Accessible, Interoperable, Reusable |
| RO-Crate | Research Object Crate (packaging format) |
| W3C PROV | W3C Provenance standard |
| CWL | Common Workflow Language |
| BYOK | Bring Your Own Key |

---

## XII. References

1. [01_overview.md](../../critiques/01_overview.md) — Ecosystem context for Gemini for Science
2. [02_philosophy.md](../../critiques/02_philosophy.md) — Philosophical gaps in the Gemini for Science approach
3. [03_structural_triad.md](../../critiques/03_structural_triad.md) — Structural gaps in the three-tool framework
4. [07_science_skills.md](../../critiques/07_science_skills.md) — Primary critique of Science Skills (48 gaps)
5. [08_miscellaneous.md](../../critiques/08_miscellaneous.md) — Cross-cutting gaps (legal, security, governance, systemic)
6. [03_ethics_layer.md](../../docs/phases/03_ethics_layer.md) — Phase 3 ethics layer implementation plan
7. [04_literature_engine.md](../../docs/phases/04_literature_engine.md) — Phase 4 literature engine implementation plan (shared adapter pattern)
8. [business-brief.md](../../docs/business-brief.md) — Strategic context and monetization approach
9. [AGENTS.md](../../AGENTS.md) — Project conventions and architectural principles

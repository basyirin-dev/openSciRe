# Phase 10 — Jupyter Lab Extension

**Duration**: 3 weeks (Jan 2027)
**Dependencies**: Phase 4 (literature), Phase 5 (RAG), Phase 8 (CLI — shares core)
**Output**: Installable Jupyter Lab extension with inline research tools

---

### Task 10.1: Extension Scaffold

- [ ] 10.1.1: Jupyter Lab extension cookiecutter or manual scaffold
- [ ] 10.1.2: `package.json` for extension with `jupyterlab` keyword
- [ ] 10.1.3: TypeScript configuration (`tsconfig.json`)
- [ ] 10.1.4: Python-side extension setup (setup.py/pyproject.toml with jupyterlab entry points)
- [ ] 10.1.5: Extension activation test — `jupyter labextension list` shows openscire-jupyter
- [ ] 10.1.6: Backend Python kernel extension (`openscire_jupyter/extension.py`)

### Task 10.2: Sidebar Panels

- [ ] 10.2.1: Literature search panel — search bar, source selector, results list, sort/filter
- [ ] 10.2.2: Hypothesis panel — research question input, agent workflow trigger, results display with confidence bars
- [ ] 10.2.3: Provenance explorer panel — interactive graph visualization (D3.js/Cytoscape.js), node detail on click, export buttons
- [ ] 10.2.4: NegativeResultRegistry browser — search, filter, detail view
- [ ] 10.2.5: Embedding index query panel — semantic search within user's local index

### Task 10.3: Cell Magic `%%openscire`

- [ ] 10.3.1: `%%openscire search <query>` — returns structured results in notebook cell
- [ ] 10.3.2: `%%openscire read <id>` — displays paper summary in notebook cell
- [ ] 10.3.3: `%%openscire hypothesize <question>` — runs full agent workflow, displays results
- [ ] 10.3.4: `%%openscire provenance` — display provenance graph inline
- [ ] 10.3.5: Magic output as rich HTML/widget (not plain text)
- [ ] 10.3.6: Magic state persistence — results stored in kernel state between cells

### Task 10.4: Provenance Visualization

- [ ] 10.4.1: DAG rendering — agent interaction graph with node types (hypothesis, evidence, review, flag)
- [ ] 10.4.2: Node detail on click — show full provenance entry for any node
- [ ] 10.4.3: Time-based sliding — view provenance evolution over session timeline
- [ ] 10.4.4: Export — export visualization as PNG, SVG, or interactive HTML
- [ ] 10.4.5: Signature verification indicator — green checkmark for verified entries, red for tampered

### Task 10.5: Distribution Packaging

- [ ] 10.5.1: PyPI-ready `pyproject.toml` for `openscire-jupyter` package
- [ ] 10.5.2: Conda recipe skeleton for `conda-forge` distribution
- [ ] 10.5.3: Extension install instructions — `pip install openscire-jupyter && jupyter labextension install openscire-jupyter`

### Task 10.6: Jupyter Tests

- [ ] 10.6.1: Unit tests for cell magic parsing (parameter extraction, error handling)
- [ ] 10.6.2: Unit tests for sidebar panel components (filtering, display logic)
- [ ] 10.6.3: Integration test: `%%openscire search` → results displayed, `%%openscire hypothesize` → agents run
- [ ] 10.6.4: Manual test: Jupyter Lab launches with extension, sidebar panels load, magic commands work

---

**Phase 10 Exit Criteria**: `%%openscire` magic commands work in Jupyter. Sidebar panels display search, hypothesis, provenance, and negative registry. Extension installs via pip.

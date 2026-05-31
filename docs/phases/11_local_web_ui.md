# Phase 11 — Local Web UI *(Deferred to Post-YC)*

**Status**: **DEFERRED**. Not on critical path. Local web UI replaces Tauri desktop app. Build only if CLI + Jupyter are insufficient for pilot labs.

---

### Task 11.1: Local FastAPI Server (if/when built)

- [ ] 11.1.1: FastAPI application with OpenAPI docs
- [ ] 11.1.2: REST endpoints mirroring CLI subcommands
- [ ] 11.1.3: WebSocket support for streaming agent output
- [ ] 11.1.4: CORS configuration for localhost origins
- [ ] 11.1.5: API key middleware for local BYOK management

### Task 11.2: React Frontend (if/when built)

- [ ] 11.2.1: React application with TypeScript
- [ ] 11.2.2: Literature search and reading interface
- [ ] 11.2.3: Hypothesis generation workflow UI
- [ ] 11.2.4: Provenance graph visualization (D3/Cytoscape)
- [ ] 11.2.5: BYOK configuration page
- [ ] 11.2.6: True offline operation (ServiceWorker, IndexedDB cache)
- [ ] 11.2.7: Sync-when-connected protocol for field researcher use cases

---

**Phase 11 Exit Criteria**: N/A — deferred. When executed, must pass all CLI integration tests and work fully offline.

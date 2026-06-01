# Cross-Cutting Concerns

Applies to all phases. These requirements are not owned by any single phase and must be satisfied throughout development.

---

## R / Julia / MATLAB Bridges (Track C, Nov–Dec)

Lightweight integration examples only — not a full phase. Build during Phase 7 window.

- [ ] C.1: R integration via `reticulate` — example notebook showing `library(reticulate); openscire <- import("openscire")`
- [ ] C.2: Julia integration via `PyCall` — example: `using PyCall; openscire = pyimport("openscire")`
- [ ] C.3: MATLAB integration via Python engine — example: `py.openscire.search("query")`
- [ ] C.4: Documentation page for each language — "Using openSciRe from R/Julia/MATLAB"
- [ ] C.5: Test that all three integration paths work in CI

---

## Provenance Pervasiveness

Every phase after Phase 1 must:
- [x] Accept a `provenance_parent_id` parameter
- [x] Generate `ProvenanceEntry` outputs for all significant operations
- [x] Sign entries with Ed25519 before persisting
- [x] Fail gracefully if provenance cannot be recorded (log warning, continue)

---

## Ethical Checkpoints

Every phase after Phase 3 must:
- [ ] Check EthicalFirewall before generating any claim
- [ ] Log RiskTier classification in provenance
- [ ] Display carbon cost estimate for compute-heavy operations
- [ ] Flag unsupported claims and require citations before final output

---

## Testing Requirements

All phases:
- [x] Minimum 80% test coverage (line coverage) for new code
- [x] All tests pass before phase exit
- [x] Integration test for cross-phase workflows
- [x] Security test for data handling (no secrets in logs, no plaintext keys)
- [x] Offline test (no network required for unit tests)

---

## Documentation Requirements

All phases:
- [x] Docstrings for all public APIs (Google-style or NumPy-style)
- [x] README in each package directory explaining purpose and status
- [x] CHANGELOG entry for significant additions
- [x] Update local agent configuration if directory structure changes

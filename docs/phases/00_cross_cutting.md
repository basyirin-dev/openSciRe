# Cross-Cutting Concerns

Applies to all phases. These requirements are not owned by any single phase and must be satisfied throughout development.

---

## R / Julia / MATLAB Bridges (Track C, Nov–Dec)

Lightweight integration examples only — not a full phase. Build during Phase 7 window.

- [ ] C.1: R integration via `reticulate` — example notebook showing `library(reticulate); skepsis <- import("skepsis")`
- [ ] C.2: Julia integration via `PyCall` — example: `using PyCall; skepsis = pyimport("skepsis")`
- [ ] C.3: MATLAB integration via Python engine — example: `py.skepsis.search("query")`
- [ ] C.4: Documentation page for each language — "Using Skepsis from R/Julia/MATLAB"
- [ ] C.5: Test that all three integration paths work in CI

---

## Provenance Pervasiveness

Every phase after Phase 1 must:
- [ ] Accept a `provenance_parent_id` parameter
- [ ] Generate `ProvenanceEntry` outputs for all significant operations
- [ ] Sign entries with Ed25519 before persisting
- [ ] Fail gracefully if provenance cannot be recorded (log warning, continue)

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
- [ ] Minimum 80% test coverage (line coverage) for new code
- [ ] All tests pass before phase exit
- [ ] Integration test for cross-phase workflows
- [ ] Security test for data handling (no secrets in logs, no plaintext keys)
- [ ] Offline test (no network required for unit tests)

---

## Documentation Requirements

All phases:
- [ ] Docstrings for all public APIs (Google-style or NumPy-style)
- [ ] README in each package directory explaining purpose and status
- [ ] CHANGELOG entry for significant additions
- [ ] Update local agent configuration if directory structure changes

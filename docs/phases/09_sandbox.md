# Phase 9 — Rust Sandbox (Design Only → Implementation Deferred)

**Duration**: 2 weeks (Jul 2026, parallel with Phase 1)
**Dependencies**: Phase 1 (config, package structure)
**Output**: Design documentation, threat model, API contract, stubs → implementation deferred to post-YC

---

### Task 9.1: Sandbox Design Documentation

- [ ] 9.1.1: Sandboxing strategy document — compare seccomp-BPF, landlock, nsjail, Firecracker for scientific code execution
- [ ] 9.1.2: Threat model — attack surfaces (malicious code execution, resource exhaustion, filesystem escape, network abuse), trust boundaries (user code vs. system code vs. LLM output)
- [ ] 9.1.3: Resource containment design — CPU limits (cgroups), memory limits, filesystem access (tmpfs overlay), network access (none by default), execution time limits
- [ ] 9.1.4: Reproducibility requirements — deterministic execution, random seed capture, dependency pinning, filesystem snapshot
- [ ] 9.1.5: Performance budget — acceptable overhead for sandboxing (target: <10% for compute-bound, <50ms startup time)

### Task 9.2: API Contract

- [ ] 9.2.1: `SandboxConfig` model — time_limit, memory_limit, network_access, filesystem_mounts, env_vars, dependencies
- [ ] 9.2.2: `execute_code(source, language, config)` → `ExecutionResult` — stdout, stderr, exit_code, execution_time, resource_usage, provenance_entry
- [ ] 9.2.3: PyO3 binding interface — Python-callable sandbox functions
- [ ] 9.2.4: Supported languages — Python (with pinned version), R (via RPy2 or compiled), Julia, bash, C++ (compiled)
- [ ] 9.2.5: ExecutionResult model in Python-side

### Task 9.3: Cargo Workspace Stubs

- [ ] 9.3.1: `skepsis-sandbox-core/Cargo.toml` — with PyO3 dependency (version pinned), seccomp crate, serde for serialization
- [ ] 9.3.2: `skepsis-sandbox-core/src/lib.rs` — `execute_code()` stub that returns unimplemented error
- [ ] 9.3.3: `skepsis-sandbox-core/src/sandbox.rs` — trait definitions, no implementation
- [ ] 9.3.4: `skepsis-sandbox-core/src/config.rs` — `SandboxConfig` struct (Rust-side)
- [ ] 9.3.5: `skepsis-sandbox-core/src/errors.rs` — error enum
- [ ] 9.3.6: `cargo build` succeeds (stubs only, no runtime sandboxing)

### Task 9.4: Deferral Documentation

- [ ] 9.4.1: README in `skepsis-sandbox-core/` explaining deferred status and design decisions
- [ ] 9.4.2: Link from Phase 9 entry in `docs/phase-roadmap.md` to deferred status
- [ ] 9.4.3: "Implementation ready" checklist for when sandbox work resumes post-YC

---

**Phase 9 Exit Criteria**: Design doc written, threat model complete, API contract defined, Cargo workspace compiles with stubs, deferral acknowledged in roadmap.

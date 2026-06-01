# Phase 9 — Rust Sandbox (Working MVP)

**Duration**: 3 weeks (Jul 2026, parallel with Phase 1)
**Dependencies**: Phase 1 (config, package structure)
**Output**: Working sandbox capable of executing Python code securely with seccomp, tmpfs, cgroups, and PyO3 bridge

> **Design**: Opens fine-grained execution environment for LLM-generated code via seccomp-bpf + cgroups v2 + tmpfs isolation.
> **Post-pilot features** (deferred): Multi-criteria evaluation, carbon tracking, DURC detection for code, multi-language support beyond Python, NegativeResultRegistry integration.

---

### Task 9.1: Sandbox Design Documentation

- [ ] 9.1.1: Sandboxing strategy document — compare seccomp-BPF, landlock, nsjail, Firecracker for scientific code execution
- [ ] 9.1.2: Threat model — attack surfaces (malicious code execution, resource exhaustion, filesystem escape, network abuse), trust boundaries (user code vs. system code vs. LLM output)
- [ ] 9.1.3: Resource containment design — CPU limits (cgroups), memory limits, filesystem access (tmpfs overlay), network access (none by default), execution time limits
- [ ] 9.1.4: Reproducibility requirements — deterministic execution, random seed capture, dependency pinning, filesystem snapshot
- [ ] 9.1.5: Performance budget — acceptable overhead for sandboxing (target: <10% for compute-bound, <50ms startup time)

### Task 9.2: Pydantic Models (Python-side)

- [ ] 9.2.1: `SandboxConfig` — time_limit, memory_limit_mb, network_access, filesystem_mounts, env_vars, dependencies (pip requirements list), language (default: python), random_seed
- [ ] 9.2.2: `ExecutionResult` — stdout, stderr, exit_code, execution_time_ms, memory_peak_mb, sandbox_exit_reason (completed, time_limit, memory_limit, internal_error), provenance_entry_id, reproducibility_bundle
- [ ] 9.2.3: `SandboxEnvironment` — captured environment snapshot: pip_freeze, python_version, cpu_info, kernel_version
- [ ] 9.2.4: `StaticAnalysisResult` — dangerous_imports_found, filesystem_access_patterns, network_calls, allowed, reason

### Task 9.3: seccomp-bpf Filter Construction

- [ ] 9.3.1: Define whitelist syscall set for safe Python execution (~60 syscalls: read, write, openat, mmap, brk, clone, exit_group, etc.)
- [ ] 9.3.2: Block dangerous syscalls: ptrace, perf_event_open, bpf, kexec_load, swapon, mount, umount2, pivot_root, ioperm, iopl, acct, chroot
- [ ] 9.3.3: Block network syscalls by default: socket, connect, bind, listen, accept, sendto, recvfrom (configurable via SandboxConfig.network_access)
- [ ] 9.3.4: Block filesystem-write outside tmpfs: only allow writes to paths under the sandbox workspace
- [ ] 9.3.5: Audit logging for blocked syscalls with reason codes
- [ ] 9.3.6: Filter testing — verify each blocked syscall returns -EPERM with expected audit log

### Task 9.4: tmpfs Workspace Management

- [ ] 9.4.1: tmpfs creation on execution start — mount at `/tmp/openscire-sandbox-{run_id}` with configurable size limit (default: 1GB)
- [ ] 9.4.2: Workspace population — copy user-provided files into tmpfs (data files, scripts)
- [ ] 9.4.3: Output extraction on completion — copy files from tmpfs back to host
- [ ] 9.4.4: Workspace teardown — unmount and discard tmpfs, zero-fill before discard for security
- [ ] 9.4.5: Nested tmpfs isolation — each execution gets a fresh, empty tmpfs; no persistence between runs

### Task 9.5: cgroups v2 Memory Controller

- [ ] 9.5.1: cgroup creation per execution — create child cgroup under system slice
- [ ] 9.5.2: Memory limit enforcement — set `memory.max` from SandboxConfig.memory_limit_mb
- [ ] 9.5.3: OOM kill handling — monitor `memory.events` for OOM kills, map to ExecutionResult.sandbox_exit_reason = memory_limit
- [ ] 9.5.4: Memory peak tracking — read `memory.peak` after execution, populate ExecutionResult.memory_peak_mb
- [ ] 9.5.5: Swap control — set `memory.swap.max = 0` to prevent swap-based memory evasion
- [ ] 9.5.6: Cgroup cleanup — remove cgroup after execution completion, handle stale cgroup edge case

### Task 9.6: Process Isolation

- [ ] 9.6.1: PID namespace — create new PID namespace for each execution, process tree isolation
- [ ] 9.6.2: Orphan prevention — ensure all child processes are killed when sandbox exits (process group kill with SIGKILL)
- [ ] 9.6.3: Time limit enforcement — use timerfd to SIGKILL execution group after SandboxConfig.time_limit
- [ ] 9.6.4: Process tree capture — log all spawned PIDs and their commands for audit

### Task 9.7: PyO3 Bridge

- [ ] 9.7.1: `openscire-sandbox-core/Cargo.toml` — PyO3 dependency, seccomp crate (libseccomp-sys or seccompiler), nix crate for namespaces/cgroups, serde
- [ ] 9.7.2: `execute(code: &str, config: &PySandboxConfig) -> PyExecutionResult` — Python-callable function exposed via PyO3
- [ ] 9.7.3: `static_analyze(code: &str) -> PyStaticAnalysisResult` — pre-execution analysis
- [ ] 9.7.4: Python package wrapper — `openscire.sandbox` module that imports the PyO3 native module and provides Pythonic API
- [ ] 9.7.5: Error handling — map Rust errors to Python exceptions (SandboxError, TimeoutError, MemoryError, AnalysisError)
- [ ] 9.7.6: Async support — expose `async execute()` for non-blocking sandbox calls from Python asyncio

### Task 9.8: Environment Capture

- [ ] 9.8.1: pip freeze lockfile — capture installed package versions before execution
- [ ] 9.8.2: Dependency tree capture — `pipdeptree`-style dependency graph
- [ ] 9.8.3: Hardware profile capture — CPU model, core count, RAM, GPU (if available), kernel version
- [ ] 9.8.4: Python environment capture — interpreter path, version, venv path
- [ ] 9.8.5: Store as `ReproducibilityBundle.environment` field

### Task 9.9: Random Seed Capture & Control

- [ ] 9.9.1: Python random seed setting — inject `random.seed(seed)` at top of executed code
- [ ] 9.9.2: numpy seed setting — inject `numpy.random.seed(seed)` if numpy is imported
- [ ] 9.9.3: torch seed setting — inject `torch.manual_seed(seed)` and `torch.cuda.manual_seed_all(seed)` if torch is imported
- [ ] 9.9.4: Unseeded library detection — scan imports for stochastic libraries without seed control; warn in ExecutionResult
- [ ] 9.9.5: Seed override — user can specify seed in SandboxConfig; random seed if not specified

### Task 9.10: Static Analysis Pre-Execution

- [ ] 9.10.1: Import scanner — extract all `import` and `from ... import` statements from code
- [ ] 9.10.2: Dangerous import classification — match against blocklist (os.system, subprocess, shutil, socket, requests, urllib, paramiko, ctypes, pickle)
- [ ] 9.10.3: Filesystem access pattern detection — scan for `open()`, `os.path`, `pathlib` operations outside allowed paths
- [ ] 9.10.4: Network call detection — scan for `urllib.request`, `requests.get/post`, `socket.connect`
- [ ] 9.10.5: Analysis result — return StaticAnalysisResult before execution; block execution if dangerous patterns found above configurable threshold
- [ ] 9.10.6: Allowlist mechanism — user can pre-approve specific imports/patterns per session

### Task 9.11: Output Sanitization

- [ ] 9.11.1: Path stripping — remove absolute filesystem paths from stdout/stderr (replace with `<sandbox-path>`)
- [ ] 9.11.2: Environment variable redaction — replace env var values in output with `***`
- [ ] 9.11.3: Stack trace sanitization — strip internal sandbox frame references from Python tracebacks
- [ ] 9.11.4: Large output truncation — truncate stdout/stderr beyond configurable limit (default: 1MB), flag in ExecutionResult

### Task 9.12: Sandbox Tests

- [ ] 9.12.1: Unit tests for SandboxConfig model — validation, defaults, serialization
- [ ] 9.12.2: Unit tests for seccomp filter — verify each blocked syscall returns -EPERM
- [ ] 9.12.3: Unit tests for tmpfs workspace — creation, population, extraction, teardown
- [ ] 9.12.4: Unit tests for cgroups — memory limit enforcement, OOM detection, cleanup
- [ ] 9.12.5: Unit tests for process isolation — orphan prevention, time limit enforcement
- [ ] 9.12.6: Unit tests for static analysis — dangerous import detection, network call detection
- [ ] 9.12.7: Unit tests for output sanitization — path stripping, env redaction, truncation
- [ ] 9.12.8: Integration test: execute simple Python code → verify stdout, exit code, execution time
- [ ] 9.12.9: Integration test: execute memory-intensive code → verify OOM kill → verify memory_limit exit reason
- [ ] 9.12.10: Integration test: execute infinite loop → verify timeout kill
- [ ] 9.12.11: Integration test: execute code with dangerous import → verify static analysis blocks it
- [ ] 9.12.12: Integration test: random seed capture → execute twice with same seed → verify identical output
- [ ] 9.12.13: Security test: attempt filesystem escape → verify tmpfs containment
- [ ] 9.12.14: Security test: attempt network connection → verify seccomp blocks socket syscall
- [ ] 9.12.15: Benchmark test: sandbox overhead <10% for compute-bound tasks

---

**Phase 9 Exit Criteria**: Working Rust sandbox with PyO3 bridge. Can execute Python code with seccomp syscall filtering, tmpfs workspace isolation, cgroups memory limits, and time limits. Static analysis blocks dangerous imports. Random seeds captured for reproducibility. All tests pass including security escape attempts.

**Post-pilot features (not tasked here)**:
- Multi-criteria evaluation engine (Pareto front optimization)
- CarbonBudgetTracker integration (compute cost per execution)
- EthicalFirewall for code (DURC detection in generated code)
- Multi-language support (R, Julia, bash, C++)
- NegativeResultRegistry integration
- Full ReproducibilityBundle with Ed25519-signed RO-Crate export

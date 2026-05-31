# Phase 14 — Distribution & DevOps Maturity

**Duration**: Ongoing / Incremental
**Dependencies**: Phase 0 (foundation)
**Output**: Multi-platform distribution, mature CI/CD, documentation site

---

### Task 14.1: PyPI Publishing

- [ ] 14.1.1: Configure PyPI trusted publishing (OpenID Connect via GitHub Actions)
- [ ] 14.1.2: Set up `publish.yml` GitHub Action — triggered on tag push (`v*`)
- [ ] 14.1.3: Build wheel and source distribution
- [ ] 14.1.4: Publish `skepsis-core` and `skepsis-jupyter` to PyPI
- [ ] 14.1.5: Release notes automation from CHANGELOG.md

### Task 14.2: Conda/Bioconda Publishing

- [ ] 14.2.1: Create `conda.recipe/meta.yaml` for `skepsis-core`
- [ ] 14.2.2: Submit to `conda-forge` feedstock
- [ ] 14.2.3: Submit to `bioconda` (for bioinformatics-specific audience)
- [ ] 14.2.4: Verify `conda install skepsis-core -c conda-forge` works

### Task 14.3: nixpkgs Submission

- [ ] 14.3.1: Create Nix derivation for `skepsis-core`
- [ ] 14.3.2: Test with `nix-build`
- [ ] 14.3.3: Submit to nixpkgs (if project has traction)

### Task 14.4: Docker + Docker Compose

- [ ] 14.4.1: `Dockerfile` for skepsis-core CLI
- [ ] 14.4.2: `Dockerfile` for API server (when built)
- [ ] 14.4.3: `docker-compose.yml` — one-command self-hosted deployment
- [ ] 14.4.4: Docker image published to GitHub Container Registry

### Task 14.5: npm Publishing (if web UI built)

- [ ] 14.5.1: npm package for web UI (if/applicable)
- [ ] 14.5.2: GitHub Action for npm publish

### Task 14.6: Homebrew Tap

- [ ] 14.6.1: Create Homebrew formula for `skepsis` CLI
- [ ] 14.6.2: Test `brew install skepsis` on macOS and Linux
- [ ] 14.6.3: Create `homebrew-skepsis` tap repository

### Task 14.7: GitHub Actions CI/CD

- [ ] 14.7.1: `ci.yml` — run on every push/PR: lint → typecheck → test (with matrix: Python 3.12, 3.13, 3.14)
- [ ] 14.7.2: `coverage.yml` — upload coverage report to Codecov or Coveralls
- [ ] 14.7.3: `publish.yml` — publish to PyPI on tag push
- [ ] 14.7.4: `docker.yml` — build and push Docker image
- [ ] 14.7.5: `docs.yml` — build and deploy documentation site
- [ ] 14.7.6: Status badges in README

### Task 14.8: Documentation Site

- [ ] 14.8.1: Choose and configure static site generator (MkDocs with Material theme or Docusaurus)
- [ ] 14.8.2: Getting started guide — install, first commands, configuration
- [ ] 14.8.3: Tutorial — "From research question to hypothesis in 15 minutes"
- [ ] 14.8.4: Architecture documentation — how phases fit together, data flow diagrams
- [ ] 14.8.5: API reference — auto-generated from Python docstrings
- [ ] 14.8.6: Ethical guidelines — dual-use policy, responsible use, citation requirements
- [ ] 14.8.7: FAQ — "Is my data sent to the cloud?", "Can I use this with my lab's VPN?"

### Task 14.9: Telemetry (Opt-In)

- [ ] 14.9.1: Anonymous usage telemetry — command usage frequency, error rates, performance metrics
- [ ] 14.9.2: No data collection from local-only mode
- [ ] 14.9.3: Opt-in consent prompt on first use
- [ ] 14.9.4: Telemetry dashboard for project maintainers

---

**Phase 14 Exit Criteria**: PyPI + conda-forge publishing works. Docker Compose self-hosted deployment works. CI passes on every PR. Documentation site is live.

# Contributing to openSciRe

Thank you for considering contributing. This project has an explicit ethical
stance — please read [RESPONSIBLE_DISCLOSURE.md](RESPONSIBLE_DISCLOSURE.md)
before contributing.

## Code of Conduct

We are committed to fostering an open and respectful community. Be collegial.
Assume good faith. Disagreement about technical decisions is fine; personal
attacks are not. If you witness unacceptable behavior, report it to
`conduct@openscire.dev`.

## Development Setup

1. **Prerequisites**: Python 3.12+, Rust toolchain (if working on sandbox),
   pre-commit (`pip install pre-commit`)
2. **Install**: `pip install -e ".[dev]"`
3. **Install hooks**: `pre-commit install`
4. **Verify**: `make all` passes

## Coding Standards

- **Python**: snake_case for modules/functions/variables, PascalCase for classes.
  Type hints required on all public functions.
- **Rust**: snake_case for functions/variables, PascalCase for types. Idiomatic
  error handling (`Result`, `?`).
- **Formatting**: `ruff format` (Python), `cargo fmt` (Rust).
- **Imports**: Sorted via `ruff check --fix` (I ruleset).

## Pull Request Workflow

1. Create a feature branch from `main`
2. Make your changes
3. Run `make all` (lint, format check, typecheck, test, build)
4. Open a PR. Keep it focused — one logical change per PR.
5. Respond to review feedback promptly.

## Ethical Contribution Guidelines

By submitting a PR, you affirm:

- Your contribution does not weaken the Ethical Firewall, provenance system,
  or any safety mechanism.
- You have considered dual-use implications of your contribution.
- You have not added cloud-only functionality without ensuring a local-first
  alternative path exists.

## Licensing

All contributions are licensed under Apache 2.0. If you're contributing on
behalf of an employer, ensure they're okay with this.

## Questions?

Open a [Discussion](https://github.com/OpenSciRe/openSciRe/discussions)
or reach out to `dev@openscire.dev`.

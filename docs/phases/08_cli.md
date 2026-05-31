# Phase 8 — CLI Application

**Duration**: 3 weeks (Dec 2026)
**Dependencies**: Phase 6 (agents), Phase 7 (hypothesis)
**Output**: Working `skepsis` CLI with end-to-end research workflow

---

### Task 8.1: CLI Framework

- [ ] 8.1.1: Application entry point (`skepsis/__main__.py` or `cli/__init__.py`)
- [ ] 8.1.2: Subcommand structure with Typer (or Click)
- [ ] 8.1.3: Global options: `--config`, `--verbose`, `--output-format`, `--model`, `--provider`
- [ ] 8.1.4: Config auto-initialization — `skepsis config init` creates default config
- [ ] 8.1.5: Version display — `skepsis --version`
- [ ] 8.1.6: Shell completion — `skepsis completion` generates bash/zsh/fish completions
- [ ] 8.1.7: Help documentation — well-structured `--help` for every subcommand

### Task 8.2: Core Subcommands

- [ ] 8.2.1: `skepsis search <query>` — search literature, display results as table, options: `--source`, `--limit`, `--year-range`, `--domain`, `--language`
- [ ] 8.2.2: `skepsis read <identifier>` — fetch and display paper, options: `--format` (text, json, bibtex), `--extract` (figures, references), `--show-retractions`
- [ ] 8.2.3: `skepsis hypothesize <research-question>` — full workflow, options: `--serendipity`, `--agents`, `--timeout`, `--output`, `--tier`
- [ ] 8.2.4: `skepsis review <hypothesis-id>` — run falsification/ethics review on existing hypothesis
- [ ] 8.2.5: `skepsis provenance <session-id>` — display provenance graph, options: `--export` (json, ro-crate, prov), `--verify` (check signatures), `--visualize`
- [ ] 8.2.6: `skepsis config` — config management subcommand group: `init`, `set`, `get`, `list`, `edit`, `validate`, `export`
- [ ] 8.2.7: `skepsis negative-registry` — registry subcommand group: `list`, `search`, `show`, `export`, `stats`
- [ ] 8.2.8: `skepsis providers` — list configured providers and models, test connection: `list`, `test`, `capabilities`
- [ ] 8.2.9: `skepsis carbon` — carbon usage: `status`, `report`, `reset-budget`, `config`

### Task 8.3: Structured Output Piping

- [ ] 8.3.1: `--output-format json` — structured JSON output for all subcommands
- [ ] 8.3.2: `--output-format yaml` — YAML output for config-heavy commands
- [ ] 8.3.3: `--output-format csv` — CSV output for tabular data
- [ ] 8.3.4: `--output-format markdown` — nicely formatted markdown
- [ ] 8.3.5: `--quiet` flag — suppress all non-output (for piping: `skepsis search "X" --quiet --output-format json | jq`)
- [ ] 8.3.6: Pipe-compatible error handling — errors go to stderr, results go to stdout

### Task 8.4: Rich Terminal Output

- [ ] 8.4.1: `rich` (or textual) for formatted tables, syntax-highlighted code, progress bars
- [ ] 8.4.2: Literature search results as sortable, scrollable tables
- [ ] 8.4.3: Hypothesis display with confidence bars, source counts, contradiction indicators
- [ ] 8.4.4: Provenance graph as ASCII/tree visualization
- [ ] 8.4.5: Progress spinners for long-running operations (model inference, literature search)
- [ ] 8.4.6: Color output: green (verified), yellow (uncertain), red (contradicted), cyan (citation)
- [ ] 8.4.7: No-color mode (`--no-color` or `NO_COLOR` env var)

### Task 8.5: BYOK Configuration Workflow

- [ ] 8.5.1: `skepsis config set provider.litellm.api_key` — interactive or CLI-arg
- [ ] 8.5.2: `skepsis config set provider.ollama.base_url http://localhost:11434`
- [ ] 8.5.3: `skepsis config set fallback.0 provider=openai model=gpt-4o-mini`
- [ ] 8.5.4: `skepsis providers test <provider-name>` — verify connection works
- [ ] 8.5.5: Multi-profile config switching — `skepsis config use work`, `skepsis config use personal`

### Task 8.6: End-to-End Workflow Testing

- [ ] 8.6.1: Integration test: `skepsis search "CRISPR off-target effects" --limit 5 --output-format json`
- [ ] 8.6.2: Integration test: `skepsis hypothesize "What causes antibiotic resistance in gut microbiomes?" --output-format json`
- [ ] 8.6.3: Integration test: `skepsis provenance <id> --export ro-crate`
- [ ] 8.6.4: Integration test: `skepsis providers test` with mock provider
- [ ] 8.6.5: Integration test: piped workflow `skepsis search "X" --quiet --output-format json | jq '.results[0].id'`

---

**Phase 8 Exit Criteria**: CLI is installable and functional. All subcommands execute end-to-end. Structured output piping works. Configuration management is complete.

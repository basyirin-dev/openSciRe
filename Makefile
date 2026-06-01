VENV       := .venv
PYTHON     := $(VENV)/bin/python
PIP        := $(VENV)/bin/pip
RUFF       := $(VENV)/bin/ruff
MYPY       := $(VENV)/bin/mypy
PYTEST     := $(VENV)/bin/pytest
PRE_COMMIT := $(VENV)/bin/pre-commit
BUILD      := $(VENV)/bin/python -m build

.PHONY: install lint format typecheck test clean build all update-hooks

install:
	$(PIP) install -e ".[dev]"
	$(PIP) install build 2>/dev/null || true

lint:
	$(RUFF) check .

format:
	$(RUFF) format .

typecheck:
	$(MYPY) openscire-core/src/openscire

test:
	$(PYTEST) -v; st=$$?; if [ $$st -eq 5 ]; then exit 0; else exit $$st; fi

clean:
	rm -rf __pycache__ .mypy_cache .pytest_cache .ruff_cache build/ dist/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

build:
	$(BUILD)

update-hooks:
	$(PRE_COMMIT) autoupdate

all: lint format typecheck test build

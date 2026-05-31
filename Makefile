.PHONY: install lint format typecheck test clean build all update-hooks

install:
	pip install -e ".[dev]"

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy skepsis-core/src/skepsis

test:
	pytest -v --cov=skepsis

clean:
	rm -rf __pycache__ .mypy_cache .pytest_cache .ruff_cache build/ dist/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

build:
	pip install build
	python -m build

update-hooks:
	pre-commit autoupdate

all: lint format typecheck build

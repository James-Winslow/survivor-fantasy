# survivor-fantasy Makefile
# All pipeline steps are run through here for reproducibility.
# Run `make help` to see available commands.

.PHONY: help install ingest ingest-s50 build score publish test lint clean reset

help:
	@echo ""
	@echo "survivor-fantasy pipeline commands"
	@echo "──────────────────────────────────────────────────────"
	@echo "  make install      Install package and dependencies"
	@echo "  make ingest       Load survivoR historical data → DuckDB"
	@echo "  make ingest-s50   Load Season 50 manual events → DuckDB"
	@echo "  make build        Materialize feature store from DB"
	@echo "  make score        Compute league scores from events"
	@echo "  make publish      Write JSON outputs → frontend/data/"
	@echo "  make all          Run full pipeline (ingest → publish)"
	@echo ""
	@echo "  make test         Run test suite"
	@echo "  make lint         Run ruff linter"
	@echo "  make clean        Remove generated files (keeps raw data)"
	@echo "  make reset        Drop and rebuild database from scratch"
	@echo ""

install:
	pip install -e ".[dev]"

ingest:
	sf-ingest

ingest-s50:
	sf-ingest-s50

build:
	sf-build

score:
	sf-score

publish:
	sf-publish

# Full pipeline — run after each episode
all: ingest-s50 build score publish
	@echo "Pipeline complete. Push frontend/data/ to deploy."

test:
	pytest

lint:
	ruff check src/ tests/

clean:
	rm -f data/features/*.parquet
	rm -f frontend/data/*.json
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete

reset: clean
	rm -f data/survivor.duckdb
	$(MAKE) ingest
	$(MAKE) build
	@echo "Database rebuilt from scratch."

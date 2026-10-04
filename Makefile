.PHONY: test sample lint typecheck check-release check-examples

test:
	PYTHONPATH=src python -m unittest discover -s tests

sample:
	PYTHONPATH=src python -m maintainer_radar from-json examples/sample-prs.json

lint:
	ruff check src tests scripts

typecheck:
	mypy src

check-release:
	python scripts/check_release.py

check-examples:
	python scripts/generate_examples.py --check

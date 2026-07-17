.PHONY: install test lint type check demo clean

PY := .venv/bin

install:
	python3.11 -m venv .venv
	$(PY)/pip install -q -U pip
	$(PY)/pip install -q -r requirements-dev.txt
	$(PY)/pip install -q -e packages/cairn-engine -e packages/cairn-retrieval

test:
	$(PY)/pytest -q

lint:
	$(PY)/ruff check packages/ examples/

type:
	$(PY)/mypy packages/cairn-engine/src/cairn_engine

check: lint type test  ## the determinism gate: everything must pass (M1.5)

demo:
	$(PY)/python examples/blog_graph_demo.py

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} +

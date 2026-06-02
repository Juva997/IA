.PHONY: lint typecheck test coverage ci

lint:
	python -m ruff check .

typecheck:
	python -m mypy --config-file mypy.ini .

test:
	python -m pytest -q

coverage:
	python -m coverage run -m pytest -q
	python -m coverage report -m --fail-under=65

ci: lint typecheck test coverage

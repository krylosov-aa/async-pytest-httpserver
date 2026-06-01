lint:
	uv run ruff format .
	uv run mypy .
	uv run ruff check --fix .
	uv run flake8 .
	uv run complexipy . --failed
	uv run radon cc .

test:
	uv run pytest

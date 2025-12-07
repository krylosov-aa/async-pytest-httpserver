lint:
	ruff format .
	ruff check --fix .
	mypy .
	flake8 .

test:
	pytest --cov async_pytest_httpserver tests --cov-report=term-missing

test_fastapi:
	pytest examples/fastapi_example/tests

test_starlette:
	pytest examples/starlette_example/tests

uv:
	uv sync
	source .venv/bin/activate

build:
	uv build

publish:
	uv publish

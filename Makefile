lt:
	make l
	make t

l:
	make lint
	make lint_examples

lint:
	ruff format .
	mypy .
	ruff check --fix .
	flake8 .
	complexipy . --failed
	radon cc .

t:
	make test
	make test_examples

test:
	coverage run -m pytest tests
	coverage report --include="async_pytest_httpserver/*" --show-missing

test_examples:
	cd examples/aiohttp_example && unset VIRTUAL_ENV && uv sync --reinstall-package async-pytest-httpserver && uv run pytest

lint_examples:
	cd examples/aiohttp_example && unset VIRTUAL_ENV && uv sync --reinstall-package async-pytest-httpserver --all-groups -q && uv run make lint

uv:
	uv sync
	source .venv/bin/activate

build:
	uv build

publish:
	uv publish

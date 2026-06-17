.PHONY: deps install lint build publish test

deps:  ## Install dependencies
	uv sync

install:  ## Install the package
	uv sync

lint:  ## Lint and static-check
	uv run ruff check .
	uv run ruff format --check .

build:  ## Build dist
	uv build

publish:  ## Publish to PyPi
	uv publish --username "${PYPI_USERNAME}" --password "${PYPI_PASSWORD}"

test:  ## Run tests
	uv run pytest -ra

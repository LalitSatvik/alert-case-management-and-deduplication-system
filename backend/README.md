# ACMS Backend

The backend for the Alert Case Management & Deduplication System.

## Setup

Install dependencies:

```bash
pip install -e ".[dev]"
```

`pyproject.toml` is the abstract spec. `requirements.lock` pins the exact runtime
closure the Docker image builds from — regenerate it (instructions in its header)
whenever `[project.dependencies]` changes.

## Tests

Run tests:

```bash
python -m pytest -v
```

## Linting

Run linting checks:

```bash
ruff check .
black --check .
mypy app
```

## Configuration

Configuration is managed via environment variables and `.env` file. See `.env.example` for all available options.

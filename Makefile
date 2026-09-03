.PHONY: up down test lint migrate seed benchmark
# `test` / `lint` assume the backend dev deps are on PATH — from an active venv
# or `pip install -e "backend/.[dev]"`, the same flow the READMEs document.
up:        ; docker compose up --build -d
down:      ; docker compose down -v
test:      ; cd backend && python -m pytest -q
lint:      ; cd backend && ruff check . && black --check . && mypy app scripts
migrate:   ; docker compose run --rm api alembic upgrade head
seed:      ; docker compose run --rm seed
benchmark: ; docker compose run --rm api python scripts/benchmark.py --dataset scripts/data/benchmark.jsonl

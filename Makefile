PYTHON ?= python
PNPM ?= pnpm

.PHONY: dev up down backend-test frontend-test lint migrate rebuild-index
dev:
	$(MAKE) -j2 backend-dev frontend-dev
backend-dev:
	cd backend && $(PYTHON) -m alembic upgrade head && $(PYTHON) -m uvicorn app.main:app --reload
frontend-dev:
	cd frontend && $(PNPM) dev
up:
	docker compose up --build
down:
	docker compose down
backend-test:
	cd backend && $(PYTHON) -m pytest
frontend-test:
	cd frontend && $(PNPM) lint && $(PNPM) typecheck && $(PNPM) build
lint:
	cd backend && $(PYTHON) -m ruff check .
	cd frontend && $(PNPM) lint
migrate:
	cd backend && $(PYTHON) -m alembic upgrade head
rebuild-index:
	cd backend && $(PYTHON) -m app.cli rebuild-index $(WORKSPACE)

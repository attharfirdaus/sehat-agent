BACKEND := cd backend &&
FRONTEND := cd frontend &&
PNPM := npx -y pnpm@12.21.0

.PHONY: db dev web test lint migrate bot ingest train eval

db:
	docker compose up -d db --wait

dev: db migrate
	$(BACKEND) uv run uvicorn app.main:app --reload --port 8000

web:
	$(FRONTEND) $(PNPM) install --frozen-lockfile && $(PNPM) dev

test: db
	$(BACKEND) uv run pytest

lint:
	$(BACKEND) uv run ruff check . ../eval && uv run ruff format --check . ../eval
	$(FRONTEND) $(PNPM) install --frozen-lockfile --silent && $(PNPM) typecheck && $(PNPM) lint

migrate:
	$(BACKEND) uv run alembic upgrade head

bot:
	@echo "TODO: M6 Telegram bot"

ingest:
	$(BACKEND) uv run python -m app.rag.ingest

train:
	$(BACKEND) uv run python -m ml.train_diabetes

eval:
	$(BACKEND) PYTHONPATH=. uv run python ../eval/run.py

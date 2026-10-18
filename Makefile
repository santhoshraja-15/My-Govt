.PHONY: up down build migrate seed embed graph-rebuild test eval lint clean logs shell-db shell-backend

# ── Docker ───────────────────────────────────────────────────
up:
	docker compose up -d --build

down:
	docker compose down

build:
	docker compose build --no-cache

logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

# ── Database ─────────────────────────────────────────────────
migrate:
	docker compose exec backend alembic upgrade head

migrate-down:
	docker compose exec backend alembic downgrade -1

migrate-status:
	docker compose exec backend alembic current

# Run schema directly (first-time setup)
schema:
	docker compose exec -T postgres psql -U postgres -d mygovt < database/schema/001_schema.sql

seed:
	docker compose exec backend python -m scripts.seed

seed-synthetic:
	docker compose exec backend python -m scripts.synth_data

# ── AI / Data ────────────────────────────────────────────────
embed:
	docker compose exec backend python -m app.ai.embeddings.run --all

graph-rebuild:
	docker compose exec backend python -m knowledge_graph.rebuild

# ── Testing ──────────────────────────────────────────────────
test:
	docker compose exec backend pytest -q --cov=app --cov-report=term-missing

test-unit:
	docker compose exec backend pytest tests/unit -q

test-integration:
	docker compose exec backend pytest tests/integration -q

eval:
	docker compose exec backend python -m ai.eval.run_all

e2e:
	cd frontend && npx playwright test

# ── Code Quality ─────────────────────────────────────────────
lint:
	docker compose exec backend ruff check . && \
	docker compose exec backend black --check . && \
	docker compose exec backend mypy app && \
	cd frontend && npm run lint && npx tsc --noEmit

format:
	docker compose exec backend ruff check --fix . && \
	docker compose exec backend black .

# ── Shell Access ─────────────────────────────────────────────
shell-db:
	docker compose exec postgres psql -U postgres -d mygovt

shell-backend:
	docker compose exec backend bash

shell-neo4j:
	docker compose exec neo4j cypher-shell -u neo4j -p ${NEO4J_PASSWORD}

# ── Health ───────────────────────────────────────────────────
health:
	curl -s http://localhost:8000/health | python -m json.tool

# ── Cleanup ──────────────────────────────────────────────────
clean:
	docker compose down -v --remove-orphans
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

# ── Scheduler (run once) ─────────────────────────────────────
scheduler:
	docker compose exec worker python -m app.jobs.sla_once

# ── Initial Setup (run once after clone) ─────────────────────
setup: up
	@echo "Waiting for services to be healthy..."
	@sleep 15
	$(MAKE) migrate
	$(MAKE) seed
	@echo "Setup complete. Visit http://localhost:3000"

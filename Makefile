.PHONY: up down build migrate schema migrate-sql db-init db-verify seed seed-verify embed graph-rebuild test eval lint clean logs shell-db shell-backend

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

# Step 1: baseline schema (no provenance columns — do NOT seed yet). Fails fast on any SQL error.
schema:
	docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d mygovt < database/schema/001_schema.sql

# Step 2: raw SQL migration (002 adds headquarters, lgd_code, verification_status etc.)
migrate-sql:
	docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d mygovt < database/migrations/002_provenance_and_audit_fixes.sql

# Full first-time database initialisation in correct dependency order:
#   1. Base schema (001_schema.sql)      → tables, functions, triggers
#   2. Migration 002                     → provenance columns seeds depend on
#   3. Seed data (backend/scripts/seed.py, applies database/seeds/002_verified_seed_data.sql only,
#      then runs integrity + provenance checks; idempotent)
# db-init is for a CLEAN database only (001_schema.sql is not re-runnable). To re-seed an existing
# database use 'make seed' (idempotent).
# NOTE: 'migrate' (alembic) has no revisions yet; use migrate-sql until Milestone 7.
db-init: schema migrate-sql seed

seed:
	docker compose exec backend python -m scripts.seed

# Re-run the post-seed integrity/provenance checks without changing data
seed-verify:
	docker compose exec backend python -m scripts.seed --verify-only

# Build a throw-away mygovt_test_* database, run schema -> migration -> seed (twice) -> constraint probes, drop it.
# Never touches the 'mygovt' database. Requires the postgres service (PostGIS image) to be up.
db-verify:
	docker compose exec backend sh -c 'python -m scripts.db_verify --admin-dsn postgresql://$$POSTGRES_USER:$$POSTGRES_PASSWORD@postgres:5432/postgres'

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
	$(MAKE) db-init
	@echo "Setup complete. Visit http://localhost:3000"

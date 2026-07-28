# AI Site Agent — release & deployment commands
# Primary deployment: Linux systemd + nginx + host services (see docs/DEPLOYMENT.md).
# Docker: optional validation only — never required for make release-check or staging smoke.

SHELL := /bin/bash

.PHONY: help dev deploy smoke deploy-smoke test test-backend test-dashboard test-migration \
        migrate release-check release-0.3 ci test-backend-benchmarks test-memory-eval \
        deploy-staging smoke-staging rollback-staging init-staging

help:
	@echo "Daily commands:"
	@echo "  make dev             — local backend + dashboard (repo .env)"
	@echo "  make deploy          — deploy checkout → /opt/ai-site-agent"
	@echo "  make smoke           — HTTP smoke (health, build, metrics, settings)"
	@echo "  make deploy-smoke    — deploy then smoke"
	@echo ""
	@echo "Release gate:"
	@echo "  make release-check   — full pre-release validation (see scripts/release/release-check.sh)"
	@echo ""
	@echo "Tests:"
	@echo "  make test            — backend unit + dashboard"
	@echo "  make test-backend    — RFC unit suite (~272 tests)"
	@echo "  make test-backend-benchmarks — optional wall-clock benchmarks (not in release-check)"
	@echo "  make test-dashboard  — vitest + tsc + build"
	@echo "  make test-memory-eval — Step 049 offline Memory Assist eval (fixtures only)"
	@echo "  make test-migration  — alembic up/down/up (POSTGRES_TEST_URL)"
	@echo "  make migrate         — alembic upgrade head (local DATABASE_URL)"

dev:
	@bash scripts/start-dev.sh

deploy:
	@bash scripts/deploy.sh

smoke:
	@bash scripts/smoke.sh

deploy-smoke:
	@bash scripts/deploy-and-smoke.sh

deploy-staging: deploy
smoke-staging: smoke

test: test-backend test-dashboard

test-backend:
	@bash scripts/release/test-backend.sh

test-backend-benchmarks:
	@bash scripts/release/test-backend-benchmarks.sh

test-memory-eval:
	@bash scripts/release/test-memory-eval.sh

test-dashboard:
	@bash scripts/release/test-dashboard.sh

test-migration:
	@bash scripts/release/test-migration.sh

migrate:
	@cd backend && .venv/bin/alembic upgrade head

release-check:
	@bash scripts/release/release-check.sh

release-0.3:
	@echo "Release 0.3:"
	@echo "  make release-check          # engineering gate"
	@echo "  make deploy-smoke           # ops gate (production only)"
	@echo "  See docs/LIFECYCLE.md"

rollback-staging:
	@bash scripts/release/rollback-staging.sh

init-staging:
	@echo "NOTE: use make deploy for /opt/ai-site-agent (see STAGING-SEED-SMOKE.md)"

ci: release-check

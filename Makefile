# Airport Investment Intelligence Agent — common tasks. See README / docs/HANDOFF.md.
.PHONY: dev test test-live e2e snapshot build up down spend

UV_BACKEND = uv run --project backend

## dev: FastAPI on :8000 (reload) + Next.js dev on :3000 (proxies /api to :8000)
dev:
	@trap 'kill 0' EXIT; \
	(cd backend && uv run uvicorn app.main:app --reload --port 8000) & \
	(cd frontend && npm run dev) & \
	wait

## test: offline tests (no API spend)
test:
	cd backend && uv run pytest -q
	$(UV_BACKEND) pytest -q ingest/tests
	$(UV_BACKEND) pytest -q tests/e2e
	cd frontend && npm test --if-present

## test-live: live e2e tests against real Claude (spends money; needs ANTHROPIC_API_KEY)
test-live:
	cd backend && set -a && . ../.env && set +a && uv run pytest -q -m live -s
	set -a && . ./.env && set +a && $(UV_BACKEND) pytest -q -m live -s tests/e2e

## e2e: Playwright smoke (access code → G3 → Evidence → reload) against docker compose (spends one answer)
e2e:
	docker compose up -d --build --wait
	set -a && . ./.env && set +a && $(UV_BACKEND) pytest -q -m e2e -s tests/e2e

## snapshot: rebuild data/snapshot/*.parquet + manifest.json from data/raw/ (fails loudly on gaps)
snapshot:
	$(UV_BACKEND) python ingest/build_snapshot.py

## build: production image (frontend static export + backend + Snapshot)
build:
	docker compose build

## up: app + postgres at http://localhost:8000
up:
	docker compose up --build

down:
	docker compose down

## spend: live API spend so far against the hard cap (backend/tests/spend_cap.py)
spend:
	cd backend && uv run python -m tests.spend_cap

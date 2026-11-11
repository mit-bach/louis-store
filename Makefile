# The store's everyday commands. Run them in the repository's top folder.
# Examples: make up · make check M=1 · make check M=1 STEP=3

PSQL = docker compose exec -T db psql -X -q -v ON_ERROR_STOP=1 -U store -d store

.PHONY: help up down logs psql migrate reset check check-all spec update

help:
	@echo "make up                  start your store (API and database), rebuilding the API if needed"
	@echo "make down                stop it; your data stays"
	@echo "make logs                follow the API's log (Ctrl-C to stop following)"
	@echo "make psql                open a SQL prompt in your database (\\q to leave)"
	@echo "make migrate             apply the migrations your database hasn't had yet"
	@echo "make reset               empty your database, then apply every migration and the seed"
	@echo "make check M=1 [STEP=3]  run the checks for a milestone, on a throwaway copy of your store"
	@echo "make check-all           run every milestone's checks"
	@echo "make spec S=14           run an optional spec's checks (optional/README.md)"
	@echo "make update              take the kit's new guides and fixes (git pull from the remote called kit)"

up:
	docker compose up -d --build --wait

down:
	docker compose down

logs:
	docker compose logs --tail 50 -f api

psql:
	docker compose exec db psql -U store -d store

migrate:
	@$(PSQL) -c "SET client_min_messages = warning; CREATE TABLE IF NOT EXISTS schema_migrations (filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now());"
	@for f in backend/migrations/*.sql; do \
		[ -e "$$f" ] || continue; \
		name=$$(basename "$$f"); \
		if [ -n "$$($(PSQL) -At -c "SELECT 1 FROM schema_migrations WHERE filename = '$$name'")" ]; then continue; fi; \
		echo "applying $$f"; \
		{ cat "$$f"; echo; echo "INSERT INTO schema_migrations (filename) VALUES ('$$name');"; } | $(PSQL) -1 || exit 1; \
	done
	@echo "migrations up to date"

reset:
	@$(PSQL) -c "SET client_min_messages = warning; DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	@$(MAKE) --no-print-directory migrate
	@if [ -f backend/seed.sql ]; then echo "applying backend/seed.sql"; $(PSQL) -1 < backend/seed.sql; fi
	@echo "done"

check:
	@command -v uv >/dev/null || { echo "uv isn't installed: see milestones/M0/1-tools-and-your-repo.md"; exit 1; }
	@if [ -z "$(M)" ]; then echo "Say which milestone: make check M=0"; exit 2; fi
	@uv run --quiet checks/check.py $(M) $(STEP)

check-all:
	@command -v uv >/dev/null || { echo "uv isn't installed: see milestones/M0/1-tools-and-your-repo.md"; exit 1; }
	@uv run --quiet checks/check.py all

spec:
	@command -v uv >/dev/null || { echo "uv isn't installed: see milestones/M0/1-tools-and-your-repo.md"; exit 1; }
	@if [ -z "$(S)" ]; then echo "Say which optional spec: make spec S=14"; exit 2; fi
	@uv run --quiet checks/check.py s$(S)

update:
	git pull --no-rebase --no-edit kit main

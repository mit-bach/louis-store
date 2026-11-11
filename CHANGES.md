# Changes

Each version of the kit, newest first. `make update` brings you the newest.

## 0.7.0 · 2026-11-11

Optional spec 14, with a guide and checks.
- **Optional specs have a home:** `optional/`, and `make spec S=<number>` checks one. They're never part of `make check-all`, and no milestone's guide or checks changed.
- **Spec 14 · Your own migration runner:** `backend/migrate.py`, with a checksum for each applied file and one lock for each run. The guide, the contract's section, and five checks.

## 0.6.0 · 2026-11-11

M6, the frontend: the last milestone.
- **M6 · The frontend, built by your agent:**
  - your orders, through all three ways in;
  - CORS for your own frontend, and nobody else's;
  - your spec, after deciding where the token lives;
  - the build, from a plan you read and approve first, on a branch;
  - the walkthrough by hand;
  - the same request with no spec, as the control.
- **The contract's M6 section.**
- **The M5 permissions check** asks for each customer tool your store has, so it includes `list_orders` from M6. Its title is the same.

## 0.5.0 · 2026-11-08

M5, agent-first for real.
- **M5 · Agent-first, for real: retries, errors, scope and evals:**
  - an `Idempotency-Key` on checkout, through all three ways in, and tested at the same instant;
  - one message for anything unexpected, through every way in, with the traceback kept for you in `make logs`;
  - `in_stock` on each cart line;
  - the customer's agent, in a folder of its own, with only the customer tools, and tested against a full agent;
  - five shopping evals, run headless, with your tool descriptions vague, wrong and rewritten.
- **`checks/retry_test.py` and `checks/evals.py`:** the retry test, and the evals.
- **The contract's M5 section,** and a line on unexpected errors in its rules for errors.
- **The M3 checks** accept the field M5 adds to a cart line, `in_stock`. Their titles and results are the same.

## 0.4.1 · 2026-11-08

- **M4-6** points to your tutor harness's rule for compacting a session: §5a of `~/tutor/orchestrator/ORCHESTRATOR.md`, new in its 1.0.3. Nothing else changed.

## 0.4.0 · 2026-11-08

M4, checkout and two buyers at once.
- **M4 · Checkout, and two buyers at once:**
  - orders that outlive their sessions, and keep the price paid;
  - checkout as one transaction that locks its products in id order, and changes nothing when it refuses;
  - checkout through all three ways in;
  - the race for the last unit and the deadlock test, each with its control;
  - two agents buying the last unit at once;
  - your first audit of your tutor harness, and your first compaction through Berth.
- **`checks/race_test.py` and `checks/deadlock_test.py`:** the checkout race and the deadlock test.
- **The contract's M4 section.**

## 0.3.0 · 2026-11-08

M3, visitors and carts.
- **M3 · Visitors and carts:** sessions with a token that expires, the cart with a join and an upsert, the three refusals for a missing, made-up or expired token through every way in, two customers shopped for by one agent, and your reviewer as a skill in your tutor harness.
- **A new exit code, 5,** for no valid session, and the contract's M3 section: how HTTP, the command line and the tools each carry a session.
- **`reviewer/REVIEWER.md`** now only reads files and git, so a tutor can use it without running anything in your store.

## 0.2.0 · 2026-11-08

M2, and what it needed from the kit.
- **M2 · The admin side, and your first race:** a second migration (archive, not delete), archiving, editing and stock changes through all three ways in, the stock race and its control, your agent as an admin, and the wall on both of your harnesses: a hook in this repository, and a deny rule in your tutor's course.
- **`make migrate`** applies only the migrations your database hasn't had, and records each one in a table called `schema_migrations`. `make reset` now ends with it.
- **`checks/stock_race.py`:** the stock race, through HTTP, `./store` or your tools.
- **The contract's M2 section.**
- **The M1 checks** now accept the field M2 adds to a product, `archived_at`. Their titles and results are the same.
- **The M0 and M1 guides** show `make reset`'s new output, which now includes `migrations up to date`, from a fresh run. Nothing else in them changed.

## 0.1.0 · 2026-11-08

The first milestones.
- **M0 · Setup, and an agent that follows your rules:** your tools, your own repository, the store's stack in Docker with a health check, and your rules file with its first control experiment.
- **M1 · Products, and the store's first tools:** the products table, the seed, the operations, and the three ways in: HTTP routes, the `./store` command line, and MCP tools, with the parity check.
- **The contract** for M0 and M1, the checks (`make check`), the reviewer prompt, and the course's text for your tutor harness.

Every guide was run from a fresh clone before release, and every expected output in it was pasted from that run. Each check was also run against a deliberately broken store, to make sure it catches what it's for.

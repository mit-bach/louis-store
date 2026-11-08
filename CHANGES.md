# Changes

Each version of the kit, newest first. `make update` brings you the newest.

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

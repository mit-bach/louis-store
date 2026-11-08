# M2 · The admin side, and your first race

**About two days.**

**Before you start:** these guides arrive with `make update`, which also brings the kit's new `make migrate` and its race script, `checks/stock_race.py`. If you're reading this, you have them.

## What works at the end

An admin, a script or an agent can run the catalogue. They can take a product off sale, change its details, and add or remove stock, through every way in:
- `POST /products/3/archive`, `./store products archive 3`, or the tool `archive_product`;
- `PATCH /products/3`, `./store products update 3 --price-cents 2900`, or the tool `update_product`;
- `POST /products/3/stock`, `./store products adjust-stock 3 --change -2`, or the tool `adjust_stock`.

A hundred stock changes sent at the same instant leave the stock exactly right, through all three. And the line from M0, that you write your backend yourself, is no longer only a rule: a hook in this repository and a setting in your tutor make Claude Code refuse to edit your backend files.

## Who writes what

- **Yours, by hand:**
  - `backend/migrations/002_add_archived_at.sql`, your second migration;
  - the new fields and models in `backend/schemas.py`;
  - `archive_product`, `update_product` and `adjust_stock` in `backend/products.py`;
  - their routes, commands and tools.
- **Given, and you type it in:**
  - the hook, `.claude/settings.json` and `.claude/hooks/protect-backend.py`;
  - the one rule your tutor's course settings gain, which you add through Tutor Orch.
- **Given, and already in the kit:** `make migrate`, and the race script `checks/stock_race.py`.

## The steps

1. [Archive, not delete: your second migration](1-archive-not-delete.md)
2. [Archiving a product](2-archiving-a-product.md)
3. [Editing a product](3-editing-a-product.md)
4. [Adjusting stock](4-adjusting-stock.md)
5. [The stock race, and your agent as an admin](5-the-stock-race.md)
6. [The wall in your store: a hook](6-the-wall-a-hook.md)
7. [The wall in your tutor: a deny rule](7-the-wall-a-deny-rule.md)

## M2 is done when

1. `make check M=2` passes. The end of step 7 shows exactly what that looks like.
2. **The manual check:** `uv run checks/stock_race.py` passes against your own store, and the read-then-write version you write in step 5 fails it.
3. **The review:** an agent has followed `reviewer/REVIEWER.md` for M2. In `JOURNAL.md`, under `## M2 review`, each thing it found is listed, with what you did: fixed, or why not.
4. **`JOURNAL.md`** has each step's decisions, and your answers to your tutor's questions.
5. **`PREDICTIONS.md`** has each step's predictions, with what happened.
6. **It's committed and pushed.**

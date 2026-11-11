# Optional spec 14 · Your own migration runner

**Why:** since M2, `make migrate` has applied your migrations: a short loop in the `Makefile` that runs each file it hasn't seen, and records its name in `schema_migrations`. That's the idea every migration tool starts from. Real ones (Alembic, Flyway, Rails' migrations) add two protections that the loop doesn't have:
- **An applied file that was edited.** Your database never sees the edit, because the name was already recorded. But a fresh database, like the one `make check` builds, gets the edited version. Now two databases that should match don't, and nothing tells you.
- **Two runs at once.** Two terminals, or two deploys, both see a file as new, and both try to apply it.

You write a runner that has both: a checksum for each applied file, and a lock. It's yours to write, in Python, as `backend/migrate.py`.

## Decide first: where does your runner record what's applied?

Two options:
- **(a)** A new table of its own, which starts empty.
- **(b)** `schema_migrations`, the table `make migrate` already keeps, with a `checksum` column added.

The facts:
- Your database's `schema_migrations` already lists every file you've applied since M2.
- A runner that thinks nothing is applied runs `001_create_products.sql` again, and Postgres refuses: `relation "products" already exists`.
- `make migrate` stays in the `Makefile`. Someone, maybe you in a hurry, will run it again.

**Write (a) or (b), and why, under `## Spec 14` in `JOURNAL.md`, before you open the answer.**

<details><summary>Check your choice</summary>

(b). One record of what's applied, which both tools read. Its rows from `make migrate` have no checksum yet. The runner trusts what's already there: it records each one's checksum once, without running the file again. From then on it checks them. A row `make migrate` adds later gets its checksum the same way, on the runner's next run.
</details>

## Decide first: two runs at once

Two options:
- **(a)** Rely on the primary key: the second run's `INSERT INTO schema_migrations` for the same file fails.
- **(b)** One lock for the whole run: the second run waits at the start until the first has finished, then reads what's applied.

The facts:
- A migration's own statements run before its `INSERT`. The second run's `CREATE TABLE products` fails first, with an error your runner didn't plan for.
- Postgres has **advisory locks**: a lock on a number you choose, not on a row. `SELECT pg_advisory_lock(42)` waits until no other session holds lock 42, and `pg_advisory_unlock(42)` lets it go. Only code that asks for the same number waits. Postgres attaches no meaning to it.

**Write (a) or (b), and why, under `## Spec 14`, before you open the answer.**

<details><summary>Check your choice</summary>

(b). It's M4's lesson in a new place: look, then act, with nothing able to change in between. The lock makes "read what's applied, then apply the rest" one step that nobody else can interleave with. The primary key is still worth having, as the last line of defence, like the `CHECK` on stock.
</details>

## The idea

The order of the work, as [`CONTRACT.md`](../CONTRACT.md), "Optional spec 14", gives it:
1. connect, and take the advisory lock;
2. make sure `schema_migrations` exists and has its `checksum` column (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE … ADD COLUMN IF NOT EXISTS`);
3. read what's applied;
4. **check every applied file's checksum before applying anything.** One edited file stops the whole run;
5. record the checksum of each row that hasn't one;
6. apply each new file, in name order, in a transaction of its own together with its row;
7. let the lock go, even when something failed (`try … finally`).

Four pieces of Python and psycopg you'll need, each on a different problem:

```python
import hashlib
from pathlib import Path

digest = hashlib.sha256(Path("notes.txt").read_bytes()).hexdigest()   # the file's checksum, in hex
files = sorted(Path("notes").glob("*.txt"))                           # every .txt in a folder, by name
```

```python
import os
import psycopg

with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
    conn.execute("SELECT pg_advisory_lock(%s)", (7,))   # waits here while another session holds lock 7
    try:
        with conn.transaction():                        # these two statements commit together, or not at all
            conn.execute("UPDATE counters SET n = n + 1 WHERE name = 'visits'")
            conn.execute("INSERT INTO log (what) VALUES ('visit')")
    finally:
        conn.execute("SELECT pg_advisory_unlock(%s)", (7,))
```

`autocommit=True` means each statement commits by itself, unless it's inside `conn.transaction()`. The lock belongs to the connection: it's released when you unlock, or when the connection closes. `conn.execute()` with no parameters runs a whole file of SQL statements at once.

Your runner doesn't use the store's pool from `db.py`: a script that runs once and exits needs one connection, not a pool.

## You write

**`backend/migrate.py`,** as the contract says: the lock, the checksums, the messages, exit 4 for an edited file, and a folder argument that defaults to `migrations`. The checks run it on a copy of your migrations, in a folder of their own.

## Try it on your own database

Your database was set up by `make migrate`, so the first run only records checksums:

```
docker compose exec api python migrate.py
```

```
checksum recorded for 001_create_products.sql
checksum recorded for 002_add_archived_at.sql
checksum recorded for 003_create_sessions.sql
checksum recorded for 004_create_cart_items.sql
checksum recorded for 005_create_orders.sql
checksum recorded for 006_create_order_lines.sql
checksum recorded for 007_add_idempotency_key.sql
migrations up to date
```

A new migration: an index, so that listing a category doesn't read every product.

```
echo 'CREATE INDEX products_category_idx ON products (category);' > backend/migrations/008_index_products_by_category.sql
docker compose exec api python migrate.py
```

```
applying 008_index_products_by_category.sql
migrations up to date
```

Now edit an applied file, and run it again. Copy the whole block:

```
echo '-- an edit' >> backend/migrations/001_create_products.sql
docker compose exec api python migrate.py; echo "exit code $?"
```

**You should see** exit 4, and the file named:

```
001_create_products.sql was edited after it was applied. Put it back as it was, and write a new migration for the change.
exit code 4
```

Put it back:

```
git checkout -- backend/migrations/001_create_products.sql
```

## The control: no lock

Comment out your `pg_advisory_lock` and `pg_advisory_unlock` lines. **Predict,** under `## Spec 14` in `PREDICTIONS.md`: two runs start at the same moment on an empty database. What happens to each?

```
make spec S=14
```

<details><summary>What happened when this was tested (open it after your run)</summary>

Tested three times on 2026-11-11, with the course's own runner and its two lock lines removed. The check failed every time, in the same way:
- **Both runs** read `schema_migrations` before either had written to it, so both saw every file as new.
- **One run** applied all seven files.
- **The other** reached `001_create_products.sql` while the first was applying it, crashed with a database error, and exited 1. A deploy that ran this way would stop half-way, with a traceback.

With the lock, the second run waited at the start, then found all seven applied, and printed only `migrations up to date`.
</details>

Put the lock back.

## Check

```
make spec S=14
```

**You should see:**

```
  PASS  S14-1  backend/migrate.py applies every migration to an empty database, in filename order, each recorded with its SHA-256
  PASS  S14-2  run again, it applies nothing; a new file is applied once, and only that file
  PASS  S14-3  an applied file that was edited stops the run: exit 4, a message naming it, and nothing new applied
  PASS  S14-4  a database make migrate set up: the runner records each file's checksum, and runs nothing again
  PASS  S14-5  two runs at the same moment: both succeed, and each file is applied exactly once

5 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

## Done

```
git add -A
git commit -m "Spec 14: my own migration runner"
git push
```

From now on, `docker compose exec api python migrate.py` is how you apply migrations. `make migrate` still works, and your runner picks up whatever it records.

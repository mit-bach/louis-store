# Step M2-1 · Archive, not delete: your second migration

**Why:** an admin will want to take products off sale. Before you write that, you decide what "taking a product off sale" means for the data, and that needs a change to a table that already holds data. That's what migrations are really for.

## Decide first: delete the row, or archive it?

There are two ways to take a product off sale:
- **(a) Delete it:** `DELETE FROM products WHERE id = …`. The row is gone.
- **(b) Archive it:** add a column `archived_at`, set it to the moment the product came off sale, and leave the row where it is. Lists leave archived products out.

The facts:
- From M4 on, every order will have lines that point at products by their `id`, with a **foreign key**: a rule in the database that a line's `product_id` must be the `id` of a row in `products`.
- With a foreign key, Postgres refuses to delete a row that something points at. The alternative, `ON DELETE CASCADE`, deletes the order lines along with it.
- A customer's order from last month must still say what they bought, even if you no longer sell it.
- An admin sometimes takes a product off sale by mistake.

**Write (a) or (b), and why, in `JOURNAL.md` under `## M2-1`, before you open the answer.**

<details><summary>Check your choice</summary>

(b), archive. A deleted product would either be refused (the foreign key) or take its order lines with it (the cascade), and an order that forgets what was bought is worse than useless. An archived row keeps every order whole, and an archive is easy to see, and to undo, with one `UPDATE`. Most real stores do this, and call it a **soft delete**.
</details>

## The idea: changing a table that has data

In M1 you used `make reset`: empty the database, then build it again from your migrations and your seed. That was fine while the only data was your seed. A real store can't do that: its data is its customers and their orders.

So the rule from now on is **add a migration, never edit one.** Once a migration has run on a database, that database will never run it again. If you edited `001_create_products.sql`, a fresh database (like the checks' throwaway one) would get your change, but your own database never would, and nothing would warn you that the two now disagree. A new file, `002_…`, is applied to every database once, in order, after `001`.

**How a database knows what it has had.** The kit's `make migrate` keeps a table called `schema_migrations`, with one row per migration file it has applied. It applies only the files that aren't listed yet, each one in a single transaction together with its row, so a migration is either applied and recorded, or neither. `make reset` now ends with `make migrate`, so it records what it applies too.

## 1. Start recording

Your database was built before `schema_migrations` existed, so it has no record of `001`. Build it once more, so `make migrate` knows what it has:

```
make reset
```

```
applying backend/migrations/001_create_products.sql
migrations up to date
applying backend/seed.sql
done
```

Now give it data you'd hate to lose. Add a product that isn't in your seed. Mine:

```
./store products create --sku TENT-3P --name 'Three-Person Tent' --category shelter --price-cents 32900 --stock 2
```

Note its `id`. Mine is 11.

## 2. You write: `backend/migrations/002_add_archived_at.sql`

**The idea.** `ALTER TABLE name ADD COLUMN …;` adds a column to a table that already has rows. The new column is written exactly like a column in `CREATE TABLE`: its name, its type, then its rules. Every existing row gets the column's default, or `NULL` if it has none.

**An example on a different table,** the library's second migration:

```sql
ALTER TABLE books ADD COLUMN withdrawn_at TIMESTAMPTZ;
```

**You write** `backend/migrations/002_add_archived_at.sql`: one statement that adds `archived_at` to `products`, as [`CONTRACT.md`](../../CONTRACT.md) describes it in "M2 · What changes for a product".

**Hint:** "empty for a product on sale" means no `NOT NULL` and no default.

## 3. Apply it, and nothing else

**Predict,** under `## M2-1` in `PREDICTIONS.md`: what will `make migrate` apply, and what will happen to the product you just added?

```
make migrate
```

```
applying backend/migrations/002_add_archived_at.sql
migrations up to date
```

Only `002` ran. Run it again:

```
make migrate
```

```
migrations up to date
```

Nothing to do. Your database's record:

```
docker compose exec db psql -U store -d store -c 'SELECT filename FROM schema_migrations ORDER BY filename;'
```

```
        filename
-------------------------
 001_create_products.sql
 002_add_archived_at.sql
(2 rows)
```

And the product you added survived:

```
./store products get 11 | grep -E '"(sku|name|stock)"'
```

```
  "sku": "TENT-3P",
  "name": "Three-Person Tent",
  "stock": 2,
```

## 4. You write: archived products leave the lists

Your table has the column. Now everything above it needs to know about it.

**An example on a different table,** the library's list, its route and its command:

```python
def list_books(include_withdrawn: bool = False) -> list[Book]:
    with pool.connection() as conn:
        if include_withdrawn:
            rows = conn.execute("SELECT * FROM books ORDER BY title").fetchall()
        else:
            rows = conn.execute("SELECT * FROM books WHERE withdrawn_at IS NULL ORDER BY title").fetchall()
    return [Book(**row) for row in rows]
```

```python
@app.get("/books", response_model=list[Book])
def get_books(include_withdrawn: bool = False):
    return books.list_books(include_withdrawn)
```

```python
@books_app.command("list")
def list_command(
    include_withdrawn: Annotated[bool, typer.Option(help="Also list withdrawn books.")] = False,
):
    """List the books on the shelves, by title."""
    print_json(books.list_books(include_withdrawn))
```

A route parameter typed `bool` with a default is read from the address: `/books?include_withdrawn=true`. A Typer option typed `bool` becomes a flag: `--include-withdrawn` turns it on.

**You write:**
- **`backend/schemas.py`:** `Product` gains `archived_at`, a `datetime` or `None`, defaulting to `None`. `ProductCreate` doesn't: nobody creates a product that's already archived.
- **`backend/products.py`:** `list_products(include_archived: bool = False)` leaves out products whose `archived_at` is set, unless `include_archived` is true. Still sorted by `id`.
- **`backend/main.py`:** `GET /products` takes `include_archived`, as above.
- **`backend/cli.py`:** `products list` takes `--include-archived`.
- **`backend/tools.py`:** the `list_products` tool takes `include_archived: bool = False`, and its docstring says that archived products are left out unless it's true. Your agent reads that docstring to know the option exists.

**Hint:** `IS NULL` is how SQL asks whether a value is missing. `= NULL` never matches anything.

## Check

Archive a product by hand, straight in the database, to see the lists change. Mine was product 10:

```
docker compose exec db psql -U store -d store -c "UPDATE products SET archived_at = now() WHERE sku = 'BOTTLE-1L';"
```

Then count what each list shows:

```
./store products list | grep -c '"id"'
./store products list --include-archived | grep -c '"id"'
```

**You should see** one more product with the option than without it. Mine:

```
10
11
```

(`grep -c '"id"'` counts the lines containing `"id"`, which is one per product.) Then:

```
make check M=2 STEP=1
```

**You should see** everything before, then:

```
M2 · The admin side, and your first race
  PASS  M2-1  the products table has archived_at, a moment with its time zone, empty by default
  PASS  M2-1  list_products() leaves archived products out, and list_products(include_archived=True) lists them
  PASS  M2-1  GET /products leaves archived products out; ?include_archived=true lists them, with archived_at
  PASS  M2-1  ./store products list --include-archived, and the tool's include_archived, agree with HTTP

54 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

## Step done

```
git status --short
```

```
 M JOURNAL.md
 M PREDICTIONS.md
 M backend/cli.py
 M backend/main.py
 M backend/products.py
 M backend/schemas.py
 M backend/tools.py
?? backend/migrations/002_add_archived_at.sql
```

Then commit and push:

```
git add -A
git commit -m "M2-1: archived_at, and lists without archived products"
git push
```

Answer your tutor's questions under `## M2-1` in `JOURNAL.md`.

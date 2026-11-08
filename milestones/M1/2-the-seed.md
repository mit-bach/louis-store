# Step M1-2 · The seed

**Why:** an empty catalogue tests nothing. A **seed** is a file of starting data that `make reset` loads after the migrations, so your store always starts from the same, known products: for you, for the checks, and for your agent later on.

## The idea: `INSERT`

`INSERT INTO table (columns) VALUES (row), (row), …;` adds rows.
- **The list of columns** names the ones you give values for. Leave out the ones the database fills in itself, like `id` and the times.
- **Each row in parentheses** gives values in the same order as that list.
- **Punctuation:** rows are separated by commas, and the last row ends with a semicolon. Text goes in single quotes. If the text itself has an apostrophe, write it twice: `'Hiker''s lamp'`. `NULL`, without quotes, means "no value".

**An example on a different table,** the library's books:

```sql
INSERT INTO books (isbn, title, subtitle, copies) VALUES
    ('978-0-14-143951-8', 'Emma',      NULL,                      2),
    ('978-0-19-953556-9', 'Walden',    'Or, Life in the Woods',   1),
    ('978-0-14-118776-1', 'Dubliners', NULL,                      0);
```

The first and third books have no subtitle, so they get `NULL`. The third has 0 copies: every copy is out.

## You write: `backend/seed.sql`

One `INSERT INTO products …;` with at least **8 products**, from a catalogue you choose: a shop you'd like to run, or one you know. It must hold:
- at least 3 categories, so your agent has something to filter by later;
- at least one product with no description (`NULL`);
- at least one product with stock 0, because you'll need one that's sold out from M3 on;
- a SKU for each, that no other product uses.

Leave out `id`, `created_at` and `updated_at`, and any column you're happy to leave at its default.

**Hint:** prices are in cents. A $24.50 product is `2450`.

## Run it

```
make reset
```

**You should see** your migration, then your seed, applied:

```
applying backend/migrations/001_create_products.sql
migrations up to date
applying backend/seed.sql
done
```

Then look at your catalogue:

```
docker compose exec db psql -U store -d store -c 'SELECT id, sku, name, price_cents, stock FROM products ORDER BY id;'
```

Mine, an outdoor-gear shop, shows this. Yours shows your products:

```
 id |    sku    |         name         | price_cents | stock
----+-----------+----------------------+-------------+-------
  1 | TENT-2P   | Two-Person Tent      |       24900 |     5
  2 | TENT-1P   | Solo Tent            |       18900 |     3
  3 | TARP-3X3  | Tarp 3 x 3 m         |        5900 |    12
  4 | BAG-0C    | Sleeping Bag 0 C     |        8900 |     8
  5 | PAD-AIR   | Air Pad              |        7400 |    10
  6 | STOVE-CAN | Canister Stove       |        3900 |    20
  7 | POT-750   | Titanium Pot 750 ml  |        4400 |    15
  8 | LAMP-HEAD | Head Torch           |        3500 |    25
  9 | FILTER-SQ | Squeeze Water Filter |        3200 |     0
 10 | BOTTLE-1L | Bottle 1 L           |        1500 |    40
(10 rows)
```

**If `make reset` stops with an error,** it names the line. The usual causes:
- a missing comma between two rows;
- a text value with an apostrophe that isn't doubled;
- two products with the same SKU, which your `UNIQUE` rule refuses.

The whole file is applied as one transaction, so when one row fails, none of them are saved. Fix it, and run `make reset` again.

## Check

```
make check M=1 STEP=2
```

**You should see** everything before, then:

```
  PASS  M1-2  your seed applies
  PASS  M1-2  the seed holds at least 8 products

19 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

## Step done

Look at what git sees:

```
git status --short
```

**You should see** this. `M` means changed, and `??` new. Your journal and predictions are listed because you wrote in them:

```
 M JOURNAL.md
 M PREDICTIONS.md
?? backend/seed.sql
```

Then commit and push:

```
git add -A
git commit -m "M1-2: the seed"
git push
```

Under `## M1-2` in `JOURNAL.md`, write one line on the catalogue you chose, and answer your tutor's questions.

# Step M1-1 · The products table

**Why:** products need a table to live in. A table is a **design**: its rules decide what the store can hold, what it refuses, and what every piece of code above it has to cope with. So this step works differently from M0:
1. you learn the building blocks;
2. you make six decisions, each with the facts you need, and write them in your journal;
3. you compare them with the contract;
4. you write the table yourself, as your first migration, and check it;
5. then you open my reasoning, and compare.

## 1. The building blocks

A table is created with `CREATE TABLE name ( … );`. Inside the parentheses, each column is written as **its name, its type, then its rules**. Columns are separated by commas, with none after the last one.

**Types:**
- `TEXT` is text of any length. `VARCHAR(n)` is the same, with a maximum length of `n`.
- `INTEGER` is a whole number up to about 2 billion. `BIGINT` goes up to about 9 quintillion.
- `NUMERIC(10,2)` is an exact decimal, with up to 10 digits, 2 of them after the point.
- `REAL` is a floating-point number: fast, but approximate.
- `TIMESTAMP` is a date and time. `TIMESTAMPTZ` is a date and time stored as an exact moment, with its time zone.

**Rules you can attach to a column:**
- `NOT NULL`: the column must have a value. Without it, the value may be missing, which SQL writes as `NULL`.
- `DEFAULT something`: the value used when an insert doesn't give one, like `DEFAULT 0` or `DEFAULT now()`. `now()` is the current moment.
- `UNIQUE`: no two rows may have the same value here.
- `CHECK (condition)`: every row must make the condition true, like `CHECK (age >= 18)`.
- `PRIMARY KEY`: this column identifies each row. It's automatically `NOT NULL` and `UNIQUE`, and other tables use it to point at a row.
- `GENERATED ALWAYS AS IDENTITY`: the database numbers the rows itself, 1, 2, 3 …

**An example on a different table,** from a small library app, using most of these:

```sql
CREATE TABLE books (
    id        BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    isbn      TEXT        NOT NULL UNIQUE,
    title     TEXT        NOT NULL,
    subtitle  TEXT,
    copies    INTEGER     NOT NULL DEFAULT 1 CHECK (copies >= 0),
    added_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Read it column by column: an id the database hands out, an ISBN that must be present and unique, a title that must be present, a subtitle that may be missing, a number of copies that defaults to 1 and can never go below 0, and the moment the book was added.

## 2. The decisions

The product's fields are listed in [`CONTRACT.md`](../../CONTRACT.md): `id`, `sku`, `name`, `description`, `category`, `image_url`, `price_cents`, `stock`, `created_at` and `updated_at`. Your columns have exactly those names. Their types and rules are yours to decide.

**Decide first.** For each decision below, write one line in `JOURNAL.md`, under `## M1-1`: your choice, and why. Write all six before you read on.

**Decision 1: what identifies a product?** Either the SKU (the shop's own product code) is the primary key, or there's a separate `id` the database generates. The facts:
- From M3 on, cart lines will store a product's key, and from M4 on, order lines will too, for as long as the store keeps orders.
- A SKU can change: someone fixes a typo, or relabels a product line.
- A number is smaller to store, and faster to compare, than text.

**Decision 2: how is the price stored?** As `REAL` dollars, as `NUMERIC(10,2)` dollars, or as `INTEGER` cents, where $19.99 is `1999`. The facts:
- Floating point is approximate. Try it: `python3 -c "print(0.1 + 0.2)"` prints `0.30000000000000004`.
- `NUMERIC` is exact, but Python receives it as a `Decimal` object, and JSON has no decimal type, so your API has to decide how to send it.
- Integer cents are exact, and a plain number in Postgres, Python, JSON and JavaScript alike. You divide by 100 only when you display a price.

**Decision 3: which columns may be missing?** Go through the columns, and mark each one `NOT NULL` or allowed to be `NULL`. For each, ask: could a product sensibly exist without this? What would a shop page, or an agent, do if it were missing?

**Decision 4: what does "no description" look like?** Some products won't have a description or an image. You could store `NULL`, an empty string `''`, or a stand-in like `'No description yet'` or a placeholder image's address. The facts:
- If both `NULL` and `''` are possible, "nothing" has two forms, and every piece of code that reads the column has to handle both.
- A stand-in looks like real data. An agent asked about the product will read `'No description yet'` out as if it were the description.

**Decision 5: when did it happen?** `created_at` and `updated_at` are dates and times. Should they be `TIMESTAMP` or `TIMESTAMPTZ`? The facts:
- Your database's clock runs on UTC.
- A browser in New York that receives a time with no zone, like `2026-11-08T15:00:00`, reads it as New York time, which is 5 hours off.
- With `TIMESTAMPTZ`, the database stores an exact moment, and your API sends it with its zone: `2026-11-08T15:00:00Z`.

**Decision 6: what must never go below zero, and where is that enforced?** Price and stock can't be negative. In step 3 you'll write Python models that refuse a negative number. The facts:
- Your Python models only check data that goes through them.
- An agent with database access, a script, a hand-typed SQL command in `make psql`, or a bug in your own code can all write to this table without going through them.
- Also: what should `stock` be when nobody says? And `created_at` and `updated_at` on a new row?

## 3. Compare with the contract

Now read "The table" in [`CONTRACT.md`](../../CONTRACT.md). It fixes several of these decisions, because callers can see them: what an API sends for a missing description, whether a time comes with its zone, what the database refuses. **Where your choice and the contract differ, the contract wins.** Write one line in your journal on why you think it chose as it did. The decisions it leaves open, like the price's type inside the table, stay yours.

## 4. Write it: `backend/migrations/001_create_products.sql`

**You write** the folder `backend/migrations/`, and in it a file called `001_create_products.sql`, holding one `CREATE TABLE products ( … );` that puts your decisions into practice.

**The idea: a migration.** A migration is a file that changes the database's structure, and it's applied once. They're numbered so they always run in the same order: `001_…` first, `002_…` next. In M2 you'll add a second one, to change this table without losing its data.

**Hint:** your table needs every rule the contract's table section lists. The library example shows the shape of each one.

## 5. Run it

```
make reset
```

`make reset` empties your database, then applies every migration in `backend/migrations/` in order, then the seed, if there is one. Use it whenever you change a migration while you're still in M1. It deletes every row, which is fine for now, because your seed puts them back. **You should see:**

```
applying backend/migrations/001_create_products.sql
done
```

**If you see `ERROR` instead,** read which word it points at. The usual causes are a missing comma between two columns, an extra comma after the last one, or a missing `;` at the end. Fix the file, and run `make reset` again.

Then look at your table:

```
docker compose exec db psql -U store -d store -c '\d products'
```

`psql` is Postgres's command-line tool. `-U store -d store` is the user and the database, and `-c` runs one command; `\d products` describes the table. My table shows this. Yours differs wherever your choices do:

```
                                   Table "public.products"
   Column    |           Type           | Collation | Nullable |           Default
-------------+--------------------------+-----------+----------+------------------------------
 id          | bigint                   |           | not null | generated always as identity
 sku         | text                     |           | not null |
 name        | text                     |           | not null |
 description | text                     |           |          |
 category    | text                     |           | not null |
 image_url   | text                     |           |          |
 price_cents | integer                  |           | not null |
 stock       | integer                  |           | not null | 0
 created_at  | timestamp with time zone |           | not null | now()
 updated_at  | timestamp with time zone |           | not null | now()
Indexes:
    "products_pkey" PRIMARY KEY, btree (id)
    "products_sku_key" UNIQUE CONSTRAINT, btree (sku)
Check constraints:
    "products_price_cents_check" CHECK (price_cents >= 0)
    "products_stock_check" CHECK (stock >= 0)
```

You never wrote an index, yet there's one for the primary key and one for the unique SKU. Each of those rules needs a fast way to find existing values, and an index is exactly that.

## 6. Predict, then break a rule on purpose

**Predict.** Under `## M1-1` in `PREDICTIONS.md`, write what happens when you insert a product with a price of −100 cents straight into the table, without any Python in the way.

```
docker compose exec db psql -U store -d store -c "INSERT INTO products (sku, name, category, price_cents) VALUES ('BAD-1', 'Bad', 'test', -100);"
```

My table answered:

```
ERROR:  new row for relation "products" violates check constraint "products_price_cents_check"
DETAIL:  Failing row contains (1, BAD-1, Bad, null, test, null, -100, 0, 2026-11-08 14:07:32.12723+00, 2026-11-08 14:07:32.12723+00).
```

Nothing was added. `products_price_cents_check` is the name Postgres gave a `CHECK` rule. Write what yours did under your prediction.

## Check

```
make check M=1 STEP=1
```

**You should see** the M0 checks pass, then these:

```
M1 · Products, and the store's first tools
  PASS  M1-1  your migrations apply to an empty database
  PASS  M1-1  the products table has the contract's columns
  PASS  M1-1  created_at and updated_at store a moment, with its time zone
  PASS  M1-1  a product with only the required columns gets its id and defaults from the database
  PASS  M1-1  the database refuses a negative price
  PASS  M1-1  the database refuses negative stock
  PASS  M1-1  the database refuses a second product with the same SKU
  PASS  M1-1  the database refuses a product without a sku, name, category or price

17 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

Each `FAIL` names the rule your table is missing. Change your file, run `make reset`, and check again.

## My reasoning, decision by decision

Open this only after your table passes.

<details><summary>My reasoning</summary>

1. **A generated `id`, not the SKU.** Cart and order lines will hold this key for as long as the store keeps orders. A SKU can be edited, and if it were the key, every row pointing at it would have to change too. A number the database hands out never needs to change.
2. **Integer cents.** Exact, and a plain number in every layer, so nothing ever rounds. The cost is dividing by 100 for display, which is one line in a page. Most payment APIs work the same way, in the currency's smallest unit.
3. **Required:** the SKU, the name, the category, the price and the stock, and both times. A product can't be sold without a name, a price or a SKU, and a shop groups products by category. **Optional:** the description and the image. Plenty of products have neither, and a page can show nothing, or a placeholder of its own.
4. **`NULL`, and only `NULL`.** The contract makes the empty string impossible (step 3's models refuse it), so "nothing" has exactly one form, and no stand-in can pass for real data.
5. **`TIMESTAMPTZ`.** It stores an exact moment, so every reader in every time zone agrees on when something happened.
6. **`CHECK (price_cents >= 0)` and `CHECK (stock >= 0)`, in the table,** as well as in the models you'll write in step 3. The models give a caller a clear message. The table is the one place every writer has to pass, agents and scripts included. **`stock` defaults to 0,** because an admin adds a product first and stocks it later. **Both times default to `now()`.** Nothing here changes `updated_at` when a row is edited; that comes in M2.
</details>

## Step done

Look at what git sees:

```
git status --short
```

**You should see** this. `M` means changed, and `??` new. Your journal and predictions are listed because you wrote in them:

```
 M JOURNAL.md
 M PREDICTIONS.md
?? backend/migrations/
```

Then commit and push:

```
git add -A
git commit -m "M1-1: the products table"
git push
```

Your journal has your six decisions and your comparison with the contract. Your predictions have what happened. Then answer your tutor's questions for this step, under `## M1-1`.

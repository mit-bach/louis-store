# Step M4-1 · Orders

**Why:** a checkout produces an order, and an order is the one record a store can never lose. It's what was bought, by whom, for how much. This step builds its two tables, and makes one decision about how long an order lives.

## Decide first: should an order point at its session?

An order is placed by a session. `orders` will have a column `session_token`. You could make it a foreign key, `REFERENCES sessions (token)`, as `cart_items` has. The facts:
- Sessions expire after an hour. A store doesn't keep millions of dead sessions: a cleanup job deletes old ones. It's optional spec 1 in your roadmap, and every real store has one.
- A foreign key with no `ON DELETE` rule refuses to delete a session that any order points at. With `ON DELETE CASCADE`, deleting the session deletes its orders.
- A customer's order, and what they paid, has to outlive their session by months or years: for refunds, for accounts, for the law.
- Only `checkout` writes orders, and it checks the session first.

**Write your choice, and why, under `## M4-1` in `JOURNAL.md`, before you open the answer.**

<details><summary>Check your choice</summary>

No foreign key: a plain `session_token TEXT NOT NULL`. With a foreign key, the cleanup either fails on every session that ever bought something, or, with a cascade, deletes the customers' orders. The column still records which session placed the order. It just doesn't tie the order's life to the session's. The rule a foreign key would protect, that the session existed, is already enforced by the only code that writes orders.

Your cart lines are the opposite case: they belong to a session and should die with it. Same column name, opposite rule.
</details>

## The idea: an order and its lines

An order is two tables, the way a cart is:
- **`orders`:** one row per order: its `id`, the session that placed it, its `total_cents`, and when.
- **`order_lines`:** one row per product in it: which order, which product, how many, and **`price_cents`, the price paid**.

The line keeps its own copy of the price. A product's price will change: a sale, a mistake corrected, inflation. An order placed last week must still say what was paid last week. Reading the price from `products` would rewrite history every time the price changed. Copying a value at the moment it matters is called a **snapshot**.

**An example on a different table,** the library's loans. A loan has lines, and each line keeps the book's title as it was:

```sql
CREATE TABLE loans (
    id          BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    card_token  TEXT        NOT NULL,
    borrowed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

```sql
CREATE TABLE loan_lines (
    loan_id BIGINT  NOT NULL REFERENCES loans (id),
    book_id BIGINT  NOT NULL REFERENCES books (id),
    copies  INTEGER NOT NULL CHECK (copies > 0),
    title   TEXT    NOT NULL,
    PRIMARY KEY (loan_id, book_id)
);
```

```python
class LoanLine(BaseModel):
    book_id: int
    title: str
    copies: int


class Loan(BaseModel):
    id: int
    items: list[LoanLine]
    borrowed_at: datetime
```

## You write

- **`backend/migrations/005_create_orders.sql`** and **`006_create_order_lines.sql`,** as [`CONTRACT.md`](../../CONTRACT.md) describes them in "M4 · Orders". Apply them with `make migrate`.
- **`backend/schemas.py`:** `OrderLine` and `Order`.

**Hint:** an order line needs no `id` of its own. `(order_id, product_id)` is its key, as `(session_token, product_id)` is a cart line's.

## Check

```
make migrate
```

```
applying backend/migrations/005_create_orders.sql
applying backend/migrations/006_create_order_lines.sql
migrations up to date
```

**Predict,** under `## M4-1` in `PREDICTIONS.md`: with your tables, what happens when a session that has placed an order is deleted? Then try it by hand, inside a transaction you roll back, so nothing stays changed:

```
docker compose exec -T db psql -U store -d store <<'EOF'
BEGIN;
INSERT INTO sessions (token) VALUES ('try-me');
INSERT INTO orders (session_token, total_cents) VALUES ('try-me', 100);
DELETE FROM sessions WHERE token = 'try-me';
SELECT count(*) FROM orders WHERE session_token = 'try-me';
ROLLBACK;
EOF
```

<details><summary>What mine showed</summary>

```
BEGIN
INSERT 0 1
INSERT 0 1
DELETE 1
 count
-------
     1
(1 row)

ROLLBACK
```

The session was deleted (`DELETE 1`), and the order is still there (`count` is 1). `ROLLBACK` then undid all three changes.
</details>

```
make check M=4 STEP=1
```

**You should see** everything before, then:

```
M4 · Checkout, and two buyers at once
  PASS  M4-1  the orders and order_lines tables: an order keeps its lines, each line the price it was bought at
  PASS  M4-1  an order outlives its session: deleting the session leaves the order

88 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

## Step done

```
git status --short
```

```
 M JOURNAL.md
 M PREDICTIONS.md
 M backend/schemas.py
?? backend/migrations/005_create_orders.sql
?? backend/migrations/006_create_order_lines.sql
```

```
git add -A
git commit -m "M4-1: orders"
git push
```

Answer your tutor's questions under `## M4-1` in `JOURNAL.md`.

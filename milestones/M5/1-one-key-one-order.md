# Step M5-1 · One key, one order

**Why:** agents retry. An agent calls `checkout`, the store places the order, and the answer is lost on the way back: a dropped connection, a timeout, a restart. The agent doesn't know whether it bought anything. A careful agent tries again. Your store has to make "try again" safe.

## What your store does today

**Predict,** under `## M5-1` in `PREDICTIONS.md`: a checkout goes through, and the same checkout is sent again straight after. What does the second call get? And what might an agent do next?

A session with one product in its cart, checked out twice. Copy the whole block:

```
TOKEN=$(./store session start | python3 -c "import json, sys; print(json.load(sys.stdin)['token'])")
./store cart set 4 1 --session $TOKEN > /dev/null
./store checkout --session $TOKEN > /dev/null
./store checkout --session $TOKEN; echo "exit code $?"
```

```
Your cart is empty.
exit code 4
```

Nothing was bought twice. But the second answer says the cart is empty, which is true whether the first checkout worked or never had anything to buy. An agent that reads it as "my cart was lost" puts the product back and checks out again: two orders, two charges. The store needs a way to tell a retry from a new purchase.

**The fix is a name for the purchase.** The caller makes up a key, any text, for one checkout, and sends it with every try of that checkout. The order records its key. When a key comes back that already has an order, the store returns that order instead of buying again. That key is called an **idempotency key**: idempotent means "doing it twice has the same effect as doing it once".

## Decide first: what is a key unique over?

Two options:
- **(a) The whole `orders` table:** one key, one order, whoever sent it.
- **(b) Each session:** one key, one order, per session.

The facts:
- The caller chooses the key. Two agents can easily pick the same one, like `buy-lantern` or `order-1`.
- When the store finds a key that already has an order, it returns that order to whoever asked.
- A session is one customer, and its token is its proof.

**Write (a) or (b), and why, under `## M5-1` in `JOURNAL.md`, before you open the answer.**

<details><summary>Check your choice</summary>

(b), each session. With (a), a second customer whose agent happened to pick `buy-lantern` would get the first customer's order back: their lantern, their total, their order number. That's another customer's purchase handed to a stranger, the same leak as M4-5's psql query, through your own API. So the key is unique per session: `UNIQUE (session_token, idempotency_key)`, and the lookup uses both.
</details>

## The idea

**The migration** adds a column and a constraint:
- `ALTER TABLE orders ADD COLUMN idempotency_key TEXT;`. Existing orders get `NULL`, and so does any checkout without a key.
- `ALTER TABLE orders ADD CONSTRAINT <name> UNIQUE (session_token, idempotency_key);`. A `UNIQUE` over two columns refuses a second row with the same *pair*. `NULL` is never equal to anything, even another `NULL`, so orders without a key never clash.

**Where the lookup goes matters.** Two tries of one checkout can arrive at the same instant. Remember from M4: the second one's locking read waits until the first commits. And each statement inside a transaction sees what was committed when *that statement* started. So a lookup placed right after the locking read runs after the wait, and sees the first try's order. Put it anywhere earlier, and both tries can look before either has written. Step 2 tests exactly that.

The order of the work inside `checkout`, with what's new in bold:
1. check the session;
2. the locking read, as in M4;
3. **if a key was given, look for this session's order with it. If there is one, return it, as it was placed, and change nothing;**
4. no lines: `EmptyCart`. (A retry finds its order in step 3, before the empty cart can be reported.)
5. the M4 checks, then **insert the order with its key**, its lines, the stock and the cart, as before.

**Returning the order "as it was placed"** means reading it back: the order's row, and its lines with the prices paid. That's a new function.

**An example on a different table,** the library. Borrowing takes a key the same way. First its lookup, right after the locking read:

```python
def borrow(token: str | None, idempotency_key: str | None = None) -> Loan:
    require_card(token)
    with pool.connection() as conn:
        lines = conn.execute(
            """
            SELECT b.id AS book_id, b.title, b.copies AS on_hand,
                   b.withdrawn_at IS NULL AS on_shelf, i.copies
            FROM basket_items i
            JOIN books b ON b.id = i.book_id
            WHERE i.card_token = %s
            ORDER BY b.id
            FOR UPDATE OF b
            """,
            (token,),
        ).fetchall()
        if idempotency_key is not None:
            done = conn.execute(
                "SELECT id FROM loans WHERE card_token = %s AND idempotency_key = %s",
                (token, idempotency_key),
            ).fetchone()
            if done:
                return read_loan(conn, done["id"])
        if not lines:
```

Then reading a loan back:

```python
def read_loan(conn, loan_id: int) -> Loan:
    """A loan as it was made."""
    head = conn.execute("SELECT id, borrowed_at FROM loans WHERE id = %s", (loan_id,)).fetchone()
    lines = conn.execute(
        "SELECT book_id, title, copies FROM loan_lines WHERE loan_id = %s ORDER BY book_id", (loan_id,)
    ).fetchall()
    return Loan(id=head["id"], items=[LoanLine(**line) for line in lines], borrowed_at=head["borrowed_at"])
```

## You write

- **`backend/migrations/007_add_idempotency_key.sql`,** as [`CONTRACT.md`](../../CONTRACT.md), "M5 · Retries", describes. Apply it with `make migrate`.
- **In `backend/orders.py`:**
  - `checkout(token: str | None, idempotency_key: str | None = None) -> Order`, with the lookup where step 3 above puts it, and the key in the order's `INSERT`;
  - `read_order(conn, order_id: int) -> Order`, which reads an order and its lines back, sorted by `product_id`, at the prices paid.

**Hint:** `return read_order(conn, ...)` inside the `with` block is fine. Leaving the block commits a transaction that changed nothing.

## Check

The same as before, with a key, then the same key from another session. Copy the whole block:

```
docker compose exec -T api python - <<'EOF'
import cart, orders, products, sessions
from db import pool

token = sessions.start_session().token
cart.set_cart_item(token, 5, 1)
before = products.get_product(5).stock
first = orders.checkout(token, "my-first-key")
again = orders.checkout(token, "my-first-key")
print("orders", first.id, "and", again.id, "same:", first == again)
print("stock", before, "->", products.get_product(5).stock)
other = sessions.start_session().token
cart.set_cart_item(other, 5, 1)
print("another session, the same key: order", orders.checkout(other, "my-first-key").id)
pool.close()
EOF
```

**You should see** the same order twice, the stock lowered once, and the other session's own order:

```
orders 2 and 2 same: True
stock 10 -> 9
another session, the same key: order 3
```

```
make check M=5 STEP=1
```

**You should see** everything before, then:

```
  PASS  M5-1  checkout(token, key) twice: the same order back, one order placed, the stock lowered once
  PASS  M5-1  a key belongs to its session; without a key, checkout is as in M4; a refused checkout records nothing

101 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

## Step done

```
git status --short
```

```
 M JOURNAL.md
 M PREDICTIONS.md
 M backend/orders.py
?? backend/migrations/007_add_idempotency_key.sql
```

```
git add -A
git commit -m "M5-1: one key, one order"
git push
```

Answer your tutor's questions under `## M5-1` in `JOURNAL.md`.

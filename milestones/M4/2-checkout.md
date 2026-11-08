# Step M4-2 · Checkout, in one transaction

**Why:** this is the operation the whole course has been leading to. Several products, several checks, several writes, and two customers who may want the same last unit at the same moment. It has to be all or nothing, and it has to be safe when it runs twice at once.

## Decide first: how does checkout take the stock?

In M2, `adjust_stock` was safe as one `UPDATE … SET stock = stock + %s`, with the table's `CHECK` refusing a stock below zero. Checkout could do the same:
- **(a) One `UPDATE` per line.** For each cart line, `UPDATE products SET stock = stock - quantity`, all in one transaction. If the `CHECK` refuses one, the transaction rolls back everything.
- **(b) Lock, then check.** First read every line's product with `SELECT … FOR UPDATE`, which locks those rows until the transaction ends. Then check every line in Python, and only then write the order, the stock and the cart.

The facts:
- Checkout needs more than the stock: each product's price for the order, whether it's still for sale, and its name for the messages. It has to read those anyway.
- A refused `UPDATE` raises `CheckViolation` from the database. It says a constraint failed, not which product, or how many are left, or what the customer should do.
- With (a), each `UPDATE` locks its row when it runs, in whatever order the lines come. Two checkouts holding the same two products can take them in opposite orders.
- A locked row isn't blocked for reading by everyone, only for writers and for other `FOR UPDATE` reads. Those wait until the lock is released.

**Write (a) or (b), and why, under `## M4-2` in `JOURNAL.md`, before you open the answer.**

<details><summary>Check your choice</summary>

(b), lock, then check. Checkout reads several facts, decides, and then writes. That's the "look, then act" shape from M2, and the lock is what closes its gap. Nobody can change those rows between the look and the act, because they wait. Reading under the lock also means the prices, the availability and the stock it checks are exactly the ones it writes against. The checks then happen in your code, with your messages, before anything is written. (a) is safe from overselling, but its only refusal is the database's `CheckViolation`, and it takes its locks in the cart's order: two carts with the same products in opposite orders can each hold one row and wait for the other's. That's a **deadlock**, and step 4 tests for it.
</details>

## Decide first: a line that isn't for sale any more

A customer's cart holds a tent and a bottle. Yesterday the bottle was archived, so its line shows `available: false`. Now they check out. Checkout could:
- **(a) Skip** the bottle, and sell the tent.
- **(b) Refuse** the whole checkout, name the bottle, and tell them to remove it.

The facts:
- With (a), the customer is charged for a cart that's different from the one they reviewed and agreed to.
- With (b), they have to fix their cart before they can buy anything.
- An agent buying for a customer reports back what it did. With (a), the change happens inside the store, and the agent may never notice it to report it.

**Write (a) or (b), and why, under `## M4-2`, before you open the answer.**

<details><summary>Check your choice</summary>

(b), refuse, and name each unavailable line. A checkout is the customer's agreement to a specific list at a specific price. Changing the list silently breaks that agreement, and an agent acting for someone makes a silent change worse: nobody may ever see it. Refusing costs one extra step, and the message says exactly which step. A price that changed since the product went in the cart is different: prices are expected to change, the order records the price actually paid, and the total is in the order the customer gets back. So only availability blocks a checkout.
</details>

## The idea: one transaction, with locks

**Everything inside one `with pool.connection() as conn:` block is one transaction.** The first statement starts it, and the end of the block commits it. An exception raised inside the block rolls back every statement in it, as if none had run, and releases its locks.

**`SELECT … FOR UPDATE OF p`** locks the rows it returns from the table `p` until the transaction ends. A second checkout's `FOR UPDATE` on any of the same rows waits at that line until the first commits or rolls back. Then it reads the rows as they are *after* the first: a sold unit is gone.

**`ORDER BY p.id` before `FOR UPDATE`** makes every checkout take its locks in the same order, smallest id first. Two checkouts can then never each hold a row the other wants.

**The order of the work inside:**
1. check the session;
2. read and lock: every cart line, joined to its product, `ORDER BY p.id FOR UPDATE OF p`;
3. no lines: raise `EmptyCart`;
4. any unavailable line: raise `NotForSale`, naming each;
5. any line that wants more than is in stock: raise `InsufficientStock`, one sentence per line;
6. insert the order, with `total_cents` from the prices you just read, and `RETURNING id, created_at`;
7. for each line, insert its order line, with the price you read, and lower the product's stock;
8. delete the cart's lines;
9. leave the block: commit.

**An example on a different table,** the library lending out a basket of books:

```python
import books
from cards import require_card
from db import pool
from schemas import Loan, LoanLine


class EmptyBasket(Exception):
    """Raised when a card borrows with nothing in its basket."""


class Withdrawn(Exception):
    """Raised when a basket holds books that were withdrawn after they went in."""


def borrow(token: str | None) -> Loan:
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
        if not lines:
            raise EmptyBasket("Your basket is empty.")
        gone = [line for line in lines if not line["on_shelf"]]
        if gone:
            raise Withdrawn("Withdrawn since you chose them: " + ", ".join(line["title"] for line in gone) + ".")
        short = [line for line in lines if line["copies"] > line["on_hand"]]
        if short:
            raise books.NotEnoughCopies(
                " ".join(f"Only {line['on_hand']} of {line['title']} on the shelf." for line in short)
            )
        loan = conn.execute(
            "INSERT INTO loans (card_token) VALUES (%s) RETURNING id, borrowed_at",
            (token,),
        ).fetchone()
        for line in lines:
            conn.execute(
                "INSERT INTO loan_lines (loan_id, book_id, copies, title) VALUES (%s, %s, %s, %s)",
                (loan["id"], line["book_id"], line["copies"], line["title"]),
            )
            conn.execute(
                "UPDATE books SET copies = copies - %s WHERE id = %s",
                (line["copies"], line["book_id"]),
            )
        conn.execute("DELETE FROM basket_items WHERE card_token = %s", (token,))
    items = [LoanLine(book_id=line["book_id"], title=line["title"], copies=line["copies"]) for line in lines]
    return Loan(id=loan["id"], items=items, borrowed_at=loan["borrowed_at"])
```

`"it" if len(gone) == 1 else "them"` is a **conditional expression**: one value or the other, in one line. The messages are written for a person, or an agent, who has to act on them.

## You write: `backend/orders.py`

A new module, with:
- `class EmptyCart(Exception):` and `class NotForSale(Exception):`, each with a one-line docstring;
- `checkout(token: str | None) -> Order`, doing the nine steps above, with exactly the messages in [`CONTRACT.md`](../../CONTRACT.md), "M4 · Checkout". It raises `products.InsufficientStock` for a short line, so every way in already knows what to do with it.

**Hint:** every `raise` for a refusal goes *inside* the `with` block, after the locking read. That way the transaction rolls back, and its locks are released, the moment you raise.

## Check

A cart, then a checkout, run inside your container. Copy the whole block:

```
docker compose exec -T api python - <<'EOF'
import cart, orders, products, sessions
from db import pool

token = sessions.start_session().token
cart.set_cart_item(token, 3, 2)
before = products.get_product(3).stock
order = orders.checkout(token)
print("order", order.id, "total_cents", order.total_cents, "lines", len(order.items))
print("stock", before, "->", products.get_product(3).stock)
print("cart", cart.get_cart(token))
pool.close()
EOF
```

**You should see** the new order's id and total, the stock lowered by 2, and an empty cart. Mine was order 2, not 1: step 1's test insert was rolled back, but the id it took wasn't given back. Postgres never reuses an id, even after a rollback, so ids can have gaps. Mine:

```
order 2 total_cents 11800 lines 1
stock 12 -> 10
cart items=[] total_cents=0
```

```
make check M=4 STEP=2
```

**You should see** everything before, then:

```
  PASS  M4-2  orders.py imports nothing from the web, the command line or the tool server
  PASS  M4-2  checkout() places one order at the database's prices, lowers the stock, and empties the cart
  PASS  M4-2  an order keeps the price it was bought at, after the product's price changes
  PASS  M4-2  checkout() refuses an empty cart, a short line or an unavailable line, with the contract's message, and changes nothing

92 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

The refusal check fills carts with short and unavailable lines, and makes sure each refusal changed nothing.

## Step done

```
git status --short
```

```
 M JOURNAL.md
 M PREDICTIONS.md
?? backend/orders.py
```

```
git add -A
git commit -m "M4-2: checkout, in one transaction"
git push
```

Answer your tutor's questions under `## M4-2` in `JOURNAL.md`.

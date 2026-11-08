# Step M4-3 · Checkout, three ways in

**Why:** `checkout` works in Python. Now a web page, a script and an agent need to reach it, each with the same rules and the same messages.

## Decide first: where does the total come from?

The customer's page shows a total, and so does `GET /cart`. When they check out, the order's `total_cents` could come from:
- **(a)** the total the client sends with the checkout request, the one the customer saw;
- **(b)** the cart's total, as `GET /cart` last showed it;
- **(c)** the database's prices, read under the lock, at the moment of checkout.

The facts:
- Anyone can send any request to your API, with any body: a browser's developer tools, `curl`, an agent told to "get a good price".
- `GET /cart` might have been read an hour ago, and a price might have changed since.
- Step 2's checkout reads every price under the lock anyway, to write the order lines.

**Write (a), (b) or (c), and why, under `## M4-3` in `JOURNAL.md`, before you open the answer.**

<details><summary>Check your choice</summary>

(c). A number the client sends is a number the client chose. Trusting it would let anyone set their own price. A cart total read earlier can be out of date. The prices read under the lock are the ones the order's lines record, so the total is their sum, by construction. That's why `POST /checkout` takes no body at all: there's nothing a caller could send that checkout should believe. The check sends a body with `"total_cents": 1` anyway, to make sure it's ignored.
</details>

## The idea

Nothing new: checkout reaches the outside the way the cart did. The route reads the token with your `session_token` dependency, the command takes `--session`, and the tool takes `session_token`. Each one maps the errors:
- `NoSession` gives `401`, exit `5`, or a tool error;
- `EmptyCart`, `NotForSale` and `InsufficientStock` are all conflicts with what's stored, so they give `409`, exit `4`, or a tool error, each with its message.

The command sits at the top level, `./store checkout`, beside the `products`, `session` and `cart` groups: `@app.command("checkout")`.

**An example on a different table,** the library's borrow:

```python
@app.post("/borrow", response_model=Loan, status_code=201)
def post_borrow(token: str | None = Depends(card_token)):
    try:
        return loans.borrow(token)
    except cards.NoCard as e:
        raise no_card(e)
    except (loans.EmptyBasket, loans.Withdrawn, books.NotEnoughCopies) as e:
        raise HTTPException(status_code=409, detail=str(e))
```

```python
@app.command("borrow")
def borrow_command(card: CardOption = None):
    """Borrow everything in a card's basket: one loan, and the basket emptied."""
    try:
        print_json(loans.borrow(card))
    except cards.NoCard as e:
        fail(str(e), 5)
    except (loans.EmptyBasket, loans.Withdrawn, books.NotEnoughCopies) as e:
        fail(str(e), 4)
```

```python
@mcp.tool()
def borrow(card_token: str | None = None) -> Loan:
    """Borrow everything in the card's basket: one loan, the copies taken off the shelf, and the
    basket emptied. If any book can't be borrowed, nothing is, and the error says which and why."""
    try:
        return loans.borrow(card_token)
    except (cards.NoCard, loans.EmptyBasket, loans.Withdrawn, books.NotEnoughCopies) as e:
        raise ToolError(str(e))
```

The tool's docstring says what happens when any line can't be bought: nothing is. An agent that knows a refusal changed nothing can safely fix the cart and try again.

## You write

- **`backend/main.py`:** `POST /checkout`, answering `201` with the `Order`.
- **`backend/cli.py`:** `checkout --session TOKEN`, a top-level command.
- **`backend/tools.py`:** the `checkout` tool, taking `session_token`. Its docstring says what it buys, at whose prices, and that a refusal changes nothing.

**Hint:** `except (orders.EmptyCart, orders.NotForSale, products.InsufficientStock) as e:` catches all three conflicts in one clause.

## Check

A session with one product in its cart, checked out over HTTP. Copy the whole block:

```
TOKEN=$(./store session start | python3 -c "import json, sys; print(json.load(sys.stdin)['token'])")
./store cart set 4 1 --session $TOKEN > /dev/null
curl -s -w '\n%{http_code}\n' -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8000/checkout
```

```
{"id":3,"items":[{"product_id":4,"sku":"BAG-0C","name":"Sleeping Bag 0 C","quantity":1,"price_cents":8900,"line_total_cents":8900}],"total_cents":8900,"created_at":"2026-11-08T19:18:13.600287Z"}
201
```

The same session again, whose cart is now empty:

```
curl -s -w '\n%{http_code}\n' -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8000/checkout
```

```
{"detail":"Your cart is empty."}
409
```

From the command line, with a new session:

```
TOKEN=$(./store session start | python3 -c "import json, sys; print(json.load(sys.stdin)['token'])")
./store cart set 5 1 --session $TOKEN > /dev/null
./store checkout --session $TOKEN
```

```
{
  "id": 4,
  "items": [
    {
      "product_id": 5,
      "sku": "PAD-AIR",
      "name": "Air Pad",
      "quantity": 1,
      "price_cents": 7400,
      "line_total_cents": 7400
    }
  ],
  "total_cents": 7400,
  "created_at": "2026-11-08T19:18:14.902304Z"
}
```

```
make check M=4 STEP=3
```

**You should see** everything before, then:

```
  PASS  M4-3  POST /checkout: 201 with the order; 409 with the contract's message; 401; and it ignores a total the client sends
  PASS  M4-3  ./store checkout and the checkout tool: the order, or the same messages with exit 4 or 5 and a tool error
  PASS  M4-3  parity: checkout has its route, its command and its tool

95 passed, 0 failed, 0 skipped.
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
 M backend/tools.py
```

```
git add -A
git commit -m "M4-3: checkout, three ways in"
git push
```

Commit before step 4: you'll break `orders.py` on purpose there, and put it back with git. Answer your tutor's questions under `## M4-3` in `JOURNAL.md`.

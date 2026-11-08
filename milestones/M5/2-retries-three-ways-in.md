# Step M5-2 · Retries, three ways in, and at the same instant

**Why:** `checkout` takes a key in Python. Now each caller needs a way to send one: a header for HTTP, an option for the command line, an argument for the tool. Then you test the hard case: a retry that arrives while the first try is still running.

## The idea

Each way in passes the key on to `orders.checkout`, and changes nothing else:
- **HTTP:** a request header, `Idempotency-Key: <key>`, which is the name most APIs use. In FastAPI, a parameter `idempotency_key: str | None = Header(default=None)` reads it: FastAPI turns the underscore into a hyphen, and header names don't care about capitals.
- **The command line:** `--idempotency-key KEY` on `./store checkout`.
- **The tool:** an argument `idempotency_key`. **Its description is the only way an agent learns the key exists, or why it should send one.** So it says: make up a key for each purchase, and call again with the same key when you're not sure a checkout went through.

A repeat answers exactly as the first did: `201` and the same order, not a `200` or a note saying "already done". The caller can't tell a first answer from a repeat, and doesn't need to.

**An example on a different table,** the library's borrow, three ways in:

```python
@app.post("/borrow", response_model=Loan, status_code=201)
def post_borrow(token: str | None = Depends(card_token), idempotency_key: str | None = Header(default=None)):
    try:
        return loans.borrow(token, idempotency_key)
    except cards.NoCard as e:
        raise no_card(e)
    except (loans.EmptyBasket, loans.Withdrawn, books.NotEnoughCopies) as e:
        raise HTTPException(status_code=409, detail=str(e))
```

```python
@app.command("borrow")
def borrow_command(
    card: CardOption = None,
    idempotency_key: Annotated[str | None, typer.Option(help="Your name for this loan. Retry with the same key: one loan.")] = None,
):
    """Borrow everything in a card's basket: one loan, and the basket emptied."""
    try:
        print_json(loans.borrow(card, idempotency_key))
    except cards.NoCard as e:
        fail(str(e), 5)
    except (loans.EmptyBasket, loans.Withdrawn, books.NotEnoughCopies) as e:
        fail(str(e), 4)
```

```python
@mcp.tool()
@agent_errors
def borrow(card_token: str | None = None, idempotency_key: str | None = None) -> Loan:
    """Borrow everything in the card's basket: one loan, the copies taken off the shelf, and the
    basket emptied. If any book can't be borrowed, nothing is, and the error says which and why.
    Give an idempotency_key you make up for this loan. Not sure it went through? Call again with the
    same key: you get the same loan back, and nothing is borrowed twice."""
    try:
        return loans.borrow(card_token, idempotency_key)
    except (cards.NoCard, loans.EmptyBasket, loans.Withdrawn, books.NotEnoughCopies) as e:
        raise ToolError(str(e))
```

(Ignore `@agent_errors` above the tool for now: it's step 3.)

## You write

- **`backend/main.py`:** `POST /checkout` reads the `Idempotency-Key` header and passes it on.
- **`backend/cli.py`:** `./store checkout` takes `--idempotency-key`.
- **`backend/tools.py`:** the `checkout` tool takes `idempotency_key`. Rewrite its description so an agent knows what the key is for, and when to send the same one again.

## Check

The same key twice, over HTTP. Copy the whole block:

```
TOKEN=$(./store session start | python3 -c "import json, sys; print(json.load(sys.stdin)['token'])")
./store cart set 6 1 --session $TOKEN > /dev/null
for i in 1 2; do curl -s -w '\n%{http_code}\n' -X POST -H "Authorization: Bearer $TOKEN" -H 'Idempotency-Key: my-http-key' http://localhost:8000/checkout; done
```

**You should see** `201` twice, with the same order:

```
{"id":4,"items":[{"product_id":6,"sku":"STOVE-CAN","name":"Canister Stove","quantity":1,"price_cents":3900,"line_total_cents":3900}],"total_cents":3900,"created_at":"2026-11-08T21:19:47.163218Z"}
201
{"id":4,"items":[{"product_id":6,"sku":"STOVE-CAN","name":"Canister Stove","quantity":1,"price_cents":3900,"line_total_cents":3900}],"total_cents":3900,"created_at":"2026-11-08T21:19:47.163218Z"}
201
```

## The retry test

`checks/retry_test.py` is a given script. It adds a product of its own with 2 in stock. Each round, a new session puts 1 in its cart and checks out twice with one key: one after the other in odd rounds, and at the same instant in even rounds. A safe store answers both with the same order, and ends each round with a stock of 1, not 0. `--via` picks the way in; `all` runs the three, one after the other.

```
uv run checks/retry_test.py --via all
```

**You should see:**

```
Installed 31 packages in 40ms
Retries through http: 20 rounds, each one checkout sent twice with one key.
20/20 rounds: one order, both answers the same, stock lowered once
Retries through cli: 20 rounds, each one checkout sent twice with one key.
20/20 rounds: one order, both answers the same, stock lowered once
Retries through tools: 20 rounds, each one checkout sent twice with one key.
20/20 rounds: one order, both answers the same, stock lowered once
```

## The control: look too early

Your step 1 work is committed. In `backend/orders.py`, move your key lookup (the `if idempotency_key is not None:` block) up, so it runs **before** the locking read: the first thing inside the `with` block. Save, and give the server about 10 seconds to restart.

**Predict,** under `## M5-2` in `PREDICTIONS.md`: the odd rounds send the two tries one after the other, and the even rounds at the same instant. Which rounds still pass? And what happens to the second try in the others?

```
uv run checks/retry_test.py --rounds 20
```

<details><summary>What mine showed (open it after your run)</summary>

```
Retries through http: 20 rounds, each one checkout sent twice with one key.
  round 2 (at the same instant): stock 1: 500 Internal Server Error; 201 {'id': 66, 'items': [{'product_id': 14, 'sku': 'RETRY-1794172816089', 'name': 'Retry test unit', 'quantity': 1, 'price_cents': 1500, 'line_t
  round 4 (at the same instant): stock 1: 201 {'id': 69, 'items': [{'product_id': 14, 'sku': 'RETRY-1794172816089', 'name': 'Retry test unit', 'quantity': 1, 'price_cents': 1500, 'line_t; 500 Internal Server Error
  round 6 (at the same instant): stock 1: 500 Internal Server Error; 201 {'id': 72, 'items': [{'product_id': 14, 'sku': 'RETRY-1794172816089', 'name': 'Retry test unit', 'quantity': 1, 'price_cents': 1500, 'line_t
  round 8 (at the same instant): stock 1: 500 Internal Server Error; 201 {'id': 75, 'items': [{'product_id': 14, 'sku': 'RETRY-1794172816089', 'name': 'Retry test unit', 'quantity': 1, 'price_cents': 1500, 'line_t
  round 10 (at the same instant): stock 1: 500 Internal Server Error; 201 {'id': 78, 'items': [{'product_id': 14, 'sku': 'RETRY-1794172816089', 'name': 'Retry test unit', 'quantity': 1, 'price_cents': 1500, 'line_t
  round 12 (at the same instant): stock 1: 500 Internal Server Error; 201 {'id': 81, 'items': [{'product_id': 14, 'sku': 'RETRY-1794172816089', 'name': 'Retry test unit', 'quantity': 1, 'price_cents': 1500, 'line_t
  round 14 (at the same instant): stock 1: 201 {'id': 84, 'items': [{'product_id': 14, 'sku': 'RETRY-1794172816089', 'name': 'Retry test unit', 'quantity': 1, 'price_cents': 1500, 'line_t; 500 Internal Server Error
  round 16 (at the same instant): stock 1: 201 {'id': 87, 'items': [{'product_id': 14, 'sku': 'RETRY-1794172816089', 'name': 'Retry test unit', 'quantity': 1, 'price_cents': 1500, 'line_t; 500 Internal Server Error
  round 18 (at the same instant): stock 1: 201 {'id': 90, 'items': [{'product_id': 14, 'sku': 'RETRY-1794172816089', 'name': 'Retry test unit', 'quantity': 1, 'price_cents': 1500, 'line_t; 500 Internal Server Error
  round 20 (at the same instant): stock 1: 201 {'id': 93, 'items': [{'product_id': 14, 'sku': 'RETRY-1794172816089', 'name': 'Retry test unit', 'quantity': 1, 'price_cents': 1500, 'line_t; 500 Internal Server Error
10/20 rounds: one order, both answers the same, stock lowered once
```

Tested three times on 2026-11-08, 20 rounds each, the result was the same every time: **10/20**. Every odd round passed, and every even round failed.
- **In the odd rounds,** the second try started after the first had committed, so even a lookup at the very top found the order.
- **In the even rounds,** both tries looked for the key before either had written, found nothing, and went on. One placed the order. The other waited at the locking read, carried on with the stock that was left, and tried to insert its own order with the same key.
- **Your `UNIQUE` constraint from step 1 refused that insert,** so there was never a second order, and the stock went down once. But the second try crashed with a `500`, where it should have got its order.

It's M4's lesson again. There, the `CHECK` stopped the oversell, and the lock made the answer clean. Here, the `UNIQUE` constraint stops the double order, and the lookup's place makes the answer right.
</details>

Write under your prediction what happened, and why. `make logs` shows the error behind each failed try. Then put your lookup back:

```
git checkout -- backend/orders.py
```

Give the server 10 seconds, and run the retry test again. **You should see** 20 out of 20.

**The lesson in one line:** where a check reads matters as much as what it reads. It has to look after the lock, or it can look before the other try has written.

## Check

```
make check M=5 STEP=2
```

**You should see** everything before, then:

```
  PASS  M5-2  the retry test through ./store: 6 rounds
  PASS  M5-2  the retry test through the tools: 10 rounds

105 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

The check runs the retry test through all three ways in: 20 rounds over HTTP, 6 through `./store` (each one starts a process in your container, so they're slow), and 10 through the tools.

## Step done

`git status` should list your three changed files, and your journal and predictions. `orders.py` must match your step 1 commit.

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
git commit -m "M5-2: retries, three ways in"
git push
```

Answer your tutor's questions under `## M5-2` in `JOURNAL.md`.

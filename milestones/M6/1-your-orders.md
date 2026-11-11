# Step M6-1 · Your orders, and the door for the browser

**Why:** in this milestone your coding agent builds the store's web pages, from a spec you write. Before it can, the backend needs two last things, and they're yours, by hand. Customers need to see what they've bought, and so does the walkthrough in step 4. And a browser has to be allowed to call your API at all.

## Decide first: whose orders can a page show?

A page will list orders. Three ways to give it them:
- **(a)** `GET /orders/{id}`: any order, by its number.
- **(b)** `GET /orders`: the orders of the session that asks, and no others.
- **(c)** Accounts, with a sign-in, so a customer sees every order they've ever placed.

The facts:
- Order numbers are a counter: 1, 2, 3. Anyone can count.
- The session token is the only proof your store has of who's asking. A session expires after an hour.
- Accounts are a whole feature: sign-up, passwords stored safely, sign-in, sign-out.

**Write (a), (b) or (c), and why, under `## M6-1` in `JOURNAL.md`, before you open the answer.**

<details><summary>Check your choice</summary>

(b). (a) hands every customer's orders to anyone who counts from 1: the M4-5 leak again, this time through your own API. (c) is the real answer for a real store, and it's a feature of its own, so it's an optional spec in your roadmap. (b) is honest about what the store knows: a session can see its own orders, and when the session expires, so does the view. The orders themselves stay, as you decided in M4.
</details>

## The idea

**`list_orders(token)`** checks the session, then reads that session's order ids, newest first (`ORDER BY id DESC`), and reads each one back with `read_order`, which you wrote in M5. It returns `list[Order]`. It's a customer's operation, so it reaches the outside three ways, as always, and your customer agent's settings must allow its tool. M5's check "every tool your store has is either allowed or denied" fails until they do.

**An example on a different table,** the library's loans:

```python
def list_loans(token: str | None) -> list[Loan]:
    """The card's loans, newest first, each as it was made."""
    require_card(token)
    with pool.connection() as conn:
        made = conn.execute("SELECT id FROM loans WHERE card_token = %s ORDER BY id DESC", (token,)).fetchall()
        return [read_loan(conn, row["id"]) for row in made]
```

```python
@app.get("/loans", response_model=list[Loan])
def get_loans(token: str | None = Depends(card_token)):
    try:
        return loans.list_loans(token)
    except cards.NoCard as e:
        raise no_card(e)
```

```python
@app.command("loans")
def loans_command(card: CardOption = None):
    """List a card's loans, newest first."""
    try:
        print_json(loans.list_loans(card))
    except cards.NoCard as e:
        fail(str(e), 5)
```

```python
@mcp.tool()
@agent_errors
def list_loans(card_token: str | None = None) -> list[Loan]:
    """List the loans this card has made, newest first. Use it to find out whether a borrow went through."""
    try:
        return loans.list_loans(card_token)
    except cards.NoCard as e:
        raise ToolError(str(e))
```

**The door for the browser.** A web page may only call the server it came from, unless that other server says otherwise. That rule is the browser's **same-origin policy**, and an origin is a scheme, a host and a port. Your pages will come from `http://localhost:3000`, and your API is at `http://localhost:8000`: a different port, so a different origin. Before a request that carries an `Authorization` header, the browser first asks the API, with an `OPTIONS` request called a **preflight**: may a page from this origin send this? **CORS** (cross-origin resource sharing) is how the API answers. FastAPI's `CORSMiddleware` does it. This is configuration with one right answer, so it's given. In `backend/main.py`, add the import at the top, and the rest straight after the line `app = FastAPI(...)`:

```python
from fastapi.middleware.cors import CORSMiddleware
```

```python
# Your frontend, at localhost:3000, may call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Only your own frontend's origin is allowed. A page from anywhere else gets no permission, so a stranger's site can't call your API from a visitor's browser.

## You write

- **`backend/orders.py`:** `list_orders(token: str | None) -> list[Order]`.
- **`backend/main.py`:** `GET /orders`, with your `session_token` dependency, and the CORS middleware above.
- **`backend/cli.py`:** `./store orders --session TOKEN`, a top-level command like `checkout`.
- **`backend/tools.py`:** the `list_orders` tool, taking `session_token`, wrapped with `@agent_errors`. Its description says what an agent can use it for: finding out whether a checkout went through.
- **`agents/customer/.claude/settings.json`:** allow `mcp__store__list_orders`.

## Check

Two orders, listed from the command line. Copy the whole block:

```
TOKEN=$(./store session start | python3 -c "import json, sys; print(json.load(sys.stdin)['token'])")
./store cart set 3 1 --session $TOKEN > /dev/null
./store checkout --session $TOKEN > /dev/null
./store cart set 4 2 --session $TOKEN > /dev/null
./store checkout --session $TOKEN > /dev/null
./store orders --session $TOKEN | python3 -c "import json, sys
for o in json.load(sys.stdin):
    print('order', o['id'], [(l['name'], l['quantity'], l['price_cents']) for l in o['items']], 'total', o['total_cents'])"
```

**You should see** two orders, the newest first:

```
order 2 [('Sleeping Bag 0 C', 2, 8900)] total 17800
order 1 [('Tarp 3 x 3 m', 1, 5900)] total 5900
```

A preflight, as a browser at `localhost:3000` sends it:

```
curl -s -o /dev/null -D - -X OPTIONS http://localhost:8000/cart -H 'Origin: http://localhost:3000' -H 'Access-Control-Request-Method: GET' -H 'Access-Control-Request-Headers: authorization' | grep -i -E '^HTTP|access-control-allow-origin'
```

**You should see** a `200` that names your frontend's origin:

```
HTTP/1.1 200 OK
access-control-allow-origin: http://localhost:3000
```

```
make check M=6 STEP=1
```

**You should see** everything before, then:

```
  PASS  M6-1  parity: list_orders has its route, its command and its tool
  PASS  M6-1  CORS: a page from http://localhost:3000 may call the API, and a page from anywhere else may not

116 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

## Step done

```
git status --short
```

```
 M JOURNAL.md
 M PREDICTIONS.md
 M agents/customer/.claude/settings.json
 M backend/cli.py
 M backend/main.py
 M backend/orders.py
 M backend/tools.py
```

```
git add -A
git commit -m "M6-1: your orders, and the door for the browser"
git push
```

Answer your tutor's questions under `## M6-1` in `JOURNAL.md`.

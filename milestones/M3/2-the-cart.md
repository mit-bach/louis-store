# Step M3-2 · The cart, and who's asking

**Why:** a session needs something to hold. This step builds the cart table, reads a cart back as lines with totals, and makes every way in say which session is asking, refusing clearly when it can't.

## Decide first: a product that's archived while it's in a cart

A visitor puts a tent in their cart on Monday. On Tuesday an admin archives the tent. On Wednesday the visitor looks at their cart. What should they see?
- **(a)** The line is gone, removed when the tent was archived.
- **(b)** The line is there, as it was, and counted in the total.
- **(c)** The line is there, marked as no longer available, and left out of the total.

The facts:
- A cart line points at a product by its `id`. Archived products stay in the table (M2), so the line still finds its product.
- The tent can't be bought any more. From M4 on, checkout will refuse it.
- A visitor, or an agent shopping for one, who finds a line gone without a word can't tell whether they removed it or the store did.
- An admin can unarchive a product with one `UPDATE`.

**Write (a), (b) or (c), and why, under `## M3-2` in `JOURNAL.md`, before you open the answer.**

<details><summary>Check your choice</summary>

(c). With (a), the cart changes behind the visitor's back, and an agent asked "is my tent still in the cart?" can only say no without knowing why. With (b), the total includes something that can't be sold, so the number on the cart is wrong. (c) keeps the line and tells the truth about it: `available: false`, and not in `total_cents`. The visitor, or their agent, can decide what to do, and if the tent comes back, the line is simply available again. The contract chose (c).
</details>

## The idea

**Foreign keys.** `product_id BIGINT NOT NULL REFERENCES products (id)` makes the database refuse a line for a product that doesn't exist. `REFERENCES sessions (token) ON DELETE CASCADE` does the same for sessions, and when a session is deleted, its lines go with it. Old sessions will be cleaned up one day, and their carts with them.

**A key made of two columns.** `PRIMARY KEY (session_token, product_id)` allows exactly one line per product per cart. A second line for the same product is refused, which the next step relies on.

**A join.** A cart line holds a product's `id` and a quantity. To show the product's name and price, the query **joins** the two tables:

```sql
SELECT …
FROM cart_items c
JOIN products p ON p.id = c.product_id
WHERE c.session_token = %s
```

`c` and `p` are short names for the tables. Each result row combines a cart line with its product, and the `SELECT` can compute too: `p.price_cents * c.quantity AS line_total_cents`, or `p.archived_at IS NULL AS available`, which is `true` or `false`.

**Who's asking, over HTTP.** The token arrives in a header, `Authorization: Bearer <token>`. Rather than read it in every cart route, you write it once, as a **dependency**: a function whose parameters FastAPI fills in from the request, and whose result it passes to the route. `Header(default=None)` reads a header; a parameter called `authorization` reads `Authorization`. A route asks for the result with `token: str | None = Depends(session_token)`. The dependency only *reads* the token. Checking it is `require_session`'s job, in the operation, so the command line and the tools get the same check.

A refusal answers `401 Unauthorized`, with the header `WWW-Authenticate: Bearer`, which tells a program how to authenticate. `HTTPException(…, headers={…})` sets it.

**An example on a different table,** the library's basket. Its table:

```sql
CREATE TABLE basket_items (
    card_token TEXT    NOT NULL REFERENCES cards (token) ON DELETE CASCADE,
    book_id    BIGINT  NOT NULL REFERENCES books (id),
    copies     INTEGER NOT NULL CHECK (copies > 0),
    PRIMARY KEY (card_token, book_id)
);
```

Its shapes:

```python
class BasketLine(BaseModel):
    book_id: int
    isbn: str
    title: str
    copies: int
    on_shelf: bool


class Basket(BaseModel):
    items: list[BasketLine]
```

Reading a basket:

```python
def get_basket(token: str | None) -> Basket:
    require_card(token)
    with pool.connection() as conn:
        rows = conn.execute(
            """
            SELECT b.id AS book_id, b.isbn, b.title, i.copies,
                   b.withdrawn_at IS NULL AS on_shelf
            FROM basket_items i
            JOIN books b ON b.id = i.book_id
            WHERE i.card_token = %s
            ORDER BY b.title
            """,
            (token,),
        ).fetchall()
    return Basket(items=[BasketLine(**row) for row in rows])
```

The dependency, the refusal, and the route:

```python
def card_token(authorization: str | None = Header(default=None)) -> str | None:
    """The token from an Authorization: Bearer header, or None."""
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip() or None
    return None


def no_card(e: cards.NoCard) -> HTTPException:
    return HTTPException(status_code=401, detail=str(e), headers={"WWW-Authenticate": "Bearer"})


@app.get("/basket", response_model=Basket)
def get_basket(token: str | None = Depends(card_token)):
    try:
        return basket.get_basket(token)
    except cards.NoCard as e:
        raise no_card(e)
```

And the command and the tool. The card arrives as an option, `--card`, and as an argument, `card_token`. When it's left out, it's `None`, and `require_card` refuses with its "no card" message:

```python
CardOption = Annotated[str | None, typer.Option("--card", help="The token from ./library card issue.")]


@basket_app.command("show")
def basket_show_command(card: CardOption = None):
    """Show a card's basket."""
    try:
        print_json(basket.get_basket(card))
    except cards.NoCard as e:
        fail(str(e), 5)
```

```python
@mcp.tool()
def get_basket(card_token: str | None = None) -> Basket:
    """Show the basket of the card whose token you pass. A book that's been withdrawn has on_shelf: false."""
    try:
        return basket.get_basket(card_token)
    except cards.NoCard as e:
        raise ToolError(str(e))
```

`CardOption = Annotated[…]` gives the option's type a name, so every basket command can reuse it. `typer.Option("--card", …)` names the option explicitly. The exit code for "no valid card" is 5.

## You write

- **`backend/migrations/004_create_cart_items.sql`,** as the contract describes `cart_items`. Apply it with `make migrate`.
- **`backend/schemas.py`:** `CartLine` and `Cart`.
- **`backend/cart.py`,** a new module: `get_cart(token)`, which checks the session first, then returns the cart. Lines are sorted by `product_id`, and `total_cents` counts only available lines.
- **`backend/main.py`:** the `session_token` dependency, and `GET /cart`, turning `NoSession` into a `401` with its message and the `WWW-Authenticate` header.
- **`backend/cli.py`:** the `cart` group, then `cart show --session TOKEN`, exiting `5` for `NoSession`. The group is given; add it under your `session` group:

  ```python
  cart_app = typer.Typer(help="A session's cart. Every command needs --session.", no_args_is_help=True)
  app.add_typer(cart_app, name="cart")
  ```

- **`backend/tools.py`:** the `get_cart` tool, taking `session_token`. Its docstring says what `available: false` means.

**Hint:** `sum(line.line_total_cents for line in lines if line.available)` adds up only the lines that count.

## Check

```
make migrate
```

```
applying backend/migrations/004_create_cart_items.sql
migrations up to date
```

No token, then a made-up one:

```
curl -s -w '\n%{http_code}\n' http://localhost:8000/cart
curl -s -w '\n%{http_code}\n' -H 'Authorization: Bearer made-up-token' http://localhost:8000/cart
```

```
{"detail":"No session token. Start a session, then send its token with every cart request."}
401
{"detail":"That session token doesn't exist. Start a new session."}
401
```

A real one, with an empty cart:

```
TOKEN=$(./store session start | python3 -c "import json, sys; print(json.load(sys.stdin)['token'])")
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/cart
```

```
{"items":[],"total_cents":0}
```

**Predict,** under `## M3-2` in `PREDICTIONS.md`: what does `./store cart show` print, and with what exit code, when the session has expired? Then make one expire, by setting its `expires_at` in the past by hand, and ask:

```
docker compose exec db psql -U store -d store -c "UPDATE sessions SET expires_at = now() - interval '1 minute' WHERE token = '$TOKEN';"
./store cart show --session $TOKEN; echo "exit code $?"
```

<details><summary>What mine showed</summary>

```
UPDATE 1
That session has expired. Start a new session.
exit code 5
```
</details>

```
make check M=3 STEP=2
```

**You should see** everything before, then:

```
  PASS  M3-2  the cart_items table: one line per session and product, a quantity above zero, and lines that go with their session
  PASS  M3-2  get_cart() joins each line to its product, totals it, and leaves archived products out of the total
  PASS  M3-2  GET /cart: 200 with a live token; 401 with the contract's message without one, or with a bad or expired one
  PASS  M3-2  ./store cart show and the get_cart tool: the cart with a live token, the same three messages without one

80 passed, 0 failed, 0 skipped.
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
 M backend/schemas.py
 M backend/tools.py
?? backend/cart.py
?? backend/migrations/004_create_cart_items.sql
```

```
git add -A
git commit -m "M3-2: the cart, and who's asking"
git push
```

Answer your tutor's questions under `## M3-2` in `JOURNAL.md`.

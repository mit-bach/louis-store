# Step M3-3 · Filling the cart

**Why:** a cart that can only be read is no use. This step puts products in, changes how many, and takes them out, through all three ways in.

## Decide first: does putting something in the cart check the stock?

A visitor asks for 5 of a tent that has 3 in stock. The store could:
- **(a)** refuse now, with a clear message;
- **(b)** accept it, and let checkout (in M4) refuse it later.

The facts:
- A cart reserves nothing. Another customer can buy the last unit while it sits in your cart, so checkout must check the stock again, whatever happens now.
- An agent filling a cart for someone reads every answer. "Only 3 in stock" now lets it ask the customer what to do while they're still choosing.
- Checking now costs one read of the product, which the operation does anyway, to find its name and price.

**Write (a) or (b), and why, under `## M3-3` in `JOURNAL.md`, before you open the answer.**

<details><summary>Check your choice</summary>

(a), refuse now, but don't mistake it for a guarantee. It's a courtesy to whoever is shopping: they learn early, while they can still choose something else. It promises nothing about checkout, because the stock can change in the meantime. That's why M4's checkout locks the rows and checks again. The contract chose (a): `409`, `Only 3 of Solo Tent in stock, so a cart can't hold 5.`
</details>

## The idea

**Set, don't add.** `PUT /cart/items/3` with `{"quantity": 2}` means "the cart holds 2 of product 3", whether it held none or 7 before. Sending it twice leaves 2, not 4, so it's safe to repeat. That's why it's a `PUT`: it replaces the whole line, which is exactly one number.

**An upsert.** One statement inserts the line, or, if the key `(session_token, product_id)` is already there, updates it instead:

```sql
INSERT INTO cart_items (session_token, product_id, quantity)
VALUES (%s, %s, %s)
ON CONFLICT (session_token, product_id) DO UPDATE SET quantity = EXCLUDED.quantity
```

`EXCLUDED` is the row the `INSERT` tried to add. "Update or insert" gives the word **upsert**. It's one statement, so two requests can't both see "no line yet" and both insert.

**Before the upsert,** the operation checks the session, finds the product (`get_product` raises `ProductNotFound` when it's missing), refuses an archived one, and refuses more than is in stock.

**Quantity 1 or more,** in three places:
- the body model `CartQuantity`, so HTTP answers `422`;
- the command, which builds a `CartQuantity` and exits `2`;
- the tool's signature, `quantity: Annotated[int, Field(ge=1, …)]`, so the rule is in the tool's schema, where the agent reads it before it calls. `Field` comes from `pydantic`, and `Annotated` from `typing`.

The table's `CHECK (quantity > 0)` stands behind all three.

**An example on a different table,** the library's basket:

```python
def set_basket_item(token: str | None, book_id: int, copies: int) -> Basket:
    require_card(token)
    book = books.get_book(book_id)
    if book.withdrawn_at is not None:
        raise books.BookNotFound(f"Book {book_id} has been withdrawn.")
    if copies > book.copies:
        raise books.NotEnoughCopies(f"The library owns {book.copies} of {book.title}, so a basket can't hold {copies}.")
    with pool.connection() as conn:
        conn.execute(
            """
            INSERT INTO basket_items (card_token, book_id, copies)
            VALUES (%s, %s, %s)
            ON CONFLICT (card_token, book_id) DO UPDATE SET copies = EXCLUDED.copies
            """,
            (token, book_id, copies),
        )
    return get_basket(token)
```

```python
class BasketCopies(BaseModel):
    copies: int = Field(ge=1, description="How many copies the basket should hold.")
```

```python
@app.put("/basket/items/{book_id}", response_model=Basket)
def put_basket_item(book_id: int, body: BasketCopies, token: str | None = Depends(card_token)):
    try:
        return basket.set_basket_item(token, book_id, body.copies)
    except cards.NoCard as e:
        raise no_card(e)
    except books.BookNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except books.NotEnoughCopies as e:
        raise HTTPException(status_code=409, detail=str(e))
```

```python
@basket_app.command("set")
def basket_set_command(book_id: int, copies: int, card: CardOption = None):
    """Put a book in the basket, or change how many copies: the basket holds exactly COPIES."""
    try:
        checked = BasketCopies(copies=copies)
    except ValidationError as e:
        fail(str(e), 2)
    try:
        print_json(basket.set_basket_item(card, book_id, checked.copies))
    except cards.NoCard as e:
        fail(str(e), 5)
    except books.BookNotFound as e:
        fail(str(e), 3)
    except books.NotEnoughCopies as e:
        fail(str(e), 4)
```

```python
@mcp.tool()
def set_basket_item(
    book_id: int,
    copies: Annotated[int, Field(ge=1, description="How many copies the basket should hold, not how many to add.")],
    card_token: str | None = None,
) -> Basket:
    """Put a book in the card's basket, or change how many copies: the basket then holds exactly copies."""
    try:
        return basket.set_basket_item(card_token, book_id, copies)
    except (cards.NoCard, books.BookNotFound, books.NotEnoughCopies) as e:
        raise ToolError(str(e))
```

`books.BookNotFound(f"Book {book_id} has been withdrawn.")` reuses the not-found error with its own message, so every way in already knows what to do with it.

## You write

- **`backend/schemas.py`:** `CartQuantity`.
- **`backend/cart.py`:** `set_cart_item(token, product_id, quantity)` and `remove_cart_item(token, product_id)`, as the contract describes them, with its messages exactly. Each returns the cart, through `get_cart`.
- **`backend/main.py`:** `PUT /cart/items/{product_id}`, with a `CartQuantity` body, and `DELETE /cart/items/{product_id}`.
- **`backend/cli.py`:** `cart set PRODUCT_ID QUANTITY --session TOKEN` and `cart remove PRODUCT_ID --session TOKEN`.
- **`backend/tools.py`:** `set_cart_item` and `remove_cart_item`, each taking `session_token`. The quantity's description says it's how many the cart should hold, not how many to add.

**Hint:** `remove_cart_item` is a `DELETE` that may match no row. That's fine: removing what isn't there changes nothing, and returns the cart.

## Check

Start a session, and put 2 of product 3 in its cart:

```
TOKEN=$(./store session start | python3 -c "import json, sys; print(json.load(sys.stdin)['token'])")
./store cart set 3 2 --session $TOKEN
```

```
{
  "items": [
    {
      "product_id": 3,
      "sku": "TARP-3X3",
      "name": "Tarp 3 x 3 m",
      "price_cents": 5900,
      "quantity": 2,
      "line_total_cents": 11800,
      "available": true
    }
  ],
  "total_cents": 11800
}
```

**Predict,** under `## M3-3` in `PREDICTIONS.md`: you now set product 3 again, to 1. What will the cart hold: one line of 1, one line of 3, or two lines? Then run it:

```
./store cart set 3 1 --session $TOKEN
```

<details><summary>What mine showed</summary>

```
{
  "items": [
    {
      "product_id": 3,
      "sku": "TARP-3X3",
      "name": "Tarp 3 x 3 m",
      "price_cents": 5900,
      "quantity": 1,
      "line_total_cents": 5900,
      "available": true
    }
  ],
  "total_cents": 5900
}
```

One line, now holding 1. It replaced the quantity; it didn't add a line.
</details>

More than is in stock, and an archived product (mine is 9, archived in M2):

```
./store cart set 3 50 --session $TOKEN; echo "exit code $?"
./store cart set 9 1 --session $TOKEN; echo "exit code $?"
```

```
Only 12 of Tarp 3 x 3 m in stock, so a cart can't hold 50.
exit code 4
Product 9 isn't for sale.
exit code 3
```

And out again:

```
./store cart remove 3 --session $TOKEN
```

```
{
  "items": [],
  "total_cents": 0
}
```

```
make check M=3 STEP=3
```

**You should see** everything before, then:

```
  PASS  M3-3  set_cart_item() sets a line's quantity, replaces it the second time, and refuses what can't be sold
  PASS  M3-3  PUT and DELETE /cart/items/{id}: the cart back, 422 for quantity 0, 409, 404 and 401 with their messages
  PASS  M3-3  ./store cart set and remove, and the set_cart_item and remove_cart_item tools: the same results and errors
  PASS  M3-3  parity: the session and cart operations each have a route, a command and a tool

84 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

## Step done

```
git status --short
```

```
 M JOURNAL.md
 M PREDICTIONS.md
 M backend/cart.py
 M backend/cli.py
 M backend/main.py
 M backend/schemas.py
 M backend/tools.py
```

```
git add -A
git commit -m "M3-3: filling the cart"
git push
```

Answer your tutor's questions under `## M3-3` in `JOURNAL.md`.

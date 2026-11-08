# Step M2-4 · Adjusting stock

**Why:** stock moves all day: a delivery adds units, a breakage removes them, and from M4 on, every order removes some. It's the number this whole course is about, because it's the one two people change at the same moment.

## Decide first: read, then write? Or one statement?

There are two ways to add `change` to a product's stock:
- **(a) Read, then write.** `get_product` reads the stock, Python works out `stock + change`, checks that it isn't negative, and an `UPDATE` stores the new number.
- **(b) One statement.** `UPDATE products SET stock = stock + %s WHERE id = %s`, and the table's `CHECK (stock >= 0)` refuses a result below zero.

The facts:
- Two admins add a delivery of 1 unit each to a product with 10 in stock, at the same moment.
- With (a), each reads 10 before either writes. Each works out 11, and each stores 11.
- With (b), Postgres works out `stock + 1` inside the `UPDATE`. While one `UPDATE` changes a row, the row is **locked**: a second `UPDATE` of the same row waits until the first is committed, then reads the new value.

**Write (a) or (b), and why, under `## M2-4` in `JOURNAL.md`, before you open the answer.**

<details><summary>Check your choice</summary>

(b). With (a), two deliveries of 1 unit leave the stock at 11, not 12: one delivery vanishes, and both callers were told it worked. That's a **lost update**, and nothing reports it. With (b), the second `UPDATE` waits for the first, then adds to 11. The `CHECK` refuses a stock below zero as part of the same statement, so nothing can slip between the check and the write either. Step 5 shows (a) losing updates for real.
</details>

## The idea

**Arithmetic in SQL.** `SET stock = stock + %s` uses the row's own current value. `%s` is the change, and it may be negative.

**When the `CHECK` refuses.** If the result would be below zero, Postgres refuses the whole `UPDATE` and nothing changes. psycopg raises `errors.CheckViolation`. You catch it and raise your own error, `InsufficientStock`, with a message that says how many are left. The `UPDATE` was refused, so the number comes from a fresh read: `get_product` again.

**A body with one field.** The route takes `{"change": -3}`. A small Pydantic model, `StockChange`, describes it, so FastAPI checks that `change` is a whole number.

**An example on a different table,** the library changing how many copies it owns:

```python
def change_copies(book_id: int, change: int) -> Book:
    try:
        with pool.connection() as conn:
            row = conn.execute(
                "UPDATE books SET copies = copies + %s WHERE id = %s RETURNING *",
                (change, book_id),
            ).fetchone()
    except errors.CheckViolation:
        book = get_book(book_id)
        raise NotEnoughCopies(f"The library owns {book.copies} of {book.title}, so it can't lose {-change}.")
    if row is None:
        raise BookNotFound(f"No book with id {book_id}.")
    return Book(**row)
```

```python
class CopiesChange(BaseModel):
    change: int = Field(description="Copies bought, or a negative number for copies lost.")
```

```python
@app.post("/books/{book_id}/copies", response_model=Book)
def post_copies(book_id: int, body: CopiesChange):
    try:
        return books.change_copies(book_id, body.change)
    except books.BookNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except books.NotEnoughCopies as e:
        raise HTTPException(status_code=409, detail=str(e))
```

```python
@books_app.command("change-copies")
def change_copies_command(
    book_id: int,
    change: Annotated[int, typer.Option(help="Copies bought, or a negative number for copies lost.")],
):
    """Change how many copies of a book the library owns."""
    try:
        print_json(books.change_copies(book_id, change))
    except books.BookNotFound as e:
        fail(str(e), 3)
    except books.NotEnoughCopies as e:
        fail(str(e), 4)
```

```python
@mcp.tool()
def change_copies(book_id: int, change: int) -> Book:
    """Change how many copies the library owns: positive for copies bought, negative for copies lost."""
    try:
        return books.change_copies(book_id, change)
    except (books.BookNotFound, books.NotEnoughCopies) as e:
        raise ToolError(str(e))
```

`{-change}` turns the change around for the message: a change of `-10` "can't lose 10".

## You write

- **`backend/products.py`:** `class InsufficientStock(Exception):`, and `adjust_stock(product_id: int, change: int) -> Product`, in one statement, with `updated_at = now()`. It raises `ProductNotFound` for a missing id, and `InsufficientStock` with exactly the message `Only 2 of Two-Person Tent in stock, so 5 can't be removed.`, filled in, when the stock would go below zero.
- **`backend/schemas.py`:** `StockChange`, with a `description` on `change` that says a negative number removes units.
- **`backend/main.py`:** `POST /products/{product_id}/stock`, with a `StockChange` body: `200`, `404` or `409`.
- **`backend/cli.py`:** `products adjust-stock PRODUCT_ID --change N`, exiting `3` or `4`.
- **`backend/tools.py`:** the `adjust_stock` tool, taking `product_id` and `change`, whose docstring says which way a negative change goes, and that stock can't go below zero.

**Hint:** the only `CHECK` this `UPDATE` can break is the stock's. Your price's `CHECK` isn't touched by `SET stock = …`.

## Check

Five units in:

```
curl -s -w '\n%{http_code}\n' -X POST http://localhost:8000/products/2/stock -H 'Content-Type: application/json' -d '{"change": 5}'
```

```
{"sku":"TENT-1P","name":"Solo Tent","description":"Single-wall, 1.1 kg.","category":"shelter","image_url":null,"price_cents":18900,"stock":8,"id":2,"created_at":"2026-11-08T17:44:55.621612Z","updated_at":"2026-11-08T17:46:26.173472Z","archived_at":null}
200
```

More out than there is:

```
curl -s -w '\n%{http_code}\n' -X POST http://localhost:8000/products/2/stock -H 'Content-Type: application/json' -d '{"change": -100}'
```

```
{"detail":"Only 8 of Solo Tent in stock, so 100 can't be removed."}
409
```

The same, from the command line:

```
./store products adjust-stock 2 --change -3 | grep '"stock"'
./store products adjust-stock 2 --change -100; echo "exit code $?"
```

```
  "stock": 5,
Only 5 of Solo Tent in stock, so 100 can't be removed.
exit code 4
```

```
make check M=2 STEP=4
```

**You should see** everything before, then:

```
  PASS  M2-4  adjust_stock() adds and removes in one statement, and refuses to go below zero with the contract's message
  PASS  M2-4  POST /products/{id}/stock: 200 with the new stock, 409 when there isn't enough, 404 for a missing id
  PASS  M2-4  ./store products adjust-stock and the adjust_stock tool: the same results, exit codes and messages
  PASS  M2-4  parity: the new operations each have a route, a command and a tool

65 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

The last check is parity: every new route has its command and its tool.

## Step done

```
git status --short
```

```
 M JOURNAL.md
 M PREDICTIONS.md
 M backend/cli.py
 M backend/main.py
 M backend/products.py
 M backend/schemas.py
 M backend/tools.py
```

```
git add -A
git commit -m "M2-4: adjust stock"
git push
```

Commit before step 5: you'll break this file on purpose there, and put it back with git. Answer your tutor's questions under `## M2-4` in `JOURNAL.md`.

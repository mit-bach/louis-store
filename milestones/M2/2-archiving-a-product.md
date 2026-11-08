# Step M2-2 · Archiving a product

**Why:** the column is there; now an admin, a script or an agent needs a way to set it. It's your first operation that changes an existing row, and the first one where it matters what happens when it's done twice.

## The idea

**An `UPDATE` that hands back what it changed.** `UPDATE table SET column = value WHERE … RETURNING *` changes the rows that match, and returns them, as `INSERT … RETURNING *` did in M1. If no row matches, it changes nothing and returns nothing: `.fetchone()` gives `None`.

**Safe to repeat.** Agents retry. A network hiccup, a timeout, or a model that isn't sure its first call worked, and the same request arrives twice. Archiving twice must not move `archived_at` to the second moment, because that would rewrite when the product really came off sale. So the operation only archives a product that isn't archived yet:

```sql
UPDATE products SET archived_at = now(), updated_at = now()
WHERE id = %s AND archived_at IS NULL
RETURNING *
```

Then "no row came back" means one of two things: there's no such product, or it was already archived. `get_product` tells them apart. It returns the product as it is, or raises `ProductNotFound`. An operation that gives the same result however many times it's called is called **idempotent**. You'll meet the word again in M5.

**An example on a different table,** the library withdrawing a book, through all three ways in:

```python
def withdraw_book(book_id: int) -> Book:
    with pool.connection() as conn:
        row = conn.execute(
            "UPDATE books SET withdrawn_at = now() WHERE id = %s AND withdrawn_at IS NULL RETURNING *",
            (book_id,),
        ).fetchone()
    if row is None:
        return get_book(book_id)
    return Book(**row)
```

```python
@app.post("/books/{book_id}/withdraw", response_model=Book)
def withdraw(book_id: int):
    try:
        return books.withdraw_book(book_id)
    except books.BookNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
```

```python
@books_app.command("withdraw")
def withdraw_command(book_id: int):
    """Take a book off the shelves. Its loans keep pointing at it."""
    try:
        print_json(books.withdraw_book(book_id))
    except books.BookNotFound as e:
        fail(str(e), 3)
```

```python
@mcp.tool()
def withdraw_book(book_id: int) -> Book:
    """Take a book off the shelves. It stays in the catalogue, so its loans still work.
    Withdrawing a book that's already withdrawn changes nothing."""
    try:
        return books.withdraw_book(book_id)
    except books.BookNotFound as e:
        raise ToolError(str(e))
```

The route is a `POST` to `/books/{book_id}/withdraw`. It isn't a `DELETE`, because nothing is deleted: the request asks for an action, and the address names it.

## You write

- **`backend/products.py`:** `archive_product(product_id: int) -> Product`, which archives the product as above, sets `updated_at` too, and returns it. If it's already archived, it returns it unchanged. If there's no such product, it raises `ProductNotFound`.
- **`backend/main.py`:** `POST /products/{product_id}/archive`, answering `200` with the product, or `404`.
- **`backend/cli.py`:** `products archive PRODUCT_ID`, exiting with `3` for a missing id. Its docstring says what archiving means, because that's what `--help` shows.
- **`backend/tools.py`:** the `archive_product` tool, with a docstring that says archiving twice changes nothing. An agent that knows a call is safe to repeat can retry it without worrying.

**Hint:** when the `UPDATE` returns nothing, `return get_product(product_id)`. That one line covers both cases.

## Check

Archive a product (mine is 9, the water filter that's out of stock):

```
curl -s -w '\n%{http_code}\n' -X POST http://localhost:8000/products/9/archive
```

```
{"sku":"FILTER-SQ","name":"Squeeze Water Filter","description":"Filters 0.1 micron.","category":"water","image_url":null,"price_cents":3200,"stock":0,"id":9,"created_at":"2026-11-08T18:20:08.767230Z","updated_at":"2026-11-08T18:20:37.443632Z","archived_at":"2026-11-08T18:20:37.443632Z"}
200
```

**Predict,** under `## M2-2` in `PREDICTIONS.md`: what happens when you send the same request again? Will `archived_at` change? Then send it, and compare the two answers.

<details><summary>What mine answered the second time</summary>

```
{"sku":"FILTER-SQ","name":"Squeeze Water Filter","description":"Filters 0.1 micron.","category":"water","image_url":null,"price_cents":3200,"stock":0,"id":9,"created_at":"2026-11-08T18:20:08.767230Z","updated_at":"2026-11-08T18:20:37.443632Z","archived_at":"2026-11-08T18:20:37.443632Z"}
200
```

The same answer, `archived_at` and `updated_at` included. The second request changed nothing.
</details>

A product that isn't there:

```
./store products archive 999999; echo "exit code $?"
```

```
No product with id 999999.
exit code 3
```

```
make check M=2 STEP=2
```

**You should see** everything before, then:

```
  PASS  M2-2  archive_product() sets archived_at; archiving again changes nothing; a missing id raises ProductNotFound
  PASS  M2-2  POST /products/{id}/archive answers 200 with the product; it stays reachable by id, and leaves the list
  PASS  M2-2  ./store products archive and the archive_product tool archive, and say why when the id is missing

57 passed, 0 failed, 0 skipped.
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
 M backend/products.py
 M backend/tools.py
```

```
git add -A
git commit -m "M2-2: archive a product"
git push
```

Answer your tutor's questions under `## M2-2` in `JOURNAL.md`.

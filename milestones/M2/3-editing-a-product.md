# Step M2-3 · Editing a product

**Why:** prices change, names get typos, descriptions get written. An admin, or an agent acting for one, needs to change a product's details without touching anything else.

## Decide first: PUT or PATCH?

HTTP has two ways to change something:
- **`PUT`** replaces it whole. The caller sends every field, and whatever it sends is what's stored.
- **`PATCH`** changes part of it. The caller sends only the fields that change, and the rest stay as they are.

The facts:
- An agent asked to "make the tent 10% cheaper" knows the price. With `PUT`, it must also send the name, the SKU, the description and everything else, exactly as they are now.
- Two admins edit the same product at once: one fixes the name, the other the price. With `PUT`, each sends every field as it was when they loaded it.
- With `PATCH`, the server has to tell "left out" apart from "set to this".

**Write `PUT` or `PATCH`, and why, under `## M2-3` in `JOURNAL.md`, before you open the answer.**

<details><summary>Check your choice</summary>

`PATCH`. With `PUT`, the second admin's request carries the old name, and silently undoes the first admin's fix. It's the same lost update you'll race against in step 5, through a different door. An agent that has to resend every field can get one wrong without meaning to. With `PATCH`, each caller sends only what it means to change. Telling "left out" from "set" is a few lines of code, below.
</details>

**One field is missing on purpose.** `ProductUpdate` in [`CONTRACT.md`](../../CONTRACT.md) has no `stock`, and it refuses any field it doesn't know. Stock changes by adding or removing units, in step 4, because "set the stock to 12" is a number someone read earlier, and may be out of date by the time it's written. And a field the store ignored in silence would let an agent tell its user "done" when nothing changed. So it's refused, loudly.

## The idea

**A model whose fields are all optional, and never null.** Each field gets a default of `None`, but keeps a type that doesn't allow `None`:

```python
title: str = Field(default=None, min_length=1)
```

Pydantic doesn't check defaults. So when `title` is left out, it's `None`, quietly. When a caller sends `"title": null`, it's checked against `str`, and refused. That's exactly what the contract asks for.

**Refusing unknown fields.** `model_config = ConfigDict(extra="forbid")` inside the class makes Pydantic refuse any field that isn't declared, instead of ignoring it. `ConfigDict` comes from `pydantic`.

**What was given.** `changes.model_dump(exclude_unset=True)` returns a dictionary of only the fields the caller actually sent. Those are the columns to change.

**SQL for columns you only know at run time.** You can't write `%s` for a column's name: `%s` is only for values. And you must never paste a name into SQL with an f-string. psycopg's `sql` module (`from psycopg import sql`) builds SQL from safe parts:
- `sql.Identifier(name)` is a column's name, quoted safely;
- `sql.Placeholder()` is a `%s` for a value;
- `sql.SQL("{} = {}").format(a, b)` fills those into a piece of SQL;
- `sql.SQL(", ").join(parts)` joins pieces with commas.

**An example on a different table,** the library's book edits:

```python
class BookUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    isbn: str = Field(default=None, min_length=1)
    title: str = Field(default=None, min_length=1)
    subtitle: str = Field(default=None, min_length=1)
```

```python
def update_book(book_id: int, changes: BookUpdate) -> Book:
    fields = changes.model_dump(exclude_unset=True)
    if not fields:
        return get_book(book_id)
    assignments = sql.SQL(", ").join(
        sql.SQL("{} = {}").format(sql.Identifier(name), sql.Placeholder()) for name in fields
    )
    query = sql.SQL("UPDATE books SET {} WHERE id = {} RETURNING *").format(assignments, sql.Placeholder())
    try:
        with pool.connection() as conn:
            row = conn.execute(query, [*fields.values(), book_id]).fetchone()
    except errors.UniqueViolation:
        raise DuplicateIsbn(f"A book with the ISBN {fields['isbn']} is already in the library.")
    if row is None:
        raise BookNotFound(f"No book with id {book_id}.")
    return Book(**row)
```

`[*fields.values(), book_id]` is one list: the new values in the same order as the columns, then the id for the `WHERE`. And its route, command and tool:

```python
@app.patch("/books/{book_id}", response_model=Book)
def patch_book(book_id: int, changes: BookUpdate):
    try:
        return books.update_book(book_id, changes)
    except books.BookNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except books.DuplicateIsbn as e:
        raise HTTPException(status_code=409, detail=str(e))
```

```python
@books_app.command("update")
def update_command(
    book_id: int,
    isbn: Annotated[str | None, typer.Option()] = None,
    title: Annotated[str | None, typer.Option()] = None,
    subtitle: Annotated[str | None, typer.Option()] = None,
):
    """Change some of a book's details. Only the options you give change."""
    given = dict(isbn=isbn, title=title, subtitle=subtitle)
    try:
        changes = BookUpdate(**{field: value for field, value in given.items() if value is not None})
    except ValidationError as e:
        fail(str(e), 2)
    try:
        print_json(books.update_book(book_id, changes))
    except books.BookNotFound as e:
        fail(str(e), 3)
    except books.DuplicateIsbn as e:
        fail(str(e), 4)
```

```python
@mcp.tool()
def update_book(book_id: int, changes: BookUpdate) -> Book:
    """Change some of a book's details: only the fields in changes."""
    try:
        return books.update_book(book_id, changes)
    except (books.BookNotFound, books.DuplicateIsbn) as e:
        raise ToolError(str(e))
```

The command passes on only the options that were given: an option left out is `None`, and `if value is not None` drops it. `except (A, B) as e:` catches either error.

## You write

- **`backend/schemas.py`:** `ProductUpdate`, as the contract describes it.
- **`backend/products.py`:** `update_product(product_id: int, changes: ProductUpdate) -> Product`. It changes only the fields given, and sets `updated_at = now()` in the same `UPDATE`. With no fields, it returns the product unchanged. It raises `ProductNotFound` for a missing id, and `DuplicateSku` for a SKU that's taken, with M1's message.
- **`backend/main.py`:** `PATCH /products/{product_id}`.
- **`backend/cli.py`:** `products update PRODUCT_ID`, with an option for each field of `ProductUpdate`.
- **`backend/tools.py`:** the `update_product` tool, whose docstring says stock isn't changed here, and names the tool that changes it.

**Hint:** the duplicate-SKU message needs the new SKU, which is `fields["sku"]`. It's only there when the caller changed it, and only then can the SKU be taken.

## Check

A new price, and nothing else changed:

```
curl -s -w '\n%{http_code}\n' -X PATCH http://localhost:8000/products/1 -H 'Content-Type: application/json' -d '{"price_cents": 22900}'
```

```
{"sku":"TENT-2P","name":"Two-Person Tent","description":"Freestanding, 2.1 kg, two doors.","category":"shelter","image_url":null,"price_cents":22900,"stock":5,"id":1,"created_at":"2026-11-08T17:44:55.621612Z","updated_at":"2026-11-08T17:45:58.150533Z","archived_at":null}
200
```

A null name:

```
curl -s -w '\n%{http_code}\n' -X PATCH http://localhost:8000/products/1 -H 'Content-Type: application/json' -d '{"name": null}'
```

```
{"detail":[{"type":"string_type","loc":["body","name"],"msg":"Input should be a valid string","input":null}]}
422
```

**Predict,** under `## M2-3` in `PREDICTIONS.md`: what happens when you send `{"stock": 50}`? Then send it:

```
curl -s -w '\n%{http_code}\n' -X PATCH http://localhost:8000/products/1 -H 'Content-Type: application/json' -d '{"stock": 50}'
```

<details><summary>What mine answered</summary>

```
{"detail":[{"type":"extra_forbidden","loc":["body","stock"],"msg":"Extra inputs are not permitted","input":50}]}
422
```

Refused, and the message names the field.
</details>

From the command line, the four lines that matter:

```
./store products update 1 --name 'Two-Person Tent, green' | grep -E '"(name|price_cents|stock|updated_at)"'
```

```
  "name": "Two-Person Tent, green",
  "price_cents": 22900,
  "stock": 5,
  "updated_at": "2026-11-08T17:45:59.456546Z",
```

```
make check M=2 STEP=3
```

**You should see** everything before, then:

```
  PASS  M2-3  ProductUpdate: every field optional; it refuses null, an empty name, a negative price, and stock
  PASS  M2-3  update_product() changes only what it's given, moves updated_at, and names a taken SKU
  PASS  M2-3  PATCH /products/{id}: 200 with the change, 422 for null or stock, 409 for a taken SKU, 404 for a missing id
  PASS  M2-3  ./store products update and the update_product tool change what they're given, and fail the same way

61 passed, 0 failed, 0 skipped.
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
 M backend/schemas.py
 M backend/tools.py
```

```
git add -A
git commit -m "M2-3: edit a product"
git push
```

Answer your tutor's questions under `## M2-3` in `JOURNAL.md`.

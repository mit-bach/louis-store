# Step M1-4 · Creating a product

**Why:** an admin, a script or an agent has to be able to add products. Creating is the first operation that writes, and the first one where two callers at the same moment can get in each other's way.

## Decide first: how do you stop a duplicate SKU?

Your table refuses a second product with the same SKU. Your code still has to decide how to deal with one. There are two ways:
- **(a) Look first.** Run a `SELECT` to see whether the SKU exists, and run the `INSERT` only if it doesn't.
- **(b) Just insert.** Run the `INSERT`, and if the database refuses it because of the `UNIQUE` rule, turn that refusal into your own error.

The facts:
- Two callers, say an admin and an agent, can save a product with the same SKU in the same instant.
- Between caller A's `SELECT` and its `INSERT`, caller B can run its own `SELECT`, find no such SKU, and go on to insert.
- The database checks `UNIQUE` at the instant of each insert, one insert at a time, and refuses whichever comes second.

**Write (a) or (b), and why, in `JOURNAL.md` under `## M1-4`, before you open the answer.**

<details><summary>Check your choice</summary>

(b). With (a), two saves in the same instant can both pass their `SELECT`, because neither has inserted yet, and then both insert. The table's `UNIQUE` rule would still stop the second one, but your code wouldn't be expecting it: the caller would get a crash instead of a clear "already exists". Only the database sees every insert in order, so only its check is safe. Your code's job is to turn its refusal into a clear message.

This "look, then act" gap is called a **race**. It comes back in M2, when two admins change the stock at once, and in M4, when two customers buy the last unit.
</details>

## The idea

Creating a product takes three new pieces:
1. **`INSERT … RETURNING *`.** The insert names its columns, and gives one `%s` for each, with the values passed separately in the same order. `RETURNING *` hands back the row just inserted, with the `id` and times the database filled in. Read it with `.fetchone()`.
2. **The transaction.** `with pool.connection() as conn:` is one **transaction**: when the indented lines finish, everything they wrote is saved (**committed**). If an error is raised inside, everything they wrote is undone (**rolled back**). So an insert that's refused leaves nothing half-done.
3. **Catching the database's refusal.** When `UNIQUE` refuses an insert, psycopg raises `errors.UniqueViolation` (after `from psycopg import errors`). Put the database work inside `try:`, and in `except errors.UniqueViolation:` raise your own named error instead.

SQL that's longer than one line goes in triple quotes, `"""…"""`.

**An example on a different table,** the library's books, with its two named errors:

```python
from psycopg import errors

from db import pool
from schemas import Book, BookCreate


class BookNotFound(Exception):
    """Raised when no book has this id."""


class DuplicateIsbn(Exception):
    """Raised when another book already has this ISBN."""


def list_books() -> list[Book]:
    with pool.connection() as conn:
        rows = conn.execute("SELECT * FROM books ORDER BY title").fetchall()
    return [Book(**row) for row in rows]


def get_book(book_id: int) -> Book:
    with pool.connection() as conn:
        row = conn.execute("SELECT * FROM books WHERE id = %s", (book_id,)).fetchone()
    if row is None:
        raise BookNotFound(f"No book with id {book_id}.")
    return Book(**row)


def add_book(data: BookCreate) -> Book:
    try:
        with pool.connection() as conn:
            row = conn.execute(
                """
                INSERT INTO books (isbn, title, subtitle, copies)
                VALUES (%s, %s, %s, %s)
                RETURNING *
                """,
                (data.isbn, data.title, data.subtitle, data.copies),
            ).fetchone()
    except errors.UniqueViolation:
        raise DuplicateIsbn(f"A book with the ISBN {data.isbn} is already in the library.")
    return Book(**row)
```

## You write, in `backend/products.py`

- `from psycopg import errors` at the top, and `ProductCreate` added to your import from `schemas`.
- `class DuplicateSku(Exception):`, with a one-line docstring.
- `create_product(data: ProductCreate) -> Product`, which:
  - inserts all seven fields of `data`: `sku`, `name`, `description`, `category`, `image_url`, `price_cents` and `stock`, in one order, with the values in the same order;
  - returns the inserted row as a `Product`;
  - raises `DuplicateSku` with exactly the message `A product with the SKU TENT-2P already exists.`, with the SKU filled in, when the database refuses the insert because the SKU is taken.

**Hint:** the `try:` goes around the whole `with` block, not inside it. That way the connection is back in the pool, and its transaction rolled back, by the time you raise your own error.

## Check

```
docker compose exec -T api python - <<'EOF'
import products
from db import pool
from schemas import ProductCreate

lamp = ProductCreate(sku="TEST-LAMP", name="Hiker's lamp", category="lighting", price_cents=2450)
made = products.create_product(lamp)
print("created:", made.id, made.name, made.stock, made.description)
try:
    products.create_product(lamp)
except products.DuplicateSku as e:
    print("second try:", e)
pool.close()
EOF
```

**You should see** the new product's id, name, stock and description, then the second try refused:

```
created: 11 Hiker's lamp 0 None
second try: A product with the SKU TEST-LAMP already exists.
```

Your id will be one more than your number of products. The name has an apostrophe on purpose: if your SQL pasted the name in instead of passing it with `%s`, this would fail with a syntax error. `TEST-LAMP` stays in your table until your next `make reset`.

Then:

```
make check M=1 STEP=4
```

**You should see** everything before, then:

```
  PASS  M1-4  ProductCreate refuses a negative price or stock, an empty name, SKU or description, and no category
  PASS  M1-4  ProductCreate's defaults: no description, no image, stock 0
  PASS  M1-4  create_product() saves the product and returns it with its id and times
  PASS  M1-4  create_product() with a SKU that exists raises DuplicateSku with the contract's message

28 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

## Step done

Look at what git sees:

```
git status --short
```

**You should see** this. `M` means changed, and `??` new. Your journal and predictions are listed because you wrote in them:

```
 M JOURNAL.md
 M PREDICTIONS.md
 M backend/products.py
```

Then commit and push:

```
git add -A
git commit -m "M1-4: create a product"
git push
```

Your journal has your (a) or (b), and your answers to your tutor's questions under `## M1-4`.

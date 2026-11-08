# Step M1-3 · The data shapes, and reading products

**Why:** this is the start of the code everything else calls. Your routes, your commands and your tools, in steps 5 to 7, will all call the functions you write here and in step 4. So this code lives in its own module, `backend/products.py`, and it knows nothing about who's calling: no web, no command line, no agents. That's what lets all three use it, and it's what the contract means by an **operation**.

You write two files, in three small pieces, with a check after each:
1. `backend/schemas.py`: the shapes of the data going in and out;
2. `list_products`, in `backend/products.py`;
3. `get_product`, and its named error, in the same file.

## Piece 1 · The data shapes: `backend/schemas.py`

**The idea.** A **Pydantic model** is a Python class that describes the shape of some data, and checks it. When you create one from wrong data, like a negative price, it refuses, with a message that names the field. FastAPI, your command line and your tools will all use the same models, so the rules you write here hold for every way in.

You need two models, because what a caller sends isn't what comes back:
- a caller never sends an `id` or the times, because the database creates those;
- what comes back includes them.

**Turning your table into Python types.** Every column becomes one field:
- a `TEXT NOT NULL` column becomes `str`;
- a column that may be `NULL` becomes `str | None = None`. `None` is Python's `NULL`, `|` means "or", and `= None` makes the field optional;
- an `INTEGER NOT NULL` column becomes `int`;
- a column with a default becomes a field with the same default: `DEFAULT 0` becomes `= 0`;
- a `TIMESTAMPTZ` column becomes `datetime`, from Python's `datetime` module.

Rules go in `Field(…)`:
- `Field(ge=0)` means "greater than or equal to 0";
- `Field(min_length=1)` means "at least one character";
- with a default as well, the default goes inside: `Field(default=0, ge=0)`;
- `description="…"` adds an explanation. Your API's docs page and your agent's tools will show it.

**An example on a different table,** the library's books:

```python
from datetime import datetime

from pydantic import BaseModel, Field


class BookCreate(BaseModel):
    isbn: str = Field(min_length=1)
    title: str = Field(min_length=1)
    subtitle: str | None = Field(default=None, min_length=1)
    copies: int = Field(default=1, ge=0, description="How many copies the library owns.")


class Book(BookCreate):
    id: int
    added_at: datetime
```

`class Book(BookCreate)` means `Book` has every field of `BookCreate`, plus the ones listed under it. `subtitle` is optional, but when it's given it must have at least one character, so "no subtitle" has exactly one form: `None`.

**You write `backend/schemas.py`,** with two models:
1. **`ProductCreate`:** the fields `sku`, `name`, `description`, `category`, `image_url`, `price_cents` and `stock`, with the rules in [`CONTRACT.md`](../../CONTRACT.md), "A product".
2. **`Product`:** based on `ProductCreate`, adding `id`, `created_at` and `updated_at`.

**Hint:** `sku`, `name`, `category` and `price_cents` have no default, which is what makes them required. Give `price_cents` a `description` that says it's in cents. An agent reading your tools will thank you.

**Check.** Run this in `~/code/store`:

```
docker compose exec api python -c "from schemas import ProductCreate; print(ProductCreate(sku='TEST-1', name='Test lamp', category='lighting', price_cents=1299))"
```

**You should see** one line listing every field, with the ones you didn't give at their defaults:

```
sku='TEST-1' name='Test lamp' description=None category='lighting' image_url=None price_cents=1299 stock=0
```

Now change `price_cents=1299` to `price_cents=-1` and run it again. **You should see** a long error that ends like this:

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for ProductCreate
price_cents
  Input should be greater than or equal to 0 [type=greater_than_equal, input_value=-1, input_type=int]
    For further information visit https://errors.pydantic.dev/2.14/v/greater_than_equal
```

- `ModuleNotFoundError: No module named 'schemas'` means the file isn't called `schemas.py`, or isn't in `backend/`.
- A `ValidationError` naming a field you *did* give means its name is misspelt in your model.

## Piece 2 · Reading every product: `list_products`

**The idea.** An operation that reads takes four moves:
1. **Borrow a connection** from the pool you made in M0: `with pool.connection() as conn:`. The lines indented under it use the connection, and when they finish, it goes back to the pool.
2. **Run SQL:** `conn.execute("SELECT …")`.
3. **Fetch the rows:** `.fetchall()` returns a list of rows. Each row is a dictionary, because of `dict_row` in `db.py`.
4. **Turn rows into models:** `Product(**row)`. The `**` passes the dictionary's keys as named arguments, so it means `Product(id=…, sku=…, …)`.

`[Book(**row) for row in rows]` is a **list comprehension**: it builds a list by running `Book(**row)` once for each row. `-> list[Book]` says what the function returns. Python doesn't enforce it, but it documents the function, and your editor uses it.

**An example on a different table:**

```python
def list_books() -> list[Book]:
    with pool.connection() as conn:
        rows = conn.execute("SELECT * FROM books ORDER BY title").fetchall()
    return [Book(**row) for row in rows]
```

**You write `backend/products.py`,** starting with:
- the imports: `pool` from `db`, and `Product` from `schemas`;
- `list_products()`, which takes no arguments and returns `list[Product]`: every product, sorted by `id`, smallest first.

**Check.** This one is a short script fed to Python inside your API's container. Copy the whole block, from `docker` down to the last `EOF`:

```
docker compose exec -T api python - <<'EOF'
import products
from db import pool

items = products.list_products()
print(len(items), "products, ids", [p.id for p in items])
print(items[0])
pool.close()
EOF
```

**You should see** your number of products and their ids, then the first one in full. Mine:

```
10 products, ids [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
sku='TENT-2P' name='Two-Person Tent' description='Freestanding, 2.1 kg, two doors.' category='shelter' image_url=None price_cents=24900 stock=5 id=1 created_at=datetime.datetime(2026, 11, 8, 14, 7, 41, 174834, tzinfo=zoneinfo.ZoneInfo(key='Etc/UTC')) updated_at=datetime.datetime(2026, 11, 8, 14, 7, 41, 174834, tzinfo=zoneinfo.ZoneInfo(key='Etc/UTC'))
```

The script ends with `pool.close()`. Without it, Python prints a long, alarming but harmless message as it exits, starting `Exception ignored while calling deallocator` and ending `cannot join thread at interpreter shutdown`: the pool's background threads were still running.

## Piece 3 · Reading one product, and a named error: `get_product`

**The idea.** Reading one product adds three things:
1. **A value in the SQL.** Write `%s` where the value goes, and pass the values separately, as a tuple: `conn.execute("SELECT … WHERE id = %s", (product_id,))`. The comma in `(product_id,)` is how Python writes a tuple with one item. **Never paste a value into the SQL text yourself,** with an f-string or `+`. A value like `'); DROP TABLE products; --` would run as SQL. Your store will soon take input from agents, and an agent passes along whatever it was told.
2. **One row, or none:** `.fetchone()` returns the first row, or `None` when there isn't one.
3. **A named error.** `class ProductNotFound(Exception):` creates an error of your own. You `raise` it with a message a person, or a model, can act on. Naming it lets each way in decide what it means: a 404 for HTTP, exit code 3 for the command line, a tool error for an agent.

**An example on a different table:**

```python
from db import pool
from schemas import Book, BookCreate


class BookNotFound(Exception):
    """Raised when no book has this id."""


def get_book(book_id: int) -> Book:
    with pool.connection() as conn:
        row = conn.execute("SELECT * FROM books WHERE id = %s", (book_id,)).fetchone()
    if row is None:
        raise BookNotFound(f"No book with id {book_id}.")
    return Book(**row)
```

`f"No book with id {book_id}."` is an **f-string**: the part in braces is replaced by its value. That's fine in a message, which nothing executes. It's never fine in SQL.

**You write, in `backend/products.py`:**
- `class ProductNotFound(Exception):`, with a one-line docstring saying when it's raised;
- `get_product(product_id: int) -> Product`, which returns the product with that id, or raises `ProductNotFound` with exactly the message `No product with id 42.`, with the id filled in.

**Hint:** the check for "no row" is `if row is None:`, after the `with` block.

**Check:**

```
docker compose exec -T api python - <<'EOF'
import products
from db import pool

print(products.get_product(1).name)
try:
    products.get_product(999999)
except products.ProductNotFound as e:
    print("ProductNotFound:", e)
pool.close()
EOF
```

**You should see** the name of your product 1, then the error's message:

```
Two-Person Tent
ProductNotFound: No product with id 999999.
```

## The rule about imports

`backend/products.py` imports from `db`, `schemas` and `psycopg`, and nothing else. It never imports `fastapi`, `typer`, `mcp`, or anything else that belongs to one way in. If it did, the command line and the tools would drag the web server along, or worse, an operation would answer with an HTTP error that means nothing to a command line or an agent. The check tests this.

## Check

```
make check M=1 STEP=3
```

**You should see** everything before, then:

```
  PASS  M1-3  products.py imports nothing from the web, the command line or the tool server
  PASS  M1-3  ProductCreate and Product have the contract's fields
  PASS  M1-3  list_products() returns every product as a Product, sorted by id
  PASS  M1-3  get_product(id) returns that product
  PASS  M1-3  get_product(999999) raises ProductNotFound with the contract's message

24 passed, 0 failed, 0 skipped.
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
?? backend/products.py
?? backend/schemas.py
```

Then commit and push:

```
git add -A
git commit -m "M1-3: data shapes, list and get"
git push
```

Answer your tutor's questions under `## M1-3` in `JOURNAL.md`.

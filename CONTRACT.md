# The contract

This file says exactly what your store must do: every route, command and tool, every body, status code, exit code and error message. The checks test it, line by line. Each milestone adds a section when its guides arrive.

**The contract is fixed. How you meet it is yours.** Your table's column types, your SQL and your Python are your decisions, as long as everything a caller can see matches this file.

---

## How the store is shaped

**An operation** is one thing the store does, like "create a product". You write each operation once, as a plain Python function, in a module that knows nothing about the web, the command line or agents (`backend/products.py` in M1).

**Each operation is reachable three ways,** and all three call the same function:
- **HTTP:** a route in `backend/main.py`, for web pages and other programs.
- **The command line:** a command in `backend/cli.py`, run as `./store …`, for you, for scripts, and for agents working in a terminal.
- **Agent tools:** an MCP tool in `backend/tools.py`, for agents connected to the store.

The same input gives the same result and the same error message, whichever way it comes in. The parity check (M1 step 7) tests that.

### Errors

Every error an operation can raise has a kind. The kind decides what each way in does with it:

| Kind | HTTP status | CLI exit code |
|---|---|---|
| success | 200, or 201 when something was created | 0 |
| invalid input | 422 | 2 |
| not found | 404 | 3 |
| conflict with what's stored | 409 | 4 |
| anything unexpected | 500 | 1 |

What the caller receives:
- **HTTP:** the status above, and the body `{"detail": "<message>"}`. For invalid input, `detail` is FastAPI's standard list of what's wrong with each field.
- **CLI:** nothing on stdout, the message on stderr, and the exit code above.
- **Tools:** an error result (`isError: true`) whose text contains the message.

The messages are written for whoever reads them next, which is often a model deciding what to do. So each one says what was wrong, with the value that was wrong in it.

---

## M0 · Health

`GET /health` is for machines checking that the server and its database are up. It isn't an operation, so it has no command and no tool.

- **The database answers:** `200` with `{"status": "ok", "database": "ok"}`.
- **The database doesn't answer within about 2 seconds:** `503` with `{"status": "error", "database": "unreachable"}`.

---

## M1 · Products

### A product

- **`id`:** an integer, set by the database.
- **`sku`:** a string of at least 1 character. Required. No two products share one.
- **`name`:** a string of at least 1 character. Required.
- **`description`:** a string of at least 1 character, or null. Optional, and null when it isn't given. Never an empty string.
- **`category`:** a string of at least 1 character. Required.
- **`image_url`:** a string of at least 1 character, or null. Optional, and null when it isn't given. Never an empty string.
- **`price_cents`:** an integer, 0 or more. Required. It's in cents, so `1999` means $19.99.
- **`stock`:** an integer, 0 or more. Optional, and 0 when it isn't given.
- **`created_at` and `updated_at`:** a date and time, set by the database and sent with its time zone.

Dates and times are sent in ISO 8601 with a time zone, for example `2026-11-08T15:04:05.123456Z`. The `Z` means UTC.

An example, as every way in returns it:

```json
{
  "sku": "TENT-2P",
  "name": "Two-Person Tent",
  "description": "Freestanding, 2.1 kg, two doors.",
  "category": "shelter",
  "image_url": null,
  "price_cents": 24900,
  "stock": 5,
  "id": 1,
  "created_at": "2026-11-08T15:04:05.123456Z",
  "updated_at": "2026-11-08T15:04:05.123456Z"
}
```

The order of the fields doesn't matter.

### The table

The table is called `products`, and its columns have exactly the names of the fields above. Their types are yours to choose (M1 step 1), but the database itself must:
- refuse a negative `price_cents` or `stock`;
- refuse a second product with the same `sku`;
- refuse a product without a `sku`, `name`, `category` or `price_cents`;
- set `id`, `created_at` and `updated_at` itself, and `stock` to 0 when it isn't given;
- leave `description` and `image_url` empty (`NULL`) when they aren't given;
- store `created_at` and `updated_at` with their time zone.

### The data shapes, in `backend/schemas.py`

- **`ProductCreate`:** what a caller sends to create a product. Its fields are `sku`, `name`, `description`, `category`, `image_url`, `price_cents` and `stock`, with the rules in the table above.
- **`Product`:** a product as the store returns it. It has every field of `ProductCreate`, plus `id`, `created_at` and `updated_at`.

### The operations, in `backend/products.py`

`backend/products.py` imports nothing from `fastapi`, `starlette`, `typer`, `click`, `mcp`, `httpx` or `uvicorn`.

- **`list_products()`** returns a `list[Product]`: every product, sorted by `id`, smallest first.
- **`get_product(product_id: int)`** returns that `Product`, or raises `ProductNotFound`.
- **`create_product(data: ProductCreate)`** stores the product and returns it as a `Product`, or raises `DuplicateSku`.

The errors and their messages, with the values filled in:
- **`ProductNotFound`** (not found): `No product with id 42.`
- **`DuplicateSku`** (conflict): `A product with the SKU TENT-2P already exists.`

### The three ways in

| Operation | HTTP | Command | Tool |
|---|---|---|---|
| `list_products` | `GET /products` | `./store products list` | `list_products` |
| `get_product` | `GET /products/{product_id}` | `./store products get PRODUCT_ID` | `get_product` |
| `create_product` | `POST /products` | `./store products create …` | `create_product` |

### HTTP

- **`GET /products`:** `200`, a JSON list of every product, sorted by `id`.
- **`GET /products/{product_id}`:**
  - `200` and the product;
  - `404` and `{"detail": "No product with id 42."}` when there's none;
  - `422` when `product_id` isn't a whole number.
- **`POST /products`,** with a `ProductCreate` as its JSON body:
  - `201` and the new product, as stored;
  - `409` and `{"detail": "A product with the SKU TENT-2P already exists."}` when the SKU is taken;
  - `422` when the body breaks a rule (a missing field, an empty name, a negative or fractional price, …). Nothing is saved.

### The command line

`./store` runs `backend/cli.py` inside your API's container. Every command:
- prints exactly **one JSON value** on stdout when it succeeds: the same JSON the matching HTTP route returns;
- prints **nothing on stdout** when it fails, puts the message on stderr, and exits with the code from the errors table;
- never stops to ask a question, so a script or an agent can run it.

The commands:
- **`./store products list`**
- **`./store products get PRODUCT_ID`**
- **`./store products create --sku TEXT --name TEXT --category TEXT --price-cents INTEGER [--description TEXT] [--image-url TEXT] [--stock INTEGER]`**
  - Invalid input exits `2`, with Pydantic's message on stderr, which names the field (`price_cents`, …).
  - A SKU that's taken exits `4`, with `A product with the SKU TENT-2P already exists.` on stderr.
- **`./store --help`, `./store products --help` and `./store products create --help`** print what each command does, and exit `0`.

### The tools

An MCP server called `store`, served by your API at `http://localhost:8000/mcp` (streamable HTTP). Each tool has a description, written as the function's docstring.

- **`list_products`** takes no arguments, and returns the list of products.
- **`get_product`** takes `product_id`, an integer, and returns the product.
- **`create_product`** takes `product`, an object shaped like `ProductCreate`, and returns the new product.

- `get_product` for a missing id is an error whose text contains `No product with id 42.`
- `create_product` with a SKU that's taken is an error whose text contains `A product with the SKU TENT-2P already exists.`
- `create_product` with invalid input is an error that names the field.

### Parity

Every route in your API's `/openapi.json`, apart from `/health`, is listed in "The three ways in" above, and has its command and its tool. A route that isn't in this contract fails the check, so nothing an agent might need is left reachable only one way.

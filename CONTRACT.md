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
| no valid session (from M3) | 401 | 5 |
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

---

## M2 · The admin side

### What changes for a product

- **A new field, `archived_at`:** a date and time with its time zone, or null. It's null for a product on sale, and set to the moment the product was archived. Every way in returns it with the product.
- **The table** gets the column through a second migration, `backend/migrations/002_add_archived_at.sql`. It's a `TIMESTAMPTZ` that may be `NULL`, with no default.
- **Archived products stay in the table.** Orders will point at them from M4 on.
- **Listing leaves archived products out,** unless the caller asks for them:
  - `list_products(include_archived: bool = False)`;
  - `GET /products?include_archived=true`;
  - `./store products list --include-archived`;
  - the tool `list_products`, with `include_archived: true`.
- **Getting one product by its id works whether it's archived or not.**

### The new data shapes, in `backend/schemas.py`

- **`ProductUpdate`:** what a caller sends to change a product. Its fields are `sku`, `name`, `description`, `category`, `image_url` and `price_cents`, each optional, with the same rules as in `ProductCreate`.
  - A field left out stays as it is.
  - `null` is refused for every field, with invalid input (422, exit 2).
  - Any other field is refused too, with invalid input. That includes `stock`, `id` and `archived_at`: a field that's ignored in silence would let a caller believe it changed something.
- **`StockChange`:** the body of a stock change, `{"change": <integer>}`. A positive change adds units, and a negative one removes them.

### The new operations, in `backend/products.py`

- **`archive_product(product_id: int)`** sets `archived_at` and `updated_at` to now, and returns the product. Archiving a product that's already archived changes nothing, and returns it as it is. A missing id raises `ProductNotFound`.
- **`update_product(product_id: int, changes: ProductUpdate)`** changes only the fields given, sets `updated_at` to now, and returns the product. With no fields given, it returns the product unchanged. It raises `ProductNotFound` and `DuplicateSku` as in M1.
- **`adjust_stock(product_id: int, change: int)`** adds `change` to the stock in a single SQL statement, sets `updated_at` to now, and returns the product. It raises `ProductNotFound`, or `InsufficientStock` (conflict) when the stock would go below zero. Then nothing changes.

The new error's message, with the values filled in: **`InsufficientStock`:** `Only 2 of Two-Person Tent in stock, so 5 can't be removed.`

### The three ways in

| Operation | HTTP | Command | Tool |
|---|---|---|---|
| `archive_product` | `POST /products/{product_id}/archive` | `./store products archive PRODUCT_ID` | `archive_product` |
| `update_product` | `PATCH /products/{product_id}` | `./store products update PRODUCT_ID …` | `update_product` |
| `adjust_stock` | `POST /products/{product_id}/stock` | `./store products adjust-stock PRODUCT_ID --change N` | `adjust_stock` |

**HTTP:**
- **`POST /products/{product_id}/archive`:** `200` and the product; `404` for a missing id.
- **`PATCH /products/{product_id}`,** with a `ProductUpdate` as its body: `200` and the product; `404`; `409` for a SKU that's taken; `422` for invalid input.
- **`POST /products/{product_id}/stock`,** with a `StockChange` as its body: `200` and the product; `404`; `409` and the `InsufficientStock` message; `422` when `change` isn't a whole number.

**The command line:**
- **`./store products archive PRODUCT_ID`**
- **`./store products update PRODUCT_ID [--sku TEXT] [--name TEXT] [--description TEXT] [--category TEXT] [--image-url TEXT] [--price-cents INTEGER]`.** Only the options given change. Exit codes: 2 for invalid input, 3 for a missing id, 4 for a SKU that's taken.
- **`./store products adjust-stock PRODUCT_ID --change N`.** Exit codes: 3 for a missing id, 4 for too little stock.

**The tools:**
- **`archive_product`** takes `product_id`.
- **`update_product`** takes `product_id`, and `changes`, an object shaped like `ProductUpdate`.
- **`adjust_stock`** takes `product_id` and `change`.

Each one is an error, whose text contains the message, in the same cases as the command line.

### The stock race

Changing stock must be safe when many callers do it at the same moment. `checks/stock_race.py` sends 50 changes of +1 and 50 of −1 to one product, all at once, through any of the three ways in. Then:
- every change is answered with success;
- the stock ends exactly where it started;
- removing more than is in stock is refused with the `InsufficientStock` message, and the stock is still where it started.

---

## M3 · Visitors and carts

### Sessions

A visitor doesn't sign in. They start a **session**, and get its **token**: a random string that works for an hour. Whoever holds the token can use that session's cart, so a token is a secret, the way a key is.

- **The table `sessions`,** in `backend/migrations/003_create_sessions.sql`, has `token`, a `TEXT` primary key; `created_at`; and `expires_at`, a `TIMESTAMPTZ` that's never `NULL`, an hour after the session started.
- **`Session`,** in `backend/schemas.py`, is what starting a session returns: `token` and `expires_at`.
- **`backend/sessions.py`** has the operations, and imports nothing from a way in:
  - **`start_session()`** makes a token with `secrets.token_urlsafe(32)`, stores it, and returns the `Session`.
  - **`require_session(token: str | None)`** returns the token when it belongs to a session that hasn't expired. Otherwise it raises `NoSession` (no valid session), with one of three messages:
    - no token: `No session token. Start a session, then send its token with every cart request.`
    - a token that isn't in the table: `That session token doesn't exist. Start a new session.`
    - a token whose `expires_at` has passed: `That session has expired. Start a new session.`

**How each way in carries the token:**
- **HTTP:** the header `Authorization: Bearer <token>`. A missing or malformed header counts as no token. A `401` also carries the header `WWW-Authenticate: Bearer`.
- **The command line:** the option `--session TOKEN` on every cart command. Leaving it out counts as no token, and exits `5`.
- **The tools:** the argument `session_token` on every cart tool. Leaving it out counts as no token, and the tool's error carries the message.

### The cart

- **The table `cart_items`,** in `backend/migrations/004_create_cart_items.sql`, holds one line per session and product:
  - `session_token`, which must be a session's token, and whose lines are deleted with their session;
  - `product_id`, which must be a product's `id`;
  - `quantity`, above zero;
  - a primary key on `(session_token, product_id)`.
- **Its shapes, in `backend/schemas.py`:**
  - **`CartLine`:** `product_id`, `sku`, `name`, `price_cents`, `quantity`, `line_total_cents` (`price_cents × quantity`), and `available`, which is `false` when the product has been archived since it went in the cart.
  - **`Cart`:** `items`, a list of `CartLine` sorted by `product_id`, and `total_cents`, the sum of the available lines' totals.
  - **`CartQuantity`:** the body for setting a line, `{"quantity": <integer, 1 or more>}`.
- **`backend/cart.py`** has the operations. Each one checks the session first, with `require_session`:
  - **`get_cart(token)`** returns the session's `Cart`.
  - **`set_cart_item(token, product_id, quantity)`** makes the cart hold exactly `quantity` of the product. It adds a line, or replaces the quantity of the line that's there, then returns the `Cart`. It raises:
    - `ProductNotFound` for a missing product: `No product with id 42.`;
    - `ProductNotFound` for an archived one: `Product 9 isn't for sale.`;
    - `InsufficientStock` when `quantity` is more than is in stock: `Only 3 of Solo Tent in stock, so a cart can't hold 5.`
  - **`remove_cart_item(token, product_id)`** removes the line and returns the `Cart`. Removing a line that isn't there changes nothing.

| Operation | HTTP | Command | Tool |
|---|---|---|---|
| `start_session` | `POST /sessions` | `./store session start` | `start_session` |
| `get_cart` | `GET /cart` | `./store cart show` | `get_cart` |
| `set_cart_item` | `PUT /cart/items/{product_id}` | `./store cart set PRODUCT_ID QUANTITY` | `set_cart_item` |
| `remove_cart_item` | `DELETE /cart/items/{product_id}` | `./store cart remove PRODUCT_ID` | `remove_cart_item` |

**HTTP:**
- **`POST /sessions`:** `201` and the `Session`.
- **`GET /cart`:** `200` and the `Cart`; `401` with one of the three messages.
- **`PUT /cart/items/{product_id}`,** with a `CartQuantity` body: `200` and the `Cart`; `401`; `404` (missing or archived); `409` (not enough stock); `422` (a quantity below 1).
- **`DELETE /cart/items/{product_id}`:** `200` and the `Cart`; `401`.

**The command line:**
- `./store session start`;
- `./store cart show --session TOKEN`;
- `./store cart set PRODUCT_ID QUANTITY --session TOKEN`, with exit codes 2 (a quantity below 1), 3 (missing or archived), 4 (not enough stock) and 5 (no valid session);
- `./store cart remove PRODUCT_ID --session TOKEN`, with exit code 5 (no valid session).

**The tools:**
- **`start_session`** takes no arguments.
- **`get_cart`** takes `session_token`.
- **`set_cart_item`** takes `product_id`, `quantity` (1 or more, which the tool's schema says), and `session_token`.
- **`remove_cart_item`** takes `product_id` and `session_token`.

Each one is an error, whose text contains the message, in the same cases as the command line.

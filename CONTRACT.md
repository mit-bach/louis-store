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

From M5, anything unexpected gives every caller one fixed message, and never a traceback: see "M5 · Unexpected errors".

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

---

## M4 · Checkout

### Orders

- **The table `orders`,** in `backend/migrations/005_create_orders.sql`: `id`, a number the database gives it; `session_token`, the session that placed it, as `TEXT` that's never `NULL`; `total_cents`; and `created_at`, a `TIMESTAMPTZ`. Deleting a session never deletes or blocks its orders.
- **The table `order_lines`,** in `backend/migrations/006_create_order_lines.sql`: `order_id`, which must be an order's `id`; `product_id`, which must be a product's `id`; `quantity`, above zero; and `price_cents`, the price the product had when it was bought, which never changes afterwards. There's one line per order and product.
- **Its shapes, in `backend/schemas.py`:**
  - **`OrderLine`:** `product_id`, `sku`, `name`, `quantity`, `price_cents` (the price paid), and `line_total_cents`.
  - **`Order`:** `id`, `items` (a list of `OrderLine`, sorted by `product_id`), `total_cents`, and `created_at`.

### Checkout, in `backend/orders.py`

`checkout(token)` checks the session, then, in **one transaction**:
1. reads the cart's lines with their products, **locking those product rows, in `id` order**;
2. checks every line;
3. writes the order and its lines, at the prices it just read;
4. lowers each product's stock by the line's quantity;
5. empties the cart.

It returns the `Order`. `total_cents` is the sum of `price_cents × quantity` over the lines: it always comes from the database, never from the caller. If any check fails, it raises, and **nothing changes**: no order, the same stock, the same cart.

The errors, in the order they're checked, with their messages:
- **`NoSession`** (no valid session), as in M3.
- **`EmptyCart`** (conflict): `Your cart is empty.`
- **`NotForSale`** (conflict), when one or more lines' products have been archived. It names each one, in product id order: `Not for sale any more: Bottle 1 L (product 10). Remove it from your cart, then check out again.` With more than one: `Not for sale any more: Bottle 1 L (product 10), Tarp 3 x 3 m (product 3). Remove them from your cart, then check out again.`
- **`InsufficientStock`** (conflict), when one or more lines want more than is in stock. It has one sentence per short line, in product id order, joined by a space: `Only 1 of Solo Tent left in stock. Only 0 of Head Torch left in stock.`

A price that changed since a product went in the cart doesn't stop a checkout. The order records the price paid.

| Operation | HTTP | Command | Tool |
|---|---|---|---|
| `checkout` | `POST /checkout` | `./store checkout` | `checkout` |

- **HTTP:** `POST /checkout`, with the session's Bearer header. No body: anything sent is ignored. `201` and the `Order`; `401`; `409` with one of the messages above.
- **The command line:** `./store checkout --session TOKEN`. Exit codes: 4 for the three conflicts, 5 for no valid session.
- **The tool:** `checkout`, taking `session_token`. Each refusal is an error whose text contains the message.

### Two buyers at once

- **`checks/race_test.py`:** each round, two sessions each put the last unit of a product in their cart and check out at the same instant. Every round must end with one `201`, one `409` and a stock of 0: never two orders, never a `500`, never a negative stock. `uv run checks/race_test.py --rounds 20` prints `20/20 rounds: one 201, one 409, stock 0`.
- **`checks/deadlock_test.py`:** each round, two sessions hold the same two products, put in their carts in opposite orders, and check out at the same instant. Both must get an order. The checks run it for 500 rounds.

---

## M5 · Agent-first, for real

### Retries: the Idempotency-Key

- **The column,** in `backend/migrations/007_add_idempotency_key.sql`: `orders.idempotency_key`, `TEXT`, and empty (`NULL`) when a checkout had no key. A `UNIQUE` constraint on `(session_token, idempotency_key)`, so a session can't have two orders with one key. Empty keys are never equal to each other, so a session can have any number of orders without one.
- **`checkout(token, idempotency_key=None)`,** in `backend/orders.py`, checks the session, then, in its one transaction:
  1. its locking read, as in M4;
  2. if a key was given, and this session already has an order with it: it returns that order, as it was placed, and changes nothing;
  3. otherwise, everything as in M4, and the new order records the key.
- **A key belongs to its session.** Another session using the same key gets its own order.
- **Only an order records its key.** A refused checkout changes nothing, so its key is still free for the next try.
- **A key is any text the caller chooses:** a new one for each purchase it means to make, and the same one every time it retries that purchase.

| Operation | HTTP | Command | Tool |
|---|---|---|---|
| `checkout` with a key | `POST /checkout` with the header `Idempotency-Key: KEY` | `./store checkout --session TOKEN --idempotency-key KEY` | `checkout` with `idempotency_key` |

- **A repeat answers exactly as the first did:** `201` and the same order, exit 0 and the same JSON, or the same tool result.
- **The tool's description** tells an agent to make up a key for each purchase, and to reuse it when it isn't sure a checkout went through.
- **`checks/retry_test.py`:** each round, a new session puts 1 of a product with 2 in stock in its cart, then checks out twice with one key: one after the other in odd rounds, at the same instant in even rounds. Both answers must be the same order, and the stock must end at 1. `--via http`, `cli` or `tools`. The checks run 20 rounds through HTTP, 6 through `./store` and 10 through the tools.

### Unexpected errors

Anything an operation raises that no way in maps to a kind above (a bug, a database that's down) reaches every caller as this message, and nothing else:

`Something went wrong in the store. Try again in a moment.`

- **HTTP:** `500` and `{"detail": "Something went wrong in the store. Try again in a moment."}`.
- **The command line:** exit 1, and that line alone on stderr.
- **Tools:** an error whose text contains it.

Never a traceback, a file path or a line of SQL. The traceback goes to the API's log, which `make logs` shows.

### The cart says what's in stock

`CartLine` gains `in_stock`: `true` when the line's quantity is in stock right now (`quantity <= stock`). `available` still means only that the product hasn't been archived, and `total_cents` still counts the available lines. Checkout checks the stock again, under its lock: `in_stock` is a hint for whoever reads the cart, not a promise.

### The customer's agent

A folder in your repository, `agents/customer/`, holds the agent a customer would use:
- **`CLAUDE.md`:** its brief, in your words.
- **`.mcp.json`:** one server, `store`: `{"type": "http", "url": "http://localhost:8000/mcp"}`.
- **`.claude/settings.json`:**
  - `permissions.allow`: each customer tool by its full name: `mcp__store__list_products`, `mcp__store__get_product`, `mcp__store__start_session`, `mcp__store__get_cart`, `mcp__store__set_cart_item`, `mcp__store__remove_cart_item` and `mcp__store__checkout`;
  - `permissions.deny`: `Bash`, `WebFetch`, `WebSearch`, and each admin tool: `mcp__store__create_product`, `mcp__store__archive_product`, `mcp__store__update_product` and `mcp__store__adjust_stock`;
  - `enabledMcpjsonServers`: `["store"]`;
  - `claudeMdExcludes`: a pattern that matches the `CLAUDE.md` at the top of your repository, and not the agent's own.

Every tool the store has is in `allow` or in `deny`.

### Evals

- **`checks/evals.py`** runs five shopping tasks, each as one headless session of your customer agent, and checks each in the database. `--model` (default `haiku`), `--tasks` and `--runs` change what it runs.
- **Each run** adds a line to `checks/evals-runs.txt`, which you commit. The line holds the score, the model, a fingerprint of your tool descriptions, and what Claude Code says the run cost.

---

## M6 · The frontend

### Your orders

- **`list_orders(token)`,** in `backend/orders.py`, checks the session, then returns its orders, newest first, each as it was placed: the same `Order` that `checkout` returns, with the prices paid. Another session's orders are never in it.

| Operation | HTTP | Command | Tool |
|---|---|---|---|
| `list_orders` | `GET /orders`, with the session's Bearer header | `./store orders --session TOKEN` | `list_orders`, taking `session_token` |

- **HTTP:** `200` and a list of orders; `401` as in M3.
- **The command line:** the list as JSON, exit 0; exit 5 for no valid session.
- **The tool:** the list; an error for no valid session. It's a customer tool: your customer agent's settings allow it.

### The door for the browser

A page served from `http://localhost:3000` may call the API from the browser. `backend/main.py` adds FastAPI's `CORSMiddleware` with exactly that origin, every method and every header. A page from anywhere else gets no permission.

### The spec

`FRONTEND-SPEC.md`, at the top of your repository, in your words. It says:
- each page, and the endpoint each one calls;
- where the session token lives in the browser, and how it's sent;
- what a page shows for a `401`, a `409` and a `422`;
- how checkout uses an `Idempotency-Key`;
- the walkthrough: what you'll check by hand, and what each check should show.

### The frontend

In `frontend/`, built by your coding agent from the spec: Next.js with the App Router, TypeScript, Tailwind CSS and shadcn/ui, with pnpm. `pnpm lint` and `pnpm build` pass in it, and `pnpm dev` serves it at `http://localhost:3000`.

---

## Optional spec 14 · Your own migration runner

`backend/migrate.py`, run inside the API container:

```
docker compose exec api python migrate.py              the files in backend/migrations/
docker compose exec api python migrate.py <folder>     the files in another folder
```

- **It connects** with the `DATABASE_URL` the container already has.
- **It records** what's applied in `schema_migrations`, the table `make migrate` keeps, with a column added: `checksum`, the SHA-256 of the file's bytes, in hex.
- **One run at a time:** it takes a Postgres advisory lock for the whole run, so a second run waits, then finds everything applied.
- **Before it applies anything,** it compares every applied file that has a checksum with the file as it is now. If one differs, it changes nothing, prints this on stderr, and exits 4:
  `<file name> was edited after it was applied. Put it back as it was, and write a new migration for the change.`
- **A row without a checksum** was applied by `make migrate`. It records the file's checksum, without running the file again, and prints `checksum recorded for <file name>`.
- **Each new file,** in file-name order, is applied in a transaction of its own, together with its row. It prints `applying <file name>` for each.
- **At the end** it prints `migrations up to date`, and exits 0.

`make spec S=14` checks it.

# Step M5-3 · What an agent reads

**Why:** an agent treats every answer as its next instruction. Your refusals already say what went wrong and what to do. This step covers the two places where your store still says too much, or too little: when something breaks that you didn't plan for, and when the cart can't tell an agent what's wrong with a line.

## 1. When something breaks

Every error you've written has a kind and a message. But a bug, or a database that's down, raises something no route catches. What reaches the caller then?

**Predict,** under `## M5-3` in `PREDICTIONS.md`: the database loses a table in the middle of a checkout. What does `curl` get? What does `./store checkout` print? And what would an agent do with each?

Break your own store for a minute: hide the `order_lines` table by renaming it.

```
docker compose exec db psql -U store -d store -c "ALTER TABLE order_lines RENAME TO order_lines_gone;"
```

A checkout over HTTP, then from the command line. Copy the whole block:

```
TOKEN=$(./store session start | python3 -c "import json, sys; print(json.load(sys.stdin)['token'])")
./store cart set 7 1 --session $TOKEN > /dev/null
curl -s -w '\n%{http_code}\n' -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8000/checkout
./store checkout --session $TOKEN; echo "exit code $?"
```

<details><summary>What mine showed (open it after your run)</summary>

```
Internal Server Error
500
╭───────────────────── Traceback (most recent call last) ──────────────────────╮
│ /app/cli.py:181 in checkout_command                                          │
│                                                                              │
│   178 ):                                                                     │
│   179 │   """Buy everything in a session's cart: one order, at today's       │
│       prices, and the cart emptied."""                                       │
│   180 │   try:                                                               │
│ ❱ 181 │   │   print_json(orders.checkout(session, idempotency_key))          │
│   182 │   except sessions.NoSession as e:                                    │
│   183 │   │   fail(str(e), 5)                                                │
│   184 │   except (orders.EmptyCart, orders.NotForSale,                       │
│       products.InsufficientStock) as e:                                      │
│                                                                              │
│ /app/orders.py:55 in checkout                                                │
│                                                                              │
│   52 │   │   │   (token, total, idempotency_key),                            │
│   53 │   │   ).fetchone()                                                    │
│   54 │   │   for line in lines:                                              │
│ ❱ 55 │   │   │   conn.execute(                                               │
│   56 │   │   │   │   "INSERT INTO order_lines (order_id, product_id,         │
│      quantity, price_cents) VALUES (%s, %s, %s, %s)",                        │
│   57 │   │   │   │   (order["id"], line["product_id"], line["quantity"],     │
│      line["price_cents"]),                                                   │
│   58 │   │   │   )                                                           │
│                                                                              │
│ /usr/local/lib/python3.14/site-packages/psycopg/connection.py:304 in execute │
│                                                                              │
│   301 │   │   │   else:                                                      │
│   302 │   │   │   │   return cur.execute(query, params, prepare=prepare)     │
│   303 │   │   except e._NO_TRACEBACK as ex:                                  │
│ ❱ 304 │   │   │   raise ex.with_traceback(None)                              │
│   305 │                                                                      │
│   306 │   def commit(self) -> None:                                          │
│   307 │   │   """Commit any pending transaction to the database."""          │
╰──────────────────────────────────────────────────────────────────────────────╯
UndefinedTable: relation "order_lines" does not exist
LINE 1: INSERT INTO order_lines (order_id, product_id, quantity, pri...
                    ^
exit code 1
```
</details>

HTTP says `Internal Server Error`, which is safe, but tells an agent nothing about what to do. The command line prints your source code, your file paths and your SQL, to whoever ran it. An agent that gets 40 lines of your code usually starts debugging your server instead of telling its customer something. Your tool server is in between: an unexpected error reaches an agent as `Error executing tool checkout` and nothing more.

Put the table back:

```
docker compose exec db psql -U store -d store -c "ALTER TABLE order_lines_gone RENAME TO order_lines;"
```

**The fix:** one message, the contract's, for anything unexpected, through every way in: `Something went wrong in the store. Try again in a moment.` The caller gets one plain sentence. You still get the whole traceback, in `make logs`. And thanks to step 1, "try again" is now safe for a checkout, as long as the caller resends its key.

## The idea: one message, three places

**HTTP.** `@app.exception_handler(Exception)` registers a function that FastAPI calls for any exception no route caught. It returns the response. The server still writes the traceback to its log.

**The command line.** Catch everything around `app()` at the bottom of `cli.py`, print the message on stderr, and exit 1. The traceback goes to the server's log: every process in the container can write to the server's own error output, and `/proc/1/fd/2` is that output. Process 1 is the server, and file 2 is its error output. Use this function exactly:

```python
def log_crash() -> None:
    """Write the traceback to the API's own log, where `make logs` shows it, not to the caller."""
    with open("/proc/1/fd/2", "w") as log:
        traceback.print_exc(file=log)
```

**The tools.** Every tool needs the same catch, and repeating it in each one is how one gets forgotten. Instead, write a **decorator**: a function that takes a function, and returns a new function that wraps it. `@mcp.tool()` is one you've used since M1. Yours runs the tool inside `try`, lets a `ToolError` through as it is, and turns anything else into `ToolError` with the message. **`@functools.wraps(tool)`** copies the tool's name, docstring and arguments onto the wrapper, so the tool server still describes the tool to agents from them. Put it under `@mcp.tool()`, so the tool server registers the wrapped function.

**An example on a different table,** the library, in the same three places:

```python
UNEXPECTED = "Something went wrong in the library. Try again in a moment."


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    """Any error no route maps: the caller gets one line, the log gets the traceback."""
    return JSONResponse(status_code=500, content={"detail": UNEXPECTED})
```

```python
UNEXPECTED = "Something went wrong in the library. Try again in a moment."


def log_crash() -> None:
    """Write the traceback to the API's own log, where `make logs` shows it, not to the caller."""
    with open("/proc/1/fd/2", "w") as log:
        traceback.print_exc(file=log)


if __name__ == "__main__":
    try:
        app(prog_name="library")
    except Exception:
        log_crash()
        typer.echo(UNEXPECTED, err=True)
        sys.exit(1)
    finally:
        pool.close()
```

```python
UNEXPECTED = "Something went wrong in the library. Try again in a moment."
log = logging.getLogger("uvicorn.error")


def agent_errors(tool):
    """Any error a tool doesn't map: the agent gets one line, the log gets the traceback."""
    @functools.wraps(tool)
    def wrapper(*args, **kwargs):
        try:
            return tool(*args, **kwargs)
        except ToolError:
            raise
        except Exception:
            log.exception("tool %s failed", tool.__name__)
            raise ToolError(UNEXPECTED)
    return wrapper
```

## You write

- **`backend/main.py`:** the exception handler, answering `500` with `{"detail": <the message>}`.
- **`backend/cli.py`:** the catch around `app()`, with `log_crash()` as given. Add `import sys` and `import traceback` at the top.
- **`backend/tools.py`:** the decorator, and `@agent_errors` on every tool, under `@mcp.tool()`.

## 2. What the cart says about each line

## Decide first: what does `available` mean?

In M4-5 testing, an agent that lost the race for the last lantern noticed that its cart still showed the lantern as `available: true`, with a total of $49.00, at a stock of 0. It asked whether `available` should mean "can be bought right now". Three options:
- **(a)** Keep it: `available` means only "not archived".
- **(b)** Widen it: `available` means "not archived, **and** enough in stock".
- **(c)** Keep `available`, and add a second field, `in_stock`: "the quantity is in stock right now".

The facts:
- An archived line and a short line need different fixes. The first must come out of the cart. The second can wait for stock, or be lowered.
- Stock changes any second, so whatever the cart says about it is already old by the time anyone reads it. Checkout checks again, under its lock.
- With (b), an agent sees `available: false`, and has to fetch the product to find out why.

**Write (a), (b) or (c), and why, under `## M5-3` in `JOURNAL.md`, before you open the answer.**

<details><summary>Check your choice</summary>

(c). Two facts, two fields: the reader can tell "gone for good" from "not enough right now" without another call, and each points at its own fix. `in_stock` is a hint, not a promise, for the reason in the second fact. Checkout still decides, under its lock. The total stays as it was: the available lines. A line that's short today may be buyable in an hour.
</details>

## You write

- **`backend/schemas.py`:** `CartLine` gets `in_stock: bool`.
- **`backend/cart.py`:** `get_cart` reads it in the same query as the line: `c.quantity <= p.stock AS in_stock`.

## Check

Break the store again, and run the same two checkouts:

```
docker compose exec db psql -U store -d store -c "ALTER TABLE order_lines RENAME TO order_lines_gone;"
TOKEN=$(./store session start | python3 -c "import json, sys; print(json.load(sys.stdin)['token'])")
./store cart set 7 1 --session $TOKEN > /dev/null
curl -s -w '\n%{http_code}\n' -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8000/checkout
./store checkout --session $TOKEN; echo "exit code $?"
```

**You should see** the message, and nothing else, from both:

```
ALTER TABLE
{"detail":"Something went wrong in the store. Try again in a moment."}
500
Something went wrong in the store. Try again in a moment.
exit code 1
```

Put the table back, and look at the end of your log:

```
docker compose exec db psql -U store -d store -c "ALTER TABLE order_lines_gone RENAME TO order_lines;"
docker compose logs api --no-log-prefix --tail 12
```

**You should see** the traceback there, where only you read it:

```
ALTER TABLE
    ~~~~~~~~~~~~^
        "INSERT INTO order_lines (order_id, product_id, quantity, price_cents) VALUES (%s, %s, %s, %s)",
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        (order["id"], line["product_id"], line["quantity"], line["price_cents"]),
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.14/site-packages/psycopg/connection.py", line 304, in execute
    raise ex.with_traceback(None)
psycopg.errors.UndefinedTable: relation "order_lines" does not exist
LINE 1: INSERT INTO order_lines (order_id, product_id, quantity, pri...
                    ^
```

```
make check M=5 STEP=3
```

**You should see** everything before, then:

```
107 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

The first check hides `order_lines` in its throwaway store, calls checkout three ways, and makes sure nothing changed.

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
git commit -m "M5-3: what an agent reads"
git push
```

Answer your tutor's questions under `## M5-3` in `JOURNAL.md`.

"""Milestone 4: orders, checkout in one transaction, two buyers at once, and the audit of your harness."""

import ast
import asyncio
import json
import os
import re
from pathlib import Path

from contract import EMPTY_CART, NO_TOKEN, not_for_sale_any_more, parity, short_line
from kitlib import ROOT, Fail, check, http_json, short
from m2 import cli_json, new_product, raised, run_py, tool
from m3 import bearer, put_line, session

FORBIDDEN = {"fastapi", "starlette", "typer", "click", "mcp", "httpx", "uvicorn"}


def columns(ctx, table: str) -> dict:
    rows = ctx.sql_value(
        "SELECT string_agg(column_name || ':' || data_type || ':' || is_nullable, ',') "
        f"FROM information_schema.columns WHERE table_name = '{table}'"
    )
    return {c.split(":")[0]: c.split(":")[1:] for c in rows.split(",")} if rows else {}


def stock_of(ctx, pid: int) -> int:
    return int(ctx.sql_value(f"SELECT stock FROM products WHERE id = {pid}"))


def counts(ctx, token: str) -> tuple[str, str]:
    """(orders for the session, lines in its cart)"""
    return (ctx.sql_value(f"SELECT count(*) FROM orders WHERE session_token = '{token}'"),
            ctx.sql_value(f"SELECT count(*) FROM cart_items WHERE session_token = '{token}'"))


# --- Step 1 · Orders ---


@check(4, 1, "the orders and order_lines tables: an order keeps its lines, each line the price it was bought at",
       needs=("cart_items exist",), gives="orders exist")
def order_tables(ctx):
    orders, lines = columns(ctx, "orders"), columns(ctx, "order_lines")
    want_orders = {"id", "session_token", "total_cents", "created_at"}
    want_lines = {"order_id", "product_id", "quantity", "price_cents"}
    if not want_orders <= set(orders) or not want_lines <= set(lines):
        raise Fail("orders: " + ", ".join(sorted(want_orders)) + "; order_lines: " + ", ".join(sorted(want_lines)),
                   "orders: " + ", ".join(sorted(orders)) + "; order_lines: " + ", ".join(sorted(lines)))
    if orders["created_at"][0] != "timestamp with time zone":
        raise Fail("orders.created_at: timestamp with time zone", f"orders.created_at: {orders['created_at'][0]}")
    pid = new_product(ctx, "CHECK-ORDER-TABLE", stock=5)
    for sql, what in [
        (f"INSERT INTO order_lines (order_id, product_id, quantity, price_cents) VALUES (999999, {pid}, 1, 100);", "a line for an order that doesn't exist"),
        ("INSERT INTO orders (session_token, total_cents) VALUES ('x', 100) RETURNING id \\gset\n"
         f"INSERT INTO order_lines (order_id, product_id, quantity, price_cents) VALUES (:id, {pid}, 0, 100);", "a line with quantity 0"),
    ]:
        r = ctx.psql(f"BEGIN;\n{sql}\nROLLBACK;")
        if r.returncode == 0:
            raise Fail(f"the database refuses {what}", "it was accepted", "A foreign key to orders, and a CHECK on quantity.")


@check(4, 1, "an order outlives its session: deleting the session leaves the order", needs=("orders exist",))
def outlives_session(ctx):
    token = session(ctx)
    r = ctx.psql(f"INSERT INTO orders (session_token, total_cents) VALUES ('{token}', 500) RETURNING id;")
    if r.returncode != 0:
        raise Fail("an order can be saved for a session", short(r.stderr))
    order_id = r.stdout.strip().splitlines()[0]
    r = ctx.psql(f"DELETE FROM sessions WHERE token = '{token}';")
    if r.returncode != 0:
        raise Fail("the session can be deleted while it has an order", short(r.stderr),
                   "A foreign key from orders to sessions refuses it. Old sessions will be cleaned up; orders must stay.")
    if ctx.sql_value(f"SELECT count(*) FROM orders WHERE id = {order_id}") != "1":
        raise Fail("the order still there after its session is deleted", "it's gone",
                   "ON DELETE CASCADE from orders to sessions deletes a customer's order history.")


# --- Step 2 · Checkout, the operation ---


@check(4, 2, "orders.py imports nothing from the web, the command line or the tool server")
def no_web_imports(ctx):
    path = ROOT / "backend" / "orders.py"
    if not path.exists():
        raise Fail("backend/orders.py", "no such file")
    found = []
    for node in ast.walk(ast.parse(path.read_text())):
        mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
        found += [m for m in mods if m.split(".")[0] in FORBIDDEN]
    if found:
        raise Fail("no imports from " + ", ".join(sorted(FORBIDDEN)), ", ".join(found))


@check(4, 2, "checkout() places one order at the database's prices, lowers the stock, and empties the cart", needs=("orders exist",))
def checkout_op(ctx):
    token = session(ctx)
    a = new_product(ctx, "CHECK-BUY-A", stock=5, name="Buy A")
    b = new_product(ctx, "CHECK-BUY-B", stock=5, name="Buy B")
    ctx.psql(f"UPDATE products SET price_cents = 250 WHERE id = {b};")
    put_line(ctx, token, b, 1)
    put_line(ctx, token, a, 2)
    out = run_py(ctx, f"import orders\nout['order'] = orders.checkout('{token}').model_dump(mode='json')")
    order = out["order"]
    want_items = [
        {"product_id": a, "sku": "CHECK-BUY-A", "name": "Buy A", "quantity": 2, "price_cents": 1000, "line_total_cents": 2000},
        {"product_id": b, "sku": "CHECK-BUY-B", "name": "Buy B", "quantity": 1, "price_cents": 250, "line_total_cents": 250},
    ]
    if order.get("items") != want_items or order.get("total_cents") != 2250 or not isinstance(order.get("id"), int):
        raise Fail(short(json.dumps({"id": "…", "items": want_items, "total_cents": 2250}), 400), short(json.dumps(order), 400))
    if (stock_of(ctx, a), stock_of(ctx, b)) != (3, 4):
        raise Fail("stock 3 and 4 after the order", f"stock {stock_of(ctx, a)} and {stock_of(ctx, b)}")
    if counts(ctx, token) != ("1", "0"):
        raise Fail("one order for the session, and an empty cart", f"orders, cart lines: {counts(ctx, token)}")
    saved = ctx.sql_value(f"SELECT string_agg(product_id || 'x' || quantity || '@' || price_cents, ' ' ORDER BY product_id) "
                          f"FROM order_lines WHERE order_id = {order['id']}")
    if saved != f"{a}x2@1000 {b}x1@250":
        raise Fail(f"order_lines {a}x2@1000 {b}x1@250", saved or "no lines")


@check(4, 2, "an order keeps the price it was bought at, after the product's price changes", needs=("orders exist",))
def price_kept(ctx):
    token = session(ctx)
    pid = new_product(ctx, "CHECK-BUY-PRICE", stock=3)
    put_line(ctx, token, pid, 1)
    out = run_py(ctx, f"import orders\nout['order'] = orders.checkout('{token}').model_dump(mode='json')")
    ctx.psql(f"UPDATE products SET price_cents = 4321 WHERE id = {pid};")
    kept = ctx.sql_value(f"SELECT price_cents FROM order_lines WHERE order_id = {out['order']['id']}")
    if kept != "1000":
        raise Fail("order_lines.price_cents still 1000", kept, "Copy the price into the line when the order is placed.")


@check(4, 2, "checkout() refuses an empty cart, a short line or an unavailable line, with the contract's message, and changes nothing",
       needs=("orders exist",))
def checkout_refusals(ctx):
    empty = session(ctx)
    short_token, gone_token = session(ctx), session(ctx)
    ok = new_product(ctx, "CHECK-REFUSE-OK", stock=5, name="Refuse ok")
    low = new_product(ctx, "CHECK-REFUSE-LOW", stock=1, name="Refuse low")
    lower = new_product(ctx, "CHECK-REFUSE-LOWER", stock=0, name="Refuse lower")
    gone1 = new_product(ctx, "CHECK-REFUSE-GONE1", stock=5, name="Refuse gone one")
    gone2 = new_product(ctx, "CHECK-REFUSE-GONE2", stock=5, name="Refuse gone two")
    for pid, q in ((ok, 1), (low, 2), (lower, 1)):
        put_line(ctx, short_token, pid, q)
    for pid in (ok, gone1, gone2):
        put_line(ctx, gone_token, pid, 1)
    ctx.psql(f"UPDATE products SET archived_at = now() WHERE id IN ({gone1}, {gone2});")
    out = run_py(ctx, "import orders\n"
                      + raised(f"orders.checkout('{empty}')", "empty") + "\n"
                      + raised(f"orders.checkout('{short_token}')", "short") + "\n"
                      + raised(f"orders.checkout('{gone_token}')", "gone") + "\n"
                      + raised("orders.checkout(None)", "none"))
    want = {
        "empty": ["EmptyCart", EMPTY_CART],
        "short": ["InsufficientStock", f"{short_line(1, 'Refuse low')} {short_line(0, 'Refuse lower')}"],
        "gone": ["NotForSale", not_for_sale_any_more([("Refuse gone one", gone1), ("Refuse gone two", gone2)])],
        "none": ["NoSession", NO_TOKEN],
    }
    for key, w in want.items():
        if out[key] != w:
            raise Fail(f"{w[0]}('{w[1]}')", str(out[key]),
                       "Lines in product id order; one sentence per short line, joined with a space." if key == "short" else "")
    if stock_of(ctx, ok) != 5 or counts(ctx, short_token) != ("0", "3") or counts(ctx, gone_token) != ("0", "3"):
        raise Fail("nothing changed: stock 5, no orders, both carts still full",
                   f"stock {stock_of(ctx, ok)}, short cart {counts(ctx, short_token)}, archived cart {counts(ctx, gone_token)}",
                   "Raise inside the with block, so the transaction rolls back everything it did.")


# --- Step 3 · The three ways in ---


@check(4, 3, "POST /checkout: 201 with the order; 409 with the contract's message; 401; and it ignores a total the client sends",
       needs=("orders exist",))
def checkout_http(ctx):
    token, empty = session(ctx), session(ctx)
    pid = new_product(ctx, "CHECK-HTTP-BUY", stock=1, name="Http buy")
    put_line(ctx, token, pid, 1)
    status, body = http_json(ctx, "POST", "/checkout", json={"total_cents": 1}, **bearer(token))
    if status != 201 or body.get("total_cents") != 1000 or [l.get("quantity") for l in body.get("items", [])] != [1]:
        raise Fail("201, an order of 1, total_cents 1000 (not the 1 the client sent)", f"{status} {short(json.dumps(body), 300)}")
    other, gone_token = session(ctx), session(ctx)
    put_line(ctx, other, pid, 1)
    gone = new_product(ctx, "CHECK-HTTP-GONE", stock=5, name="Http gone")
    put_line(ctx, gone_token, gone, 1)
    ctx.psql(f"UPDATE products SET archived_at = now() WHERE id = {gone};")
    for label, tok, want in [("an empty cart", empty, (409, EMPTY_CART)), ("a sold-out line", other, (409, short_line(0, "Http buy"))),
                             ("an archived line", gone_token, (409, not_for_sale_any_more([("Http gone", gone)]))),
                             ("no token", None, (401, NO_TOKEN))]:
        status, body = http_json(ctx, "POST", "/checkout", **bearer(tok))
        if (status, body) != (want[0], {"detail": want[1]}):
            raise Fail(f'{label}: {want[0]} {{"detail": "{want[1]}"}}', f"{status} {short(json.dumps(body), 200)}")


@check(4, 3, "./store checkout and the checkout tool: the order, or the same messages with exit 4 or 5 and a tool error",
       needs=("orders exist",))
def checkout_cli_tool(ctx):
    token, empty = session(ctx), session(ctx)
    pid = new_product(ctx, "CHECK-CLI-BUY", stock=2, name="Cli buy")
    put_line(ctx, token, pid, 1)
    code, out, err = cli_json(ctx, "checkout", "--session", token)
    if code != 0 or not isinstance(out, dict) or out.get("total_cents") != 1000:
        raise Fail("exit 0, the order as JSON", f"exit {code}, {short(err or str(out), 200)}")
    gone_token = session(ctx)
    gone = new_product(ctx, "CHECK-CLI-GONE", stock=5, name="Cli gone")
    put_line(ctx, gone_token, gone, 1)
    ctx.psql(f"UPDATE products SET archived_at = now() WHERE id = {gone};")
    for args, want_code, want in [(("--session", empty), 4, EMPTY_CART), (("--session", gone_token), 4, not_for_sale_any_more([("Cli gone", gone)])),
                                  ((), 5, NO_TOKEN)]:
        code, out, err = cli_json(ctx, "checkout", *args)
        if (code, err) != (want_code, want):
            raise Fail(f"exit {want_code}, stderr: {want}", f"exit {code}, stderr {short(err, 200)!r}")
    buyer = session(ctx)
    put_line(ctx, buyer, pid, 1)
    is_error, body = tool(ctx, "checkout", {"session_token": buyer})
    if is_error or (body or {}).get("total_cents") != 1000:
        raise Fail("the tool returns the order", short(str(body), 200))
    late = session(ctx)
    put_line(ctx, late, pid, 1)
    is_error, body = tool(ctx, "checkout", {"session_token": late})
    if not is_error or short_line(0, "Cli buy") not in str(body):
        raise Fail(f"an error containing: {short_line(0, 'Cli buy')}", short(str(body), 200))


@check(4, 3, "parity: checkout has its route, its command and its tool", needs=("orders exist",))
def parity_m4(ctx):
    parity(ctx, 4)


# --- Step 4 · Two buyers at once ---


@check(4, 4, "the checkout race: 20 rounds of two buyers and one unit, each round one 201, one 409, stock 0", needs=("orders exist",))
def race(ctx):
    import race_test

    lines: list[str] = []
    ok = asyncio.run(race_test.race(ctx.base, 20, say=lines.append))
    if not ok:
        raise Fail("20/20 rounds: one 201, one 409, stock 0", " / ".join(lines[-4:])[:600],
                   "A 500 means the second buyer's stock change was refused by your CHECK: lock the rows before you read them.")


@check(4, 4, "the deadlock test: 500 rounds of two carts with the same two products, put in in opposite orders, all bought",
       needs=("orders exist",))
def deadlock(ctx):
    import deadlock_test

    lines: list[str] = []
    ok = asyncio.run(deadlock_test.test(ctx.base, 500, say=lines.append, env=ctx.env()))
    if not ok:
        raise Fail("500/500 rounds: two 201s, and no deadlocks", " / ".join(lines[-4:])[:600],
                   "Lock the rows in one order every time: ORDER BY p.id, before FOR UPDATE.")


# --- Step 6 · The audit of your harness ---


@check(4, 6, "your journal has the audit of your tutor harness, and your harness's rules log has at least one change")
def audit(ctx):
    journal = (ROOT / "JOURNAL.md").read_text() if (ROOT / "JOURNAL.md").exists() else ""
    m = re.search(r"^## M4 audit\s*$(.*?)(?=^## |\Z)", journal, re.M | re.S)
    words = len(re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S).split()) if m else 0
    if words < 150:
        raise Fail("a section ## M4 audit in JOURNAL.md, about half a page (150 words or more)", f"{words} words")
    home = Path(os.environ.get("TUTOR_HOME", Path.home() / "tutor"))
    log = home / "orchestrator" / "RULES-LOG.md"
    entries = re.findall(r"^### ", log.read_text().split("## Entries", 1)[-1], re.M) if log.exists() else []
    if not entries:
        raise Fail(f"at least one entry in {log}", "none", "Your audit has to produce one change, made through Tutor Orch.")

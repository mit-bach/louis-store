"""Milestone 5: retries with an Idempotency-Key, errors an agent can act on, the customer's agent, and evals."""

import asyncio
import fnmatch
import json
import os

from contract import ADMIN_TOOLS, CUSTOMER_TOOLS, EMPTY_CART, UNEXPECTED, short_line
from kitlib import ROOT, Fail, check, http_json, short
from m2 import cli_json, new_product, raised, run_py, tool
from m3 import bearer, put_line, session
from m4 import columns, counts, stock_of

AGENT = ROOT / "agents" / "customer"
SETTINGS = AGENT / ".claude" / "settings.json"
RUNS = ROOT / "checks" / "evals-runs.txt"


def order_count(ctx, token: str) -> str:
    return ctx.sql_value(f"SELECT count(*) FROM orders WHERE session_token = '{token}'")


# --- Step 1 · One key, one order ---


@check(5, 1, "orders has idempotency_key, and the database refuses a second order with the same session and key",
       needs=("orders exist",), gives="keys exist")
def key_column(ctx):
    col = columns(ctx, "orders").get("idempotency_key")
    if col != ["text", "YES"]:
        raise Fail("a column idempotency_key, TEXT, that may be empty (NULL)", str(col or "no such column"))
    a, b = session(ctx), session(ctx)
    twice = ctx.psql(f"INSERT INTO orders (session_token, total_cents, idempotency_key) VALUES ('{a}', 1, 'k');\n"
                     f"INSERT INTO orders (session_token, total_cents, idempotency_key) VALUES ('{a}', 1, 'k');",
                     single_transaction=True)
    if twice.returncode == 0:
        raise Fail("a second order with the same session and key is refused", "it was saved",
                   "A UNIQUE constraint over (session_token, idempotency_key).")
    others = ctx.psql(f"INSERT INTO orders (session_token, total_cents, idempotency_key) VALUES ('{a}', 1, 'k');\n"
                      f"INSERT INTO orders (session_token, total_cents, idempotency_key) VALUES ('{b}', 1, 'k');\n"
                      f"INSERT INTO orders (session_token, total_cents) VALUES ('{a}', 1);\n"
                      f"INSERT INTO orders (session_token, total_cents) VALUES ('{a}', 1);", single_transaction=True)
    if others.returncode != 0:
        raise Fail("the same key in another session, and any number of orders without a key, are all saved",
                   short(others.stderr), "The key is unique within a session, not across the whole table.")


@check(5, 1, "checkout(token, key) twice: the same order back, one order placed, the stock lowered once", needs=("keys exist",))
def retry_op(ctx):
    token = session(ctx)
    pid = new_product(ctx, "CHECK-RETRY-OP", stock=5, name="Retry op")
    put_line(ctx, token, pid, 2)
    out = run_py(ctx, f"import orders\nout['first'] = orders.checkout('{token}', 'key-1').model_dump(mode='json')\n"
                      f"out['again'] = orders.checkout('{token}', 'key-1').model_dump(mode='json')")
    if out["first"] != out["again"]:
        raise Fail("the second call returns the first order, exactly",
                   f"first {short(json.dumps(out['first']), 200)}, then {short(json.dumps(out['again']), 200)}",
                   "Look the key up before anything else is checked: the cart is already empty the second time.")
    if (stock_of(ctx, pid), order_count(ctx, token)) != (3, "1"):
        raise Fail("one order, and the stock 5 → 3", f"{order_count(ctx, token)} order(s), stock {stock_of(ctx, pid)}")


@check(5, 1, "a key belongs to its session; without a key, checkout is as in M4; a refused checkout records nothing",
       needs=("keys exist",))
def key_scope(ctx):
    a, b = session(ctx), session(ctx)
    pa = new_product(ctx, "CHECK-KEY-A", stock=5, name="Key a")
    pb = new_product(ctx, "CHECK-KEY-B", stock=5, name="Key b")
    put_line(ctx, a, pa, 1)
    put_line(ctx, b, pb, 1)
    out = run_py(ctx, f"import orders\nout['a'] = orders.checkout('{a}', 'same-key').model_dump(mode='json')\n"
                      f"out['b'] = orders.checkout('{b}', 'same-key').model_dump(mode='json')")
    if out["a"]["id"] == out["b"]["id"] or [line["product_id"] for line in out["b"]["items"]] != [pb]:
        raise Fail("two sessions using the same key each get their own order", short(json.dumps(out["b"]), 300),
                   "Look the key up together with the session's token. Another customer's key isn't yours.")
    c = session(ctx)
    put_line(ctx, c, pa, 1)
    out = run_py(ctx, f"import orders\norders.checkout('{c}')\n" + raised(f"orders.checkout('{c}')", "again"))
    if out["again"] != ["EmptyCart", EMPTY_CART]:
        raise Fail(f"without a key, a second checkout raises EmptyCart('{EMPTY_CART}')", str(out["again"]))
    d = session(ctx)
    low = new_product(ctx, "CHECK-KEY-LOW", stock=1, name="Key low")
    put_line(ctx, d, low, 2)
    out = run_py(ctx, "import orders\n" + raised(f"orders.checkout('{d}', 'fix-me')", "refused"))
    ctx.psql(f"UPDATE cart_items SET quantity = 1 WHERE session_token = '{d}';")
    after = run_py(ctx, f"import orders\nout['order'] = orders.checkout('{d}', 'fix-me').model_dump(mode='json')")
    if out["refused"] != ["InsufficientStock", short_line(1, "Key low")] or \
            [line["quantity"] for line in after["order"]["items"]] != [1]:
        raise Fail("refused, then, with the cart fixed, the same key places the order",
                   f"{out['refused']}, then {short(json.dumps(after['order']), 200)}",
                   "Only an order records its key. A refusal changes nothing, so the key is still free.")


# --- Step 2 · Retries, three ways in, and at the same instant ---


@check(5, 2, "the Idempotency-Key header, --idempotency-key and the tool's idempotency_key: the same key twice, the same order",
       needs=("keys exist",))
def retry_three_ways(ctx):
    pid = new_product(ctx, "CHECK-RETRY-WAYS", stock=10, name="Retry ways")
    t = session(ctx)
    put_line(ctx, t, pid, 1)
    head = {"headers": {"Authorization": f"Bearer {t}", "Idempotency-Key": "http-key"}}
    (s1, b1), (s2, b2) = http_json(ctx, "POST", "/checkout", **head), http_json(ctx, "POST", "/checkout", **head)
    if (s1, s2) != (201, 201) or b1 != b2:
        raise Fail("POST /checkout twice with one Idempotency-Key: 201 both times, the same order",
                   f"{s1}, then {s2} {short(json.dumps(b2), 200)}")
    t = session(ctx)
    put_line(ctx, t, pid, 1)
    first = cli_json(ctx, "checkout", "--session", t, "--idempotency-key", "cli-key")
    again = cli_json(ctx, "checkout", "--session", t, "--idempotency-key", "cli-key")
    if first[0] != 0 or first[:2] != again[:2]:
        raise Fail("./store checkout twice with one --idempotency-key: exit 0 both times, the same order",
                   f"exit {first[0]}, then exit {again[0]} {short(str(again[1] or again[2]), 200)}")
    t = session(ctx)
    put_line(ctx, t, pid, 1)
    one = tool(ctx, "checkout", {"session_token": t, "idempotency_key": "tool-key"})
    two = tool(ctx, "checkout", {"session_token": t, "idempotency_key": "tool-key"})
    if one[0] or two[0] or one[1] != two[1]:
        raise Fail("the checkout tool twice with one idempotency_key: the same order", short(str(two[1]), 200))
    if stock_of(ctx, pid) != 7:
        raise Fail("three orders in all, and the stock 10 → 7", f"stock {stock_of(ctx, pid)}")


def run_retry(ctx, via: str, rounds: int):
    import retry_test

    lines: list[str] = []
    if not asyncio.run(retry_test.retry(via, ctx.base, rounds, say=lines.append, env=ctx.env())):
        raise Fail(f"{rounds}/{rounds} rounds: one order, both answers the same, stock lowered once",
                   " / ".join(lines[-4:])[:600],
                   "Look the key up right after your locking read, in the same transaction, before the cart is checked.")


@check(5, 2, "the retry test through HTTP: 20 rounds, each checkout sent twice with one key", needs=("keys exist",))
def retry_http(ctx):
    run_retry(ctx, "http", 20)


@check(5, 2, "the retry test through ./store: 6 rounds", needs=("keys exist",))
def retry_cli(ctx):
    run_retry(ctx, "cli", 6)


@check(5, 2, "the retry test through the tools: 10 rounds", needs=("keys exist",))
def retry_tools(ctx):
    run_retry(ctx, "tools", 10)


# --- Step 3 · What an agent reads ---


@check(5, 3, "when something breaks, every way in answers with the contract's message, never a traceback, and nothing changes",
       needs=("keys exist",))
def unexpected(ctx):
    t = session(ctx)
    pid = new_product(ctx, "CHECK-CRASH", stock=5, name="Crash")
    put_line(ctx, t, pid, 1)
    broke = ctx.psql("ALTER TABLE order_lines RENAME TO order_lines_gone;")
    if broke.returncode != 0:
        raise Fail("the check can hide the order_lines table for a moment", short(broke.stderr))
    try:
        http = http_json(ctx, "POST", "/checkout", **bearer(t))
        code, _, err = cli_json(ctx, "checkout", "--session", t)
        is_error, text = tool(ctx, "checkout", {"session_token": t})
    finally:
        ctx.psql("ALTER TABLE order_lines_gone RENAME TO order_lines;")
    problems = []
    if http != (500, {"detail": UNEXPECTED}):
        problems.append(f"HTTP: {http[0]} {short(str(http[1]), 150)}")
    if (code, err) != (1, UNEXPECTED):
        problems.append(f"./store: exit {code}, stderr {short(err, 150)!r}")
    if not is_error or UNEXPECTED not in str(text) or "order_lines" in str(text):
        problems.append(f"tool: {short(str(text), 150)}")
    if problems:
        raise Fail(f'HTTP 500 {{"detail": "{UNEXPECTED}"}}; ./store exit 1 with that line alone on stderr; '
                   "a tool error with that message", "; ".join(problems),
                   "An exception handler in main.py, a catch around app() in cli.py, and a wrapper around every tool.")
    if (stock_of(ctx, pid), counts(ctx, t)) != (5, ("0", "1")):
        raise Fail("nothing changed: stock 5, no order, the cart still full",
                   f"stock {stock_of(ctx, pid)}, orders and cart lines {counts(ctx, t)}")


@check(5, 3, "each cart line says in_stock: whether its quantity is in stock right now, through every way in",
       needs=("keys exist",))
def in_stock(ctx):
    t = session(ctx)
    a = new_product(ctx, "CHECK-INSTOCK-A", stock=5, name="In stock a")
    b = new_product(ctx, "CHECK-INSTOCK-B", stock=5, name="In stock b")
    c = new_product(ctx, "CHECK-INSTOCK-C", stock=4, name="In stock c")
    put_line(ctx, t, a, 2)
    put_line(ctx, t, b, 3)
    put_line(ctx, t, c, 4)
    ctx.psql(f"UPDATE products SET stock = 2 WHERE id = {b};")
    want = [[a, True, True], [b, False, True], [c, True, True]]
    out = run_py(ctx, f"import cart\nout['cart'] = cart.get_cart('{t}').model_dump(mode='json')")
    got = {"get_cart()": out["cart"], "GET /cart": http_json(ctx, "GET", "/cart", **bearer(t))[1],
           "./store cart show": cli_json(ctx, "cart", "show", "--session", t)[1],
           "the get_cart tool": tool(ctx, "get_cart", {"session_token": t})[1]}
    for way, cart in got.items():
        lines = [[line.get("product_id"), line.get("in_stock"), line.get("available")] for line in (cart or {}).get("items", [])]
        if lines != want or cart.get("total_cents") != 9000:
            raise Fail(f"{way}: in_stock true for 2 of 5 and for 4 of 4, false for 3 of 2; all available; total_cents 9000",
                       short(json.dumps(cart), 300), "in_stock is quantity <= stock, read in the same query as the line.")


# --- Step 4 · What a customer's agent gets ---


def settings(ctx) -> dict:
    if "settings" not in ctx.notes_cache:
        try:
            ctx.notes_cache["settings"] = json.loads(SETTINGS.read_text())
        except (OSError, ValueError) as e:
            raise Fail("agents/customer/.claude/settings.json, valid JSON", f"{type(e).__name__}: {e}")
    return ctx.notes_cache["settings"]


@check(5, 4, "agents/customer has the customer agent's brief, in your words, its tool server, and its settings",
       gives="customer agent")
def customer_files(ctx):
    brief = AGENT / "CLAUDE.md"
    if not brief.exists() or len(brief.read_text().split()) < 60:
        raise Fail("agents/customer/CLAUDE.md, at least 60 words", f"{len(brief.read_text().split()) if brief.exists() else 'no'} words")
    try:
        server = json.loads((AGENT / ".mcp.json").read_text())["mcpServers"]["store"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise Fail('agents/customer/.mcp.json with a server called "store"', f"{type(e).__name__}: {e}")
    url = f"http://localhost:{os.environ.get('API_PORT', '8000')}/mcp"
    if server.get("type") != "http" or server.get("url") != url:
        raise Fail(f'{{"type": "http", "url": "{url}"}}', json.dumps(server))
    settings(ctx)


@check(5, 4, "its permissions: every customer tool allowed; the shell, the web and every admin tool denied",
       needs=("customer agent",))
def customer_permissions(ctx):
    p = settings(ctx).get("permissions", {})
    allow, deny = set(p.get("allow", [])), set(p.get("deny", []))

    async def calls(client):
        return {t.name for t in (await client.list_tools()).tools}

    exists = ctx.tools(calls)
    missing = [f"allow mcp__store__{t}" for t in CUSTOMER_TOOLS if t in exists and f"mcp__store__{t}" not in allow]
    missing += [f"deny {rule}" for rule in ["Bash", "WebFetch", "WebSearch"] + [f"mcp__store__{t}" for t in ADMIN_TOOLS]
                if rule not in deny]
    too_much = sorted(rule for rule in allow if rule in ("mcp__store", "mcp__store__*", "Bash") or
                      any(rule == f"mcp__store__{t}" for t in ADMIN_TOOLS))
    if missing or too_much:
        raise Fail("the customer tools allowed, and Bash, WebFetch, WebSearch and the admin tools denied",
                   "; ".join(missing + [f"allows {r}" for r in too_much]),
                   "Allow each customer tool by its full name. A bare mcp__store would allow the admin tools too.")


@check(5, 4, "every tool your store has is either allowed or denied for the customer agent", needs=("customer agent",))
def every_tool_decided(ctx):
    p = settings(ctx).get("permissions", {})
    decided = set(p.get("allow", [])) | set(p.get("deny", [])) | set(p.get("ask", []))

    async def calls(client):
        return sorted(t.name for t in (await client.list_tools()).tools)

    left = [name for name in ctx.tools(calls) if f"mcp__store__{name}" not in decided]
    if left:
        raise Fail("no tool left to chance", "not in allow or deny: " + ", ".join(left),
                   "A new tool needs a decision too: is it a customer's, or the store's?")


@check(5, 4, "the customer agent doesn't load your developer rules: the top CLAUDE.md is excluded, its own isn't",
       needs=("customer agent",))
def no_developer_rules(ctx):
    patterns = settings(ctx).get("claudeMdExcludes", [])
    top, own = str(ROOT / "CLAUDE.md"), str(AGENT / "CLAUDE.md")
    if not any(fnmatch.fnmatch(top, p) for p in patterns) or any(fnmatch.fnmatch(own, p) for p in patterns):
        raise Fail(f"claudeMdExcludes matches {top}, and not {own}", json.dumps(patterns),
                   'For example "**/store/CLAUDE.md": a CLAUDE.md directly inside a folder called store.')


# --- Step 5 · Evals ---


@check(5, 5, "checks/evals-runs.txt has your eval runs: at least two, against two versions of your tool descriptions",
       needs=("customer agent",))
def evals_ran(ctx):
    lines = [line for line in (RUNS.read_text().splitlines() if RUNS.exists() else []) if " · score " in line]
    versions = {line.split("descriptions ")[1].split(" ")[0] for line in lines if "descriptions " in line}
    if len(lines) < 2 or len(versions) < 2:
        raise Fail("two runs or more, with two different description fingerprints",
                   f"{len(lines)} run(s), {len(versions)} version(s) of your descriptions",
                   "uv run checks/evals.py, then again after you change your tool descriptions.")

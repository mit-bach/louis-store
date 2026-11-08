"""Milestone 3: visitor sessions, the cart, and the reviewer as a skill."""

import ast
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from contract import BAD_TOKEN, EXPIRED, NO_TOKEN, cart_too_many, not_for_sale, not_found, parity
from kitlib import ROOT, Fail, check, http_json, short
from m2 import cli_json, new_product, raised, run_py, tool

MISSING_ID = 999999
FORBIDDEN = {"fastapi", "starlette", "typer", "click", "mcp", "httpx", "uvicorn"}
EMPTY = {"items": [], "total_cents": 0}


def session(ctx, expired: bool = False) -> str:
    """A session made straight in the throwaway database: live, or already expired."""
    token = f"check-{os.urandom(12).hex()}"
    when = "now() - interval '1 minute'" if expired else "now() + interval '1 hour'"
    r = ctx.psql(f"INSERT INTO sessions (token, expires_at) VALUES ('{token}', {when});")
    if r.returncode != 0:
        raise Fail("a test session can be inserted", short(r.stderr))
    return token


def put_line(ctx, token: str, product_id: int, quantity: int) -> None:
    r = ctx.psql(f"INSERT INTO cart_items (session_token, product_id, quantity) VALUES ('{token}', {product_id}, {quantity});")
    if r.returncode != 0:
        raise Fail("a test cart line can be inserted", short(r.stderr))


def bearer(token: str | None) -> dict:
    return {"headers": {"Authorization": f"Bearer {token}"}} if token else {}


# --- Step 1 · Sessions ---


@check(3, 1, "sessions.py and cart.py import nothing from the web, the command line or the tool server")
def no_web_imports(ctx):
    found = []
    for name in ("sessions.py", "cart.py"):
        path = ROOT / "backend" / name
        if not path.exists():
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            found += [f"{name}: {m}" for m in mods if m.split(".")[0] in FORBIDDEN]
    if found:
        raise Fail("no imports from " + ", ".join(sorted(FORBIDDEN)), "; ".join(found))


@check(3, 1, "the sessions table: a token as its key, and when it expires", needs=("your seed is in",), gives="sessions exist")
def sessions_table(ctx):
    got = ctx.sql_value(
        "SELECT string_agg(column_name || ' ' || data_type || ' ' || is_nullable, ', ' ORDER BY column_name) "
        "FROM information_schema.columns WHERE table_name = 'sessions' AND column_name IN ('token', 'expires_at')"
    )
    if got != "expires_at timestamp with time zone NO, token text NO":
        raise Fail("token text NOT NULL, expires_at timestamp with time zone NOT NULL", got or "no table sessions")
    key = ctx.sql_value(
        "SELECT string_agg(a.attname, ',') FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid "
        "AND a.attnum = ANY(i.indkey) WHERE i.indrelid = 'sessions'::regclass AND i.indisprimary"
    )
    if key != "token":
        raise Fail("the primary key is token", key or "no primary key")


@check(3, 1, "start_session() makes a long random token, valid for an hour", needs=("sessions exist",))
def start_op(ctx):
    out = run_py(ctx, "import sessions\na = sessions.start_session()\nb = sessions.start_session()\n"
                      "out['a'] = a.model_dump(mode='json')\nout['b'] = b.model_dump(mode='json')")
    a, b = out["a"], out["b"]
    if set(a) != {"token", "expires_at"}:
        raise Fail("a Session with token and expires_at", short(json.dumps(a), 200))
    if a["token"] == b["token"] or len(a["token"]) < 32 or not re.fullmatch(r"[A-Za-z0-9_-]+", a["token"]):
        raise Fail("a different, URL-safe token of 32 characters or more each time", f"{a['token']!r}, {b['token']!r}",
                   "secrets.token_urlsafe(32)")
    left = datetime.fromisoformat(a["expires_at"].replace("Z", "+00:00")) - datetime.now(timezone.utc)
    if not timedelta(minutes=55) < left < timedelta(minutes=65):
        raise Fail("expires_at about an hour from now", f"{left} from now")


@check(3, 1, "require_session() names what's wrong: no token, a made-up token, an expired one", needs=("sessions exist",))
def require_op(ctx):
    live, old = session(ctx), session(ctx, expired=True)
    out = run_py(ctx, "import sessions\n"
                      + raised("sessions.require_session(None)", "none") + "\n"
                      + raised("sessions.require_session('made-up-token')", "bad") + "\n"
                      + raised(f"sessions.require_session('{old}')", "old") + "\n"
                      + f"out['live'] = sessions.require_session('{live}')")
    for key, want in (("none", NO_TOKEN), ("bad", BAD_TOKEN), ("old", EXPIRED)):
        if out[key] != ["NoSession", want]:
            raise Fail(f"NoSession('{want}')", str(out[key]))
    if out["live"] != live:
        raise Fail("the token back, for a live session", str(out["live"]))


@check(3, 1, "POST /sessions, ./store session start and the start_session tool each start a session", needs=("sessions exist",))
def start_ways(ctx):
    status, body = http_json(ctx, "POST", "/sessions")
    if status != 201 or set(body) != {"token", "expires_at"}:
        raise Fail('201 {"token": …, "expires_at": …}', f"{status} {short(json.dumps(body), 200)}")
    code, out, err = cli_json(ctx, "session", "start")
    if code != 0 or not isinstance(out, dict) or set(out) != {"token", "expires_at"}:
        raise Fail("exit 0, and the session as JSON", f"exit {code}, {short(err or str(out), 200)}")
    is_error, made = tool(ctx, "start_session", {})
    if is_error or set(made or {}) != {"token", "expires_at"}:
        raise Fail("the tool returns the session", short(str(made), 200))
    tokens = {body["token"], out["token"], made["token"]}
    if len(tokens) != 3 or ctx.sql_value(f"SELECT count(*) FROM sessions WHERE token IN ({', '.join(repr(t) for t in tokens)})") != "3":
        raise Fail("three different tokens, each saved in the sessions table", str(tokens))


# --- Step 2 · The cart table, and reading a cart ---


@check(3, 2, "the cart_items table: one line per session and product, a quantity above zero, and lines that go with their session",
       needs=("sessions exist",), gives="cart_items exist")
def cart_table(ctx):
    token = session(ctx)
    pid = new_product(ctx, "CHECK-CART-TABLE", stock=5)
    put_line(ctx, token, pid, 2)
    for sql, what in [
        (f"INSERT INTO cart_items (session_token, product_id, quantity) VALUES ('{token}', {pid}, 3);", "a second line for the same product"),
        (f"INSERT INTO cart_items (session_token, product_id, quantity) VALUES ('{token}', {MISSING_ID}, 1);", "a line for a product that doesn't exist"),
        (f"INSERT INTO cart_items (session_token, product_id, quantity) VALUES ('no-such-session', {pid}, 1);", "a line for a session that doesn't exist"),
        (f"UPDATE cart_items SET quantity = 0 WHERE session_token = '{token}';", "a quantity of 0"),
    ]:
        r = ctx.psql(f"BEGIN;\n{sql}\nROLLBACK;")
        if r.returncode == 0:
            raise Fail(f"the database refuses {what}", "it was accepted",
                       "A primary key on (session_token, product_id), two foreign keys, and a CHECK.")
    ctx.psql(f"DELETE FROM sessions WHERE token = '{token}';")
    if ctx.sql_value(f"SELECT count(*) FROM cart_items WHERE session_token = '{token}'") != "0":
        raise Fail("deleting a session deletes its cart lines", "the lines are still there", "ON DELETE CASCADE")


@check(3, 2, "get_cart() joins each line to its product, totals it, and leaves archived products out of the total", needs=("cart_items exist",))
def get_cart_op(ctx):
    token = session(ctx)
    a = new_product(ctx, "CHECK-CART-A", stock=9, name="Cart A")
    b = new_product(ctx, "CHECK-CART-B", stock=9, name="Cart B")
    put_line(ctx, token, b, 3)
    put_line(ctx, token, a, 2)
    ctx.psql(f"UPDATE products SET archived_at = now() WHERE id = {b};")
    out = run_py(ctx, f"import cart\nout['empty'] = cart.get_cart('{session(ctx)}').model_dump(mode='json')\n"
                      f"out['cart'] = cart.get_cart('{token}').model_dump(mode='json')")
    if out["empty"] != EMPTY:
        raise Fail(json.dumps(EMPTY), json.dumps(out["empty"]))
    want = {"items": [
        {"product_id": a, "sku": "CHECK-CART-A", "name": "Cart A", "price_cents": 1000, "quantity": 2, "line_total_cents": 2000, "available": True},
        {"product_id": b, "sku": "CHECK-CART-B", "name": "Cart B", "price_cents": 1000, "quantity": 3, "line_total_cents": 3000, "available": False},
    ], "total_cents": 2000}
    for line in out["cart"]["items"]:
        line.pop("in_stock", None)  # M5 adds it; this check is about M3's fields
    if out["cart"] != want:
        raise Fail(short(json.dumps(want), 500), short(json.dumps(out["cart"]), 500),
                   "Lines sorted by product id; an archived product's line has available: false and isn't in the total.")


@check(3, 2, "GET /cart: 200 with a live token; 401 with the contract's message without one, or with a bad or expired one",
       needs=("cart_items exist",))
def get_cart_http(ctx):
    token = session(ctx)
    status, body = http_json(ctx, "GET", "/cart", **bearer(token))
    if (status, body) != (200, EMPTY):
        raise Fail(f"200 {json.dumps(EMPTY)}", f"{status} {short(json.dumps(body), 200)}")
    for label, kw, want in [("no header", {}, NO_TOKEN), ("a made-up token", bearer("made-up-token"), BAD_TOKEN),
                            ("an expired token", bearer(session(ctx, expired=True)), EXPIRED)]:
        status, body = http_json(ctx, "GET", "/cart", **kw)
        if (status, body) != (401, {"detail": want}):
            raise Fail(f'{label}: 401 {{"detail": "{want}"}}', f"{status} {short(json.dumps(body), 200)}")


@check(3, 2, "./store cart show and the get_cart tool: the cart with a live token, the same three messages without one",
       needs=("cart_items exist",))
def get_cart_cli_tool(ctx):
    token, old = session(ctx), session(ctx, expired=True)
    code, out, err = cli_json(ctx, "cart", "show", "--session", token)
    if (code, out) != (0, EMPTY):
        raise Fail(f"exit 0, {json.dumps(EMPTY)}", f"exit {code}, {short(err or str(out), 200)}")
    for label, args, want in [("no --session", [], NO_TOKEN), ("a made-up token", ["--session", "made-up-token"], BAD_TOKEN),
                              ("an expired token", ["--session", old], EXPIRED)]:
        code, out, err = cli_json(ctx, "cart", "show", *args)
        if (code, err) != (5, want):
            raise Fail(f"{label}: exit 5, stderr: {want}", f"exit {code}, stderr {short(err, 200)!r}")
    is_error, body = tool(ctx, "get_cart", {"session_token": token})
    if is_error or body != EMPTY:
        raise Fail(f"the tool returns {json.dumps(EMPTY)}", short(str(body), 200))
    for label, args, want in [("no session_token", {}, NO_TOKEN), ("a made-up token", {"session_token": "made-up-token"}, BAD_TOKEN),
                              ("an expired token", {"session_token": old}, EXPIRED)]:
        is_error, body = tool(ctx, "get_cart", args)
        if not is_error or want not in str(body):
            raise Fail(f"{label}: an error containing: {want}", short(str(body), 200))


# --- Step 3 · Putting things in the cart ---


@check(3, 3, "set_cart_item() sets a line's quantity, replaces it the second time, and refuses what can't be sold",
       needs=("cart_items exist",))
def set_op(ctx):
    token = session(ctx)
    pid = new_product(ctx, "CHECK-SET-OP", stock=4, name="Set lamp")
    gone = new_product(ctx, "CHECK-SET-GONE", stock=4)
    ctx.psql(f"UPDATE products SET archived_at = now() WHERE id = {gone};")
    out = run_py(ctx, f"import cart\nfirst = cart.set_cart_item('{token}', {pid}, 2)\nsecond = cart.set_cart_item('{token}', {pid}, 3)\n"
                      "out['first'] = first.model_dump(mode='json')\nout['second'] = second.model_dump(mode='json')\n"
                      + raised(f"cart.set_cart_item('{token}', {pid}, 5)", "too_many") + "\n"
                      + raised(f"cart.set_cart_item('{token}', {MISSING_ID}, 1)", "missing") + "\n"
                      + raised(f"cart.set_cart_item('{token}', {gone}, 1)", "archived") + "\n"
                      + raised(f"cart.set_cart_item('made-up-token', {pid}, 1)", "bad") + "\n"
                      + f"out['removed'] = cart.remove_cart_item('{token}', {pid}).model_dump(mode='json')\n"
                      + f"out['removed_again'] = cart.remove_cart_item('{token}', {pid}).model_dump(mode='json')")
    lines = out["second"]["items"]
    if [l["quantity"] for l in out["first"]["items"]] != [2] or [l["quantity"] for l in lines] != [3]:
        raise Fail("one line, quantity 2, then the same line with quantity 3", f"{out['first']['items']} then {lines}",
                   "INSERT … ON CONFLICT (session_token, product_id) DO UPDATE SET quantity = EXCLUDED.quantity")
    for key, want in [("too_many", ["InsufficientStock", cart_too_many(4, "Set lamp", 5)]),
                      ("missing", ["ProductNotFound", not_found(MISSING_ID)]),
                      ("archived", ["ProductNotFound", not_for_sale(gone)]),
                      ("bad", ["NoSession", BAD_TOKEN])]:
        if out[key] != want:
            raise Fail(f"{want[0]}('{want[1]}')", str(out[key]))
    if out["removed"] != EMPTY or out["removed_again"] != EMPTY:
        raise Fail("remove_cart_item() empties the line, and removing it again changes nothing",
                   f"{out['removed']}, then {out['removed_again']}")


@check(3, 3, "PUT and DELETE /cart/items/{id}: the cart back, 422 for quantity 0, 409, 404 and 401 with their messages",
       needs=("cart_items exist",))
def set_http(ctx):
    token = session(ctx)
    pid = new_product(ctx, "CHECK-SET-HTTP", stock=3, name="Set pot")
    gone = new_product(ctx, "CHECK-SET-HTTP-GONE", stock=3)
    ctx.psql(f"UPDATE products SET archived_at = now() WHERE id = {gone};")
    status, body = http_json(ctx, "PUT", f"/cart/items/{pid}", json={"quantity": 2}, **bearer(token))
    if status != 200 or [(l["product_id"], l["quantity"]) for l in body.get("items", [])] != [(pid, 2)] or body.get("total_cents") != 2000:
        raise Fail("200, one line of 2, total_cents 2000", f"{status} {short(json.dumps(body), 300)}")
    status, body = http_json(ctx, "PUT", f"/cart/items/{pid}", json={"quantity": 1}, **bearer(token))
    if [(l["product_id"], l["quantity"]) for l in body.get("items", [])] != [(pid, 1)]:
        raise Fail("the same line, now with quantity 1", short(json.dumps(body), 300))
    for label, path, sent, kw, want in [
        ("quantity 0", f"/cart/items/{pid}", {"quantity": 0}, bearer(token), (422, None)),
        ("more than in stock", f"/cart/items/{pid}", {"quantity": 4}, bearer(token), (409, cart_too_many(3, "Set pot", 4))),
        ("a missing product", f"/cart/items/{MISSING_ID}", {"quantity": 1}, bearer(token), (404, not_found(MISSING_ID))),
        ("an archived product", f"/cart/items/{gone}", {"quantity": 1}, bearer(token), (404, not_for_sale(gone))),
        ("no token", f"/cart/items/{pid}", {"quantity": 1}, {}, (401, NO_TOKEN)),
    ]:
        status, body = http_json(ctx, "PUT", path, json=sent, **kw)
        if status != want[0] or (want[1] and body != {"detail": want[1]}):
            raise Fail(f"{label}: {want[0]}" + (f' {{"detail": "{want[1]}"}}' if want[1] else ""), f"{status} {short(json.dumps(body), 200)}")
    status, body = http_json(ctx, "DELETE", f"/cart/items/{pid}", **bearer(token))
    if (status, body) != (200, EMPTY):
        raise Fail(f"DELETE: 200 {json.dumps(EMPTY)}", f"{status} {short(json.dumps(body), 200)}")


@check(3, 3, "./store cart set and remove, and the set_cart_item and remove_cart_item tools: the same results and errors",
       needs=("cart_items exist",))
def set_cli_tool(ctx):
    token = session(ctx)
    pid = new_product(ctx, "CHECK-SET-CLI", stock=2, name="Set mug")
    code, out, err = cli_json(ctx, "cart", "set", str(pid), "2", "--session", token)
    if code != 0 or not isinstance(out, dict) or [l["quantity"] for l in out.get("items", [])] != [2]:
        raise Fail("exit 0, one line of 2", f"exit {code}, {short(err or str(out), 200)}")
    for args, want_code, want in [
        ((str(pid), "0", "--session", token), 2, "quantity"),
        ((str(pid), "3", "--session", token), 4, cart_too_many(2, "Set mug", 3)),
        ((str(MISSING_ID), "1", "--session", token), 3, not_found(MISSING_ID)),
        ((str(pid), "1"), 5, NO_TOKEN),
    ]:
        code, out, err = cli_json(ctx, "cart", "set", *args)
        if code != want_code or want not in err:
            raise Fail(f"exit {want_code}, stderr containing {want!r}", f"exit {code}, stderr {short(err, 200)!r}")
    code, out, err = cli_json(ctx, "cart", "remove", str(pid), "--session", token)
    if (code, out) != (0, EMPTY):
        raise Fail(f"remove: exit 0, {json.dumps(EMPTY)}", f"exit {code}, {short(err or str(out), 200)}")
    is_error, body = tool(ctx, "set_cart_item", {"session_token": token, "product_id": pid, "quantity": 1})
    if is_error or [l["quantity"] for l in (body or {}).get("items", [])] != [1]:
        raise Fail("set_cart_item: the cart, one line of 1", short(str(body), 200))
    for args, want in [({"session_token": token, "product_id": pid, "quantity": 0}, "quantity"),
                       ({"session_token": token, "product_id": pid, "quantity": 3}, cart_too_many(2, "Set mug", 3)),
                       ({"product_id": pid, "quantity": 1}, NO_TOKEN)]:
        is_error, body = tool(ctx, "set_cart_item", args)
        if not is_error or want not in str(body):
            raise Fail(f"set_cart_item {json.dumps(args)[:80]}: an error containing {want!r}", short(str(body), 200))
    is_error, body = tool(ctx, "remove_cart_item", {"session_token": token, "product_id": pid})
    if is_error or body != EMPTY:
        raise Fail(f"remove_cart_item: {json.dumps(EMPTY)}", short(str(body), 200))


@check(3, 3, "parity: the session and cart operations each have a route, a command and a tool", needs=("cart_items exist",))
def parity_m3(ctx):
    parity(ctx, 3)


# --- Step 4 · Two customers ---


@check(3, 4, "two sessions have two carts: what one puts in, the other doesn't see", needs=("cart_items exist",))
def carts_apart(ctx):
    a_token, b_token = session(ctx), session(ctx)
    one = new_product(ctx, "CHECK-APART-1", stock=5)
    two = new_product(ctx, "CHECK-APART-2", stock=5)
    http_json(ctx, "PUT", f"/cart/items/{one}", json={"quantity": 1}, **bearer(a_token))
    http_json(ctx, "PUT", f"/cart/items/{two}", json={"quantity": 2}, **bearer(b_token))
    _, a = http_json(ctx, "GET", "/cart", **bearer(a_token))
    _, b = http_json(ctx, "GET", "/cart", **bearer(b_token))
    got = ([(l["product_id"], l["quantity"]) for l in a.get("items", [])], [(l["product_id"], l["quantity"]) for l in b.get("items", [])])
    if got != ([(one, 1)], [(two, 2)]):
        raise Fail(f"cart A: [({one}, 1)], cart B: [({two}, 2)]", f"cart A: {got[0]}, cart B: {got[1]}",
                   "Every cart query needs WHERE session_token = %s.")


# --- Step 5 · The reviewer, as a skill ---


@check(3, 5, "your tutor harness has the reviewer as a skill, with a name and a description that says when to use it")
def reviewer_skill(ctx):
    home = Path(os.environ.get("TUTOR_HOME", Path.home() / "tutor"))
    skills = sorted((home / ".claude" / "skills").glob("*/SKILL.md"))
    found = []
    for path in skills:
        text = path.read_text()
        head = re.match(r"---\n(.*?)\n---\n", text, re.S)
        if not head:
            continue
        fields = dict(line.split(":", 1) for line in head.group(1).splitlines() if ":" in line)
        if "review" in fields.get("description", "").lower() and "CONTRACT.md" in text:
            found.append((path, fields))
    if not found:
        raise Fail(f"a skill in {home / '.claude' / 'skills'} whose description mentions reviewing, and whose instructions use CONTRACT.md",
                   ", ".join(str(p.parent.name) for p in skills) or "no skills there",
                   "SKILL.md starts with --- name: … description: … ---, then the instructions.")
    path, fields = found[0]
    if fields.get("name", "").strip() != path.parent.name:
        raise Fail(f"name: {path.parent.name}, the skill's folder name", f"name: {fields.get('name', '').strip()}")

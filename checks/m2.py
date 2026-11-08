"""Milestone 2: archiving, editing and adjusting stock, the stock race, and the wall."""

import asyncio
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

from contract import duplicate, insufficient, not_found, parity
from kitlib import ROOT, Fail, check, http_json, short

MISSING_ID = 999999


def new_product(ctx, sku: str, stock: int = 0, name: str = "Check item") -> int:
    """Insert a product straight into the throwaway database, and return its id."""
    r = ctx.psql(
        "INSERT INTO products (sku, name, category, price_cents, stock) "
        f"VALUES ('{sku}', '{name}', 'check', 1000, {stock}) RETURNING id;"
    )
    if r.returncode != 0:
        raise Fail(f"a test product {sku} can be inserted", short(r.stderr))
    return int(r.stdout.strip().splitlines()[0])


def run_py(ctx, body: str) -> dict:
    """Run a few lines inside the API container, with products and schemas imported, and return out."""
    script = (
        "import json\nout = {}\ntry:\n    import products, schemas\n"
        + "".join(f"    {line}\n" for line in body.strip("\n").splitlines())
        + "except Exception as e:\n    out['error'] = f'{type(e).__name__}: {e}'\n"
        "finally:\n    try:\n        from db import pool\n        pool.close()\n    except Exception:\n        pass\n"
        "print('RESULT:' + json.dumps(out, default=str))\n"
    )
    out = ctx.py(script)
    if "error" in out:
        raise Fail("the operation runs", out["error"])
    return out


def raised(call: str, name: str) -> str:
    """Lines that run a call and record the error it raises."""
    return f"try:\n    {call}\n    out['{name}'] = 'no error'\nexcept Exception as e:\n    out['{name}'] = [type(e).__name__, str(e)]"


def tool(ctx, name: str, args: dict):
    async def calls(client):
        return await client.call_tool(name, args)

    r = ctx.tools(calls)
    text = " ".join(getattr(c, "text", "") for c in r.content)
    return r.is_error, (text if r.is_error else r.structured_content)


def cli_json(ctx, *args):
    r = ctx.cli(*args)
    try:
        return r.returncode, json.loads(r.stdout), r.stderr.strip()
    except ValueError:
        return r.returncode, r.stdout.strip(), r.stderr.strip()


# --- Step 1 · The second migration: archived_at, and lists that leave archived products out ---


@check(2, 1, "the products table has archived_at, a moment with its time zone, empty by default", needs=("your seed is in",),
       gives="archived_at exists")
def archived_column(ctx):
    got = ctx.sql_value(
        "SELECT data_type || ' ' || is_nullable || ' ' || coalesce(column_default, 'none') FROM information_schema.columns "
        "WHERE table_name = 'products' AND column_name = 'archived_at'"
    )
    if got != "timestamp with time zone YES none":
        raise Fail("archived_at: timestamp with time zone, nullable, no default", got or "no column archived_at",
                   "002_add_archived_at.sql adds it with ALTER TABLE.")


@check(2, 1, "list_products() leaves archived products out, and list_products(include_archived=True) lists them", needs=("archived_at exists",))
def list_archived_op(ctx):
    pid = new_product(ctx, "CHECK-ARCH-LIST")
    ctx.psql(f"UPDATE products SET archived_at = now() WHERE id = {pid};")
    out = run_py(ctx, f"out['plain'] = [p.id for p in products.list_products()]\n"
                      f"out['all'] = [p.id for p in products.list_products(include_archived=True)]")
    if pid in out["plain"]:
        raise Fail(f"product {pid}, archived, not in list_products()", f"it's there")
    if pid not in out["all"]:
        raise Fail(f"product {pid} in list_products(include_archived=True)", f"ids {out['all']}")
    if out["all"] != sorted(out["all"]):
        raise Fail("sorted by id", f"ids {out['all']}")


@check(2, 1, "GET /products leaves archived products out; ?include_archived=true lists them, with archived_at", needs=("archived_at exists",))
def list_archived_http(ctx):
    pid = int(ctx.sql_value("SELECT id FROM products WHERE sku = 'CHECK-ARCH-LIST'") or 0)
    _, plain = http_json(ctx, "GET", "/products")
    status, every = http_json(ctx, "GET", "/products?include_archived=true")
    if any(p.get("id") == pid for p in plain):
        raise Fail(f"archived product {pid} left out of GET /products", "it's listed")
    match = [p for p in every if p.get("id") == pid] if isinstance(every, list) else []
    if status != 200 or not match or not match[0].get("archived_at"):
        raise Fail(f"product {pid} in GET /products?include_archived=true, with archived_at set",
                   f"{status} {short(json.dumps(match or every), 200)}")
    if "archived_at" not in plain[0] or plain[0]["archived_at"] is not None:
        raise Fail("every product has archived_at: null when it isn't archived", short(json.dumps(plain[0]), 200))


@check(2, 1, "./store products list --include-archived, and the tool's include_archived, agree with HTTP", needs=("archived_at exists",))
def list_archived_cli_tool(ctx):
    _, every = http_json(ctx, "GET", "/products?include_archived=true")
    _, plain = http_json(ctx, "GET", "/products")
    code, out, err = cli_json(ctx, "products", "list", "--include-archived")
    if code != 0 or out != every:
        raise Fail("exit 0, and the same JSON as GET /products?include_archived=true", f"exit {code}, {short(err or str(out), 200)}")
    code, out, err = cli_json(ctx, "products", "list")
    if out != plain:
        raise Fail("./store products list without the option: the same JSON as GET /products", short(err or str(out), 200))
    is_error, body = tool(ctx, "list_products", {"include_archived": True})
    if is_error or (body or {}).get("result") != every:
        raise Fail("list_products with include_archived true: the same as HTTP", short(str(body), 200))


# --- Step 2 · Archiving a product ---


@check(2, 2, "archive_product() sets archived_at; archiving again changes nothing; a missing id raises ProductNotFound", needs=("archived_at exists",))
def archive_op(ctx):
    pid = new_product(ctx, "CHECK-ARCH-OP")
    out = run_py(ctx, f"first = products.archive_product({pid})\nsecond = products.archive_product({pid})\n"
                      f"out['first'] = first.model_dump(mode='json')\nout['second'] = second.model_dump(mode='json')\n"
                      + raised(f"products.archive_product({MISSING_ID})", "missing"))
    if not out["first"].get("archived_at"):
        raise Fail("the product, with archived_at set", short(json.dumps(out["first"]), 200))
    if out["second"] != out["first"]:
        raise Fail("archiving it again returns it unchanged, archived_at included",
                   f"first {out['first'].get('archived_at')}, then {out['second'].get('archived_at')}")
    if ctx.sql_value(f"SELECT count(*) FROM products WHERE id = {pid}") != "1":
        raise Fail("the row still in the table", "it's gone", "Archiving keeps the row: orders will point at it.")
    if out["missing"] != ["ProductNotFound", not_found(MISSING_ID)]:
        raise Fail(f"ProductNotFound('{not_found(MISSING_ID)}')", str(out["missing"]))


@check(2, 2, "POST /products/{id}/archive answers 200 with the product; it stays reachable by id, and leaves the list", needs=("archived_at exists",))
def archive_http(ctx):
    pid = new_product(ctx, "CHECK-ARCH-HTTP")
    status, body = http_json(ctx, "POST", f"/products/{pid}/archive")
    if status != 200 or not isinstance(body, dict) or not body.get("archived_at"):
        raise Fail("200, and the product with archived_at set", f"{status} {short(json.dumps(body), 200)}")
    again_status, again = http_json(ctx, "POST", f"/products/{pid}/archive")
    if (again_status, again) != (200, body):
        raise Fail("the same answer again, archived_at unchanged", f"{again_status} {short(json.dumps(again), 200)}")
    get_status, one = http_json(ctx, "GET", f"/products/{pid}")
    if get_status != 200 or one != body:
        raise Fail(f"GET /products/{pid} still shows it", f"{get_status} {short(json.dumps(one), 200)}")
    _, listed = http_json(ctx, "GET", "/products")
    if any(p.get("id") == pid for p in listed):
        raise Fail("left out of GET /products", "it's still listed")
    status, body = http_json(ctx, "POST", f"/products/{MISSING_ID}/archive")
    if (status, body) != (404, {"detail": not_found(MISSING_ID)}):
        raise Fail(f'404 {{"detail": "{not_found(MISSING_ID)}"}}', f"{status} {short(json.dumps(body), 200)}")


@check(2, 2, "./store products archive and the archive_product tool archive, and say why when the id is missing", needs=("archived_at exists",))
def archive_cli_tool(ctx):
    pid = new_product(ctx, "CHECK-ARCH-CLI")
    code, out, err = cli_json(ctx, "products", "archive", str(pid))
    if code != 0 or not isinstance(out, dict) or not out.get("archived_at"):
        raise Fail("exit 0, and the product with archived_at set", f"exit {code}, {short(err or str(out), 200)}")
    code, out, err = cli_json(ctx, "products", "archive", str(MISSING_ID))
    if (code, err) != (3, not_found(MISSING_ID)):
        raise Fail(f"exit 3, stderr: {not_found(MISSING_ID)}", f"exit {code}, stderr {short(err, 200)!r}")
    pid = new_product(ctx, "CHECK-ARCH-TOOL")
    is_error, body = tool(ctx, "archive_product", {"product_id": pid})
    if is_error or not (body or {}).get("archived_at"):
        raise Fail("the tool returns the product, with archived_at set", short(str(body), 200))
    is_error, body = tool(ctx, "archive_product", {"product_id": MISSING_ID})
    if not is_error or not_found(MISSING_ID) not in body:
        raise Fail(f"an error containing: {not_found(MISSING_ID)}", short(str(body), 200))


# --- Step 3 · Editing a product ---


@check(2, 3, "ProductUpdate: every field optional; it refuses null, an empty name, a negative price, and stock", needs=("archived_at exists",))
def update_model(ctx):
    out = run_py(ctx, "M = schemas.ProductUpdate\nout['empty'] = M().model_dump(exclude_unset=True)\n"
                      "refused = {}\n"
                      "for label, data in [('null name', {'name': None}), ('empty name', {'name': ''}),\n"
                      "                    ('negative price', {'price_cents': -1}), ('stock', {'stock': 5}),\n"
                      "                    ('id', {'id': 3})]:\n"
                      "    try:\n        M(**data)\n        refused[label] = False\n"
                      "    except Exception:\n        refused[label] = True\n"
                      "out['refused'] = refused\nout['fields'] = sorted(M.model_fields)")
    want = {"sku", "name", "description", "category", "image_url", "price_cents"}
    if set(out["fields"]) != want:
        raise Fail("ProductUpdate's fields: " + ", ".join(sorted(want)), ", ".join(out["fields"]))
    if out["empty"] != {}:
        raise Fail("ProductUpdate() with nothing set", str(out["empty"]))
    accepted = [k for k, v in out["refused"].items() if not v]
    if accepted:
        raise Fail("a ValidationError for each", "accepted: " + ", ".join(accepted),
                   "stock and id aren't fields of ProductUpdate, so they must be refused, not ignored.")


@check(2, 3, "update_product() changes only what it's given, moves updated_at, and names a taken SKU", needs=("archived_at exists",))
def update_op(ctx):
    pid = new_product(ctx, "CHECK-UPD-OP")
    new_product(ctx, "CHECK-UPD-TAKEN")
    out = run_py(ctx, f"before = products.get_product({pid})\n"
                      f"after = products.update_product({pid}, schemas.ProductUpdate(name=\"Hiker's mug\", price_cents=1500))\n"
                      f"same = products.update_product({pid}, schemas.ProductUpdate())\n"
                      "out['before'] = before.model_dump(mode='json')\nout['after'] = after.model_dump(mode='json')\n"
                      "out['same'] = same.model_dump(mode='json')\n"
                      + raised(f"products.update_product({pid}, schemas.ProductUpdate(sku='CHECK-UPD-TAKEN'))", "dup") + "\n"
                      + raised(f"products.update_product({MISSING_ID}, schemas.ProductUpdate(name='x'))", "missing"))
    b, a = out["before"], out["after"]
    if (a.get("name"), a.get("price_cents")) != ("Hiker's mug", 1500):
        raise Fail("name Hiker's mug, price_cents 1500", f"name {a.get('name')!r}, price_cents {a.get('price_cents')}")
    unchanged = [k for k in ("sku", "category", "stock", "description", "created_at") if a.get(k) != b.get(k)]
    if unchanged:
        raise Fail("every other field unchanged", "changed: " + ", ".join(unchanged))
    if not a.get("updated_at") or a["updated_at"] <= b["updated_at"]:
        raise Fail("updated_at later than before", f"{b.get('updated_at')} -> {a.get('updated_at')}",
                   "SET updated_at = now() in the same UPDATE.")
    if out["same"] != a:
        raise Fail("an empty update returns the product unchanged", short(json.dumps(out["same"]), 200))
    if out["dup"] != ["DuplicateSku", duplicate("CHECK-UPD-TAKEN")]:
        raise Fail(f"DuplicateSku('{duplicate('CHECK-UPD-TAKEN')}')", str(out["dup"]))
    if out["missing"] != ["ProductNotFound", not_found(MISSING_ID)]:
        raise Fail(f"ProductNotFound('{not_found(MISSING_ID)}')", str(out["missing"]))


@check(2, 3, "PATCH /products/{id}: 200 with the change, 422 for null or stock, 409 for a taken SKU, 404 for a missing id", needs=("archived_at exists",))
def update_http(ctx):
    pid = new_product(ctx, "CHECK-UPD-HTTP")
    status, body = http_json(ctx, "PATCH", f"/products/{pid}", json={"price_cents": 2200})
    if status != 200 or body.get("price_cents") != 2200 or body.get("sku") != "CHECK-UPD-HTTP":
        raise Fail("200, price_cents 2200, everything else as it was", f"{status} {short(json.dumps(body), 200)}")
    for sent in ({"name": None}, {"stock": 5}):
        status, body = http_json(ctx, "PATCH", f"/products/{pid}", json=sent)
        if status != 422:
            raise Fail(f"422 for {json.dumps(sent)}", f"{status} {short(json.dumps(body), 200)}")
    status, body = http_json(ctx, "PATCH", f"/products/{pid}", json={"sku": "CHECK-UPD-TAKEN"})
    if (status, body) != (409, {"detail": duplicate("CHECK-UPD-TAKEN")}):
        raise Fail(f'409 {{"detail": "{duplicate("CHECK-UPD-TAKEN")}"}}', f"{status} {short(json.dumps(body), 200)}")
    status, body = http_json(ctx, "PATCH", f"/products/{MISSING_ID}", json={"name": "x"})
    if (status, body) != (404, {"detail": not_found(MISSING_ID)}):
        raise Fail(f'404 {{"detail": "{not_found(MISSING_ID)}"}}', f"{status} {short(json.dumps(body), 200)}")


@check(2, 3, "./store products update and the update_product tool change what they're given, and fail the same way", needs=("archived_at exists",))
def update_cli_tool(ctx):
    pid = new_product(ctx, "CHECK-UPD-CLI")
    code, out, err = cli_json(ctx, "products", "update", str(pid), "--price-cents", "3100", "--name", "Camp kettle")
    if code != 0 or not isinstance(out, dict) or (out.get("price_cents"), out.get("name")) != (3100, "Camp kettle"):
        raise Fail("exit 0, price_cents 3100, name Camp kettle", f"exit {code}, {short(err or str(out), 200)}")
    for args, want_code, want_err in [
        (("--sku", "CHECK-UPD-TAKEN"), 4, duplicate("CHECK-UPD-TAKEN")),
        (("--price-cents", "-1"), 2, "price_cents"),
    ]:
        code, out, err = cli_json(ctx, "products", "update", str(pid), *args)
        if code != want_code or want_err not in err:
            raise Fail(f"exit {want_code}, stderr containing {want_err!r}", f"exit {code}, stderr {short(err, 200)!r}")
    code, out, err = cli_json(ctx, "products", "update", str(MISSING_ID), "--name", "x")
    if (code, err) != (3, not_found(MISSING_ID)):
        raise Fail(f"exit 3, stderr: {not_found(MISSING_ID)}", f"exit {code}, stderr {short(err, 200)!r}")
    is_error, body = tool(ctx, "update_product", {"product_id": pid, "changes": {"category": "kitchen"}})
    if is_error or (body or {}).get("category") != "kitchen" or body.get("name") != "Camp kettle":
        raise Fail("the tool returns the product, category kitchen, everything else as it was", short(str(body), 200))
    is_error, body = tool(ctx, "update_product", {"product_id": pid, "changes": {"sku": "CHECK-UPD-TAKEN"}})
    if not is_error or duplicate("CHECK-UPD-TAKEN") not in body:
        raise Fail(f"an error containing: {duplicate('CHECK-UPD-TAKEN')}", short(str(body), 200))


# --- Step 4 · Adjusting stock ---


@check(2, 4, "adjust_stock() adds and removes in one statement, and refuses to go below zero with the contract's message",
       needs=("archived_at exists",))
def adjust_op(ctx):
    pid = new_product(ctx, "CHECK-STOCK-OP", stock=4, name="Check lantern")
    out = run_py(ctx, f"before = products.get_product({pid})\nup = products.adjust_stock({pid}, 3)\n"
                      f"out['before'] = before.model_dump(mode='json')\nout['up'] = up.model_dump(mode='json')\n"
                      + raised(f"products.adjust_stock({pid}, -10)", "short") + "\n"
                      + raised(f"products.adjust_stock({MISSING_ID}, 1)", "missing"))
    if out["up"].get("stock") != 7 or out["up"]["updated_at"] <= out["before"]["updated_at"]:
        raise Fail("stock 7, and updated_at later than before", short(json.dumps(out["up"]), 200))
    want = ["InsufficientStock", insufficient(7, "Check lantern", 10)]
    if out["short"] != want:
        raise Fail(f"InsufficientStock('{want[1]}')", str(out["short"]))
    if ctx.sql_value(f"SELECT stock FROM products WHERE id = {pid}") != "7":
        raise Fail("stock still 7 after the refusal", ctx.sql_value(f"SELECT stock FROM products WHERE id = {pid}"))
    if out["missing"] != ["ProductNotFound", not_found(MISSING_ID)]:
        raise Fail(f"ProductNotFound('{not_found(MISSING_ID)}')", str(out["missing"]))


@check(2, 4, "POST /products/{id}/stock: 200 with the new stock, 409 when there isn't enough, 404 for a missing id", needs=("archived_at exists",))
def adjust_http(ctx):
    pid = new_product(ctx, "CHECK-STOCK-HTTP", stock=2, name="Check stove")
    status, body = http_json(ctx, "POST", f"/products/{pid}/stock", json={"change": 5})
    if status != 200 or body.get("stock") != 7:
        raise Fail("200, stock 7", f"{status} {short(json.dumps(body), 200)}")
    status, body = http_json(ctx, "POST", f"/products/{pid}/stock", json={"change": -8})
    want = {"detail": insufficient(7, "Check stove", 8)}
    if (status, body) != (409, want):
        raise Fail(f"409 {json.dumps(want)}", f"{status} {short(json.dumps(body), 200)}",
                   "A 500 means the CHECK refused the UPDATE and nothing caught the CheckViolation.")
    status, body = http_json(ctx, "POST", f"/products/{MISSING_ID}/stock", json={"change": 1})
    if (status, body) != (404, {"detail": not_found(MISSING_ID)}):
        raise Fail(f'404 {{"detail": "{not_found(MISSING_ID)}"}}', f"{status} {short(json.dumps(body), 200)}")
    status, body = http_json(ctx, "POST", f"/products/{pid}/stock", json={"change": 1.5})
    if status != 422:
        raise Fail("422 for a change of 1.5", f"{status} {short(json.dumps(body), 200)}")


@check(2, 4, "./store products adjust-stock and the adjust_stock tool: the same results, exit codes and messages", needs=("archived_at exists",))
def adjust_cli_tool(ctx):
    pid = new_product(ctx, "CHECK-STOCK-CLI", stock=1, name="Check pan")
    code, out, err = cli_json(ctx, "products", "adjust-stock", str(pid), "--change", "4")
    if code != 0 or not isinstance(out, dict) or out.get("stock") != 5:
        raise Fail("exit 0, stock 5", f"exit {code}, {short(err or str(out), 200)}")
    code, out, err = cli_json(ctx, "products", "adjust-stock", str(pid), "--change", "-9")
    if (code, err) != (4, insufficient(5, "Check pan", 9)):
        raise Fail(f"exit 4, stderr: {insufficient(5, 'Check pan', 9)}", f"exit {code}, stderr {short(err, 200)!r}")
    code, out, err = cli_json(ctx, "products", "adjust-stock", str(MISSING_ID), "--change", "1")
    if (code, err) != (3, not_found(MISSING_ID)):
        raise Fail(f"exit 3, stderr: {not_found(MISSING_ID)}", f"exit {code}, stderr {short(err, 200)!r}")
    is_error, body = tool(ctx, "adjust_stock", {"product_id": pid, "change": -2})
    if is_error or (body or {}).get("stock") != 3:
        raise Fail("the tool returns the product, stock 3", short(str(body), 200))
    is_error, body = tool(ctx, "adjust_stock", {"product_id": pid, "change": -9})
    if not is_error or insufficient(3, "Check pan", 9) not in body:
        raise Fail(f"an error containing: {insufficient(3, 'Check pan', 9)}", short(str(body), 200))


@check(2, 4, "parity: the new operations each have a route, a command and a tool", needs=("archived_at exists",))
def parity_m2(ctx):
    parity(ctx, 2)


# --- Step 5 · The stock race ---


def race(ctx, via: str) -> None:
    import stock_race

    pid = new_product(ctx, f"CHECK-RACE-{via.upper()}", stock=10, name=f"Race {via}")
    lines: list[str] = []
    env = dict(ctx.env())
    ok = asyncio.run(stock_race.race(via, ctx.base, pid, 50, say=lines.append, env=env))
    if not ok:
        detail = [l.strip() for l in lines if "answered" in l or "now" in l or "Answer" in l or "Not a" in l]
        raise Fail("50 × +1 and 50 × -1 at once, all answered success, stock back where it started; then a clean refusal",
                   " / ".join(detail)[:600], "Read then write loses updates: change the stock in one UPDATE.")


@check(2, 5, "the stock race over HTTP: 50 × +1 and 50 × -1 at once leave the stock where it was", needs=("archived_at exists",))
def race_http(ctx):
    race(ctx, "http")


@check(2, 5, "the stock race through ./store", needs=("archived_at exists",))
def race_cli(ctx):
    race(ctx, "cli")


@check(2, 5, "the stock race through the tools", needs=("archived_at exists",))
def race_tools(ctx):
    race(ctx, "tools")


# --- Step 6 · The wall in your store: a hook ---


@check(2, 6, "your repository's settings run protect-backend.py before every file edit")
def hook_settings(ctx):
    path = ROOT / ".claude" / "settings.json"
    if not path.exists():
        raise Fail(".claude/settings.json", "no such file")
    try:
        settings = json.loads(path.read_text())
    except ValueError as e:
        raise Fail(".claude/settings.json is valid JSON", str(e))
    entries = settings.get("hooks", {}).get("PreToolUse", [])
    found = [e for e in entries if all(t in e.get("matcher", "") for t in ("Edit", "Write"))
             and any("protect-backend.py" in h.get("command", "") for h in e.get("hooks", []))]
    if not found:
        raise Fail("a PreToolUse hook, matching Edit and Write, that runs protect-backend.py", short(json.dumps(entries), 300))


@check(2, 6, "protect-backend.py refuses an edit in backend/, and allows one anywhere else")
def hook_script(ctx):
    script = ROOT / ".claude" / "hooks" / "protect-backend.py"
    if not script.exists():
        raise Fail(".claude/hooks/protect-backend.py", "no such file")
    results = {}
    for rel in ("backend/products.py", "backend/new_file.py", "README.md", "JOURNAL.md"):
        event = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(ROOT / rel)}})
        r = subprocess.run(["python3", str(script)], input=event, capture_output=True, text=True,
                           env={**os.environ, "CLAUDE_PROJECT_DIR": str(ROOT)})
        results[rel] = (r.returncode, r.stderr.strip())
    wrong = [f"{rel}: exit {code}" for rel, (code, _) in results.items()
             if (code == 2) != rel.startswith("backend/")]
    if wrong:
        raise Fail("exit 2 for backend/ files, exit 0 for the rest", "; ".join(wrong))
    if not results["backend/products.py"][1]:
        raise Fail("a message on stderr saying why", "nothing on stderr", "The agent reads it, and decides what to do next with it.")


# --- Step 7 · The wall in your tutor: a deny rule ---


@check(2, 7, "your tutor's store course denies edits to this repository's backend/")
def tutor_deny(ctx):
    home = Path(os.environ.get("TUTOR_HOME", Path.home() / "tutor"))
    path = home / "courses" / "01-online-store" / ".claude" / "settings.json"
    if not path.exists():
        raise Fail(str(path), "no such file", "Is your tutor harness at ~/tutor, with course 01-online-store?")
    deny = json.loads(path.read_text()).get("permissions", {}).get("deny", [])
    backend = os.path.realpath(ROOT / "backend")
    good = {f"Edit(/{backend}/**)"}
    home_dir = os.path.realpath(Path.home())
    if backend.startswith(home_dir + os.sep):
        good.add(f"Edit(~/{os.path.relpath(backend, home_dir)}/**)")
    if not good & set(deny):
        single = f"Edit({backend}/**)"
        hint = ("That path starts with one slash, so Claude Code reads it relative to the settings file. "
                "An absolute path needs two: Edit(//Users/…)." if single in deny else
                f"Add {sorted(good)[0]} to permissions.deny, through Tutor Orch.")
        raise Fail(" or ".join(sorted(good)), json.dumps(deny), hint)

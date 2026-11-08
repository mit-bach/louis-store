"""Milestone 1: the products table, its seed, the operations, and the three ways in (HTTP, CLI, tools)."""

import ast
import json
from datetime import datetime

from contract import duplicate, not_found, parity
from kitlib import ROOT, Fail, check, http_json, short

# What CONTRACT.md fixes for products.
FIELDS = {"id", "sku", "name", "description", "category", "image_url", "price_cents", "stock", "created_at", "updated_at"}
CREATE_FIELDS = {"sku", "name", "description", "category", "image_url", "price_cents", "stock"}
MISSING_ID = 999999


FORBIDDEN_IMPORTS = {"fastapi", "starlette", "typer", "click", "mcp", "httpx", "uvicorn"}


def expect_refused(ctx, sql: str, fragment: str, what: str) -> None:
    r = ctx.psql(f"BEGIN;\n{sql}\nROLLBACK;")
    if r.returncode == 0:
        raise Fail(f"the database refuses {what}", "it was accepted",
                   "Which rule in your CREATE TABLE should refuse it? Rules in the table hold for every caller.")
    if fragment not in r.stderr:
        raise Fail(f"an error containing '{fragment}'", short(r.stderr))


def first_id(ctx) -> int:
    return int(ctx.sql_value("SELECT min(id) FROM products"))


def product_count(ctx) -> int:
    return int(ctx.sql_value("SELECT count(*) FROM products"))


def has_zone(stamp: str) -> bool:
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00")).tzinfo is not None
    except (TypeError, ValueError):
        return False


# --- Step 1 · The products table ---


@check(1, 1, "your migrations apply to an empty database", needs=("your store starts",), gives="your table exists")
def migrations(ctx):
    files = sorted((ROOT / "backend" / "migrations").glob("*.sql"))
    if not files:
        raise Fail("backend/migrations/001_create_products.sql", "no .sql files in backend/migrations/")
    for f in files:
        r = ctx.psql(f.read_text(), single_transaction=True)
        if r.returncode != 0:
            raise Fail(f"{f.name} applies without errors", short(r.stderr), "The error names the line and the word it stopped at.")


@check(1, 1, "the products table has the contract's columns", needs=("your table exists",))
def columns(ctx):
    got = set(ctx.sql_value(
        "SELECT string_agg(column_name, ',') FROM information_schema.columns WHERE table_name = 'products'"
    ).split(","))
    if not FIELDS <= got:
        raise Fail(", ".join(sorted(FIELDS)), ", ".join(sorted(got)), f"Missing: {', '.join(sorted(FIELDS - got))}.")


@check(1, 1, "created_at and updated_at store a moment, with its time zone", needs=("your table exists",))
def timestamptz(ctx):
    got = ctx.sql_value(
        "SELECT string_agg(column_name || ' ' || data_type, ', ' ORDER BY column_name) FROM information_schema.columns "
        "WHERE table_name = 'products' AND column_name IN ('created_at', 'updated_at')"
    )
    if got.count("timestamp with time zone") != 2:
        raise Fail("created_at timestamp with time zone, updated_at timestamp with time zone", got)


@check(1, 1, "a product with only the required columns gets its id and defaults from the database", needs=("your table exists",))
def defaults(ctx):
    r = ctx.psql(
        "BEGIN;\n"
        "INSERT INTO products (sku, name, category, price_cents) VALUES ('CHECK-DEFAULTS', 'Check', 'check', 100)\n"
        "  RETURNING id IS NOT NULL, stock, description IS NULL, image_url IS NULL,\n"
        "            created_at IS NOT NULL, updated_at IS NOT NULL;\n"
        "ROLLBACK;"
    )
    if r.returncode != 0:
        raise Fail("the insert is accepted", short(r.stderr), "Only sku, name, category and price_cents are required.")
    got = r.stdout.strip().splitlines()[0]
    if got != "t|0|t|t|t|t":
        raise Fail("an id, stock 0, no description (NULL), no image (NULL), and both times filled in",
                   f"id set|stock|description null|image null|created set|updated set = {got}")


@check(1, 1, "the database refuses a negative price", needs=("your table exists",))
def negative_price(ctx):
    expect_refused(ctx, "INSERT INTO products (sku, name, category, price_cents) VALUES ('CHECK-NEG', 'Check', 'check', -1);",
                   "violates check constraint", "a price of -1")


@check(1, 1, "the database refuses negative stock", needs=("your table exists",))
def negative_stock(ctx):
    expect_refused(ctx, "INSERT INTO products (sku, name, category, price_cents, stock) VALUES ('CHECK-NEG', 'Check', 'check', 100, -1);",
                   "violates check constraint", "a stock of -1")


@check(1, 1, "the database refuses a second product with the same SKU", needs=("your table exists",))
def unique_sku(ctx):
    expect_refused(ctx,
                   "INSERT INTO products (sku, name, category, price_cents) VALUES ('CHECK-DUP', 'One', 'check', 100);\n"
                   "INSERT INTO products (sku, name, category, price_cents) VALUES ('CHECK-DUP', 'Two', 'check', 100);",
                   "violates unique constraint", "a duplicate SKU")


@check(1, 1, "the database refuses a product without a sku, name, category or price", needs=("your table exists",))
def required(ctx):
    allowed = []
    values = {"sku": "'CHECK-REQ'", "name": "'Check'", "category": "'check'", "price_cents": "100"}
    for column in values:
        row = {**values, column: "NULL"}
        r = ctx.psql(f"BEGIN;\nINSERT INTO products ({', '.join(row)}) VALUES ({', '.join(row.values())});\nROLLBACK;")
        if r.returncode == 0:
            allowed.append(column)
    if allowed:
        raise Fail("NOT NULL on sku, name, category and price_cents", f"NULL accepted in: {', '.join(allowed)}")


# --- Step 2 · The seed ---


@check(1, 2, "your seed applies", needs=("your table exists",), gives="your seed is in")
def seed(ctx):
    path = ROOT / "backend" / "seed.sql"
    if not path.exists():
        raise Fail("backend/seed.sql", "no such file")
    r = ctx.psql(path.read_text(), single_transaction=True)
    if r.returncode != 0:
        raise Fail("seed.sql applies without errors", short(r.stderr))


@check(1, 2, "the seed holds at least 8 products", needs=("your seed is in",))
def seed_size(ctx):
    n = product_count(ctx)
    if n < 8:
        raise Fail("8 or more products", f"{n}")


# --- Step 3 · The data shapes, and the first two operations ---


@check(1, 3, "products.py imports nothing from the web, the command line or the tool server")
def no_web_imports(ctx):
    path = ROOT / "backend" / "products.py"
    if not path.exists():
        raise Fail("backend/products.py", "no such file")
    found = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names if a.name.split(".")[0] in FORBIDDEN_IMPORTS]
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in FORBIDDEN_IMPORTS:
            found.append(node.module)
    if found:
        raise Fail("no imports from " + ", ".join(sorted(FORBIDDEN_IMPORTS)), "imports " + ", ".join(found),
                   "The operations are shared by HTTP, the CLI and the tools, so they can't depend on any one of them.")


PROBE_READ = f"""
import json
out = {{}}
try:
    import schemas, products
    out["create_fields"] = sorted(schemas.ProductCreate.model_fields)
    out["fields"] = sorted(schemas.Product.model_fields)
    items = products.list_products()
    out["list_types"] = sorted({{type(p).__name__ for p in items}})
    out["list_ids"] = [p.id for p in items]
    one = products.get_product(items[0].id) if items else None
    out["get"] = one.model_dump(mode="json") if one is not None else None
    out["first"] = items[0].model_dump(mode="json") if items else None
    try:
        products.get_product({MISSING_ID})
        out["missing"] = "no error"
    except Exception as e:
        out["missing"] = [type(e).__name__, str(e)]
except Exception as e:
    out["error"] = f"{{type(e).__name__}}: {{e}}"
finally:
    try:
        from db import pool
        pool.close()
    except Exception:
        pass
print("RESULT:" + json.dumps(out))
"""


def read_probe(ctx) -> dict:
    if "read" not in ctx.notes_cache:
        out = ctx.py(PROBE_READ)
        if "error" in out:
            raise Fail("schemas.py and products.py import and run", out["error"])
        ctx.notes_cache["read"] = out
    return ctx.notes_cache["read"]


@check(1, 3, "ProductCreate and Product have the contract's fields", needs=("your seed is in",))
def model_fields(ctx):
    out = read_probe(ctx)
    if set(out["create_fields"]) != CREATE_FIELDS:
        raise Fail("ProductCreate: " + ", ".join(sorted(CREATE_FIELDS)), "ProductCreate: " + ", ".join(out["create_fields"]))
    if not FIELDS <= set(out["fields"]):
        raise Fail("Product: " + ", ".join(sorted(FIELDS)), "Product: " + ", ".join(out["fields"]))


@check(1, 3, "list_products() returns every product as a Product, sorted by id", needs=("your seed is in",))
def list_products_op(ctx):
    out = read_probe(ctx)
    ids = [int(x) for x in ctx.sql_value("SELECT string_agg(id::text, ',' ORDER BY id) FROM products").split(",")]
    if out["list_types"] != ["Product"]:
        raise Fail("a list of Product", "a list of " + ", ".join(out["list_types"]))
    if out["list_ids"] != ids:
        raise Fail(f"ids {ids}", f"ids {out['list_ids']}", "Every product, ORDER BY id.")


@check(1, 3, "get_product(id) returns that product", needs=("your seed is in",))
def get_product_op(ctx):
    out = read_probe(ctx)
    if out["get"] != out["first"]:
        raise Fail(json.dumps(out["first"])[:200], json.dumps(out["get"])[:200])


@check(1, 3, f"get_product({MISSING_ID}) raises ProductNotFound with the contract's message", needs=("your seed is in",))
def get_missing_op(ctx):
    out = read_probe(ctx)
    want = ["ProductNotFound", not_found(MISSING_ID)]
    if out["missing"] != want:
        raise Fail(f"ProductNotFound('{want[1]}')", str(out["missing"]))


# --- Step 4 · Creating a product ---

PROBE_CREATE = f"""
import json
out = {{}}
try:
    import schemas, products
    from pydantic import ValidationError
    base = dict(sku="CHECK-CREATE-1", name="Hiker's lamp", category="check", price_cents=1250)
    refused = {{}}
    for label, change in [("negative price", dict(price_cents=-1)), ("negative stock", dict(stock=-1)),
                          ("empty name", dict(name="")), ("empty SKU", dict(sku="")),
                          ("empty description", dict(description="")), ("no category", dict(category=None))]:
        try:
            schemas.ProductCreate(**{{**base, **change}})
            refused[label] = False
        except ValidationError:
            refused[label] = True
    out["refused"] = refused
    d = schemas.ProductCreate(**base)
    out["defaults"] = [d.description, d.image_url, d.stock]
    try:
        made = products.create_product(d)
        out["made_type"] = type(made).__name__
        out["made"] = made.model_dump(mode="json")
        out["made_tz"] = made.created_at.tzinfo is not None
        try:
            products.create_product(d)
            out["dup"] = "no error"
        except Exception as e:
            out["dup"] = [type(e).__name__, str(e)]
    except Exception as e:
        out["create_error"] = f"{{type(e).__name__}}: {{e}}"
except Exception as e:
    out["error"] = f"{{type(e).__name__}}: {{e}}"
finally:
    try:
        from db import pool
        pool.close()
    except Exception:
        pass
print("RESULT:" + json.dumps(out))
"""


def create_probe(ctx) -> dict:
    if "create" not in ctx.notes_cache:
        out = ctx.py(PROBE_CREATE)
        if "error" in out:
            raise Fail("ProductCreate and create_product import and run", out["error"])
        ctx.notes_cache["create"] = out
    return ctx.notes_cache["create"]


@check(1, 4, "ProductCreate refuses a negative price or stock, an empty name, SKU or description, and no category", needs=("your seed is in",))
def create_validation(ctx):
    refused = create_probe(ctx)["refused"]
    accepted = [label for label, ok in refused.items() if not ok]
    if accepted:
        raise Fail("a ValidationError for each", "accepted: " + ", ".join(accepted))


@check(1, 4, "ProductCreate's defaults: no description, no image, stock 0", needs=("your seed is in",))
def create_defaults(ctx):
    got = create_probe(ctx)["defaults"]
    if got != [None, None, 0]:
        raise Fail("description=None, image_url=None, stock=0", f"description={got[0]!r}, image_url={got[1]!r}, stock={got[2]!r}")


def created(ctx) -> dict:
    out = create_probe(ctx)
    if "create_error" in out:
        raise Fail("create_product(ProductCreate(sku='CHECK-CREATE-1', name=\"Hiker's lamp\", …)) runs", out["create_error"],
                   "A syntax error near the name means the name was pasted into the SQL text: pass it with %s.")
    return out


@check(1, 4, "create_product() saves the product and returns it with its id and times", needs=("your seed is in",))
def create_op(ctx):
    out = created(ctx)
    made = out["made"]
    if out["made_type"] != "Product" or made.get("sku") != "CHECK-CREATE-1" or not isinstance(made.get("id"), int):
        raise Fail("a Product with sku CHECK-CREATE-1 and an id", json.dumps(made)[:200])
    if made.get("name") != "Hiker's lamp":
        raise Fail("the name exactly as given: Hiker's lamp", str(made.get("name")))
    if not out["made_tz"]:
        raise Fail("created_at with a time zone", str(made.get("created_at")))
    saved = ctx.sql_value("SELECT count(*) FROM products WHERE sku = 'CHECK-CREATE-1'")
    if saved != "1":
        raise Fail("one row in the table with that SKU", saved, "Did the insert commit? It must run inside `with pool.connection()`.")


@check(1, 4, "create_product() with a SKU that exists raises DuplicateSku with the contract's message", needs=("your seed is in",))
def create_dup_op(ctx):
    want = ["DuplicateSku", duplicate("CHECK-CREATE-1")]
    got = created(ctx)["dup"]
    if got != want:
        raise Fail(f"DuplicateSku('{want[1]}')", str(got))


# --- Step 5 · The HTTP routes ---


@check(1, 5, "GET /products answers 200 with every product, sorted by id", needs=("your seed is in",))
def http_list(ctx):
    status, body = http_json(ctx, "GET", "/products")
    if status != 200 or not isinstance(body, list):
        raise Fail("200 and a JSON list", f"{status} {short(str(body), 200)}")
    ids = [int(x) for x in ctx.sql_value("SELECT string_agg(id::text, ',' ORDER BY id) FROM products").split(",")]
    if [p.get("id") for p in body] != ids:
        raise Fail(f"ids {ids}", f"ids {[p.get('id') for p in body]}")
    keys = set(body[0])
    if not FIELDS <= keys:
        raise Fail("each product with: " + ", ".join(sorted(FIELDS)), "keys: " + ", ".join(sorted(keys)))
    if not has_zone(body[0]["created_at"]):
        raise Fail("created_at with a time zone, like 2026-11-08T10:00:00.123456Z", body[0]["created_at"])


@check(1, 5, "GET /products/{id} answers 200 with that product", needs=("your seed is in",))
def http_get(ctx):
    pid = first_id(ctx)
    status, body = http_json(ctx, "GET", f"/products/{pid}")
    _, listed = http_json(ctx, "GET", "/products")
    if status != 200 or body != listed[0]:
        raise Fail(f"200 and product {pid}, as GET /products shows it", f"{status} {short(json.dumps(body), 200)}")


@check(1, 5, f"GET /products/{MISSING_ID} answers 404 with the contract's message", needs=("your seed is in",))
def http_missing(ctx):
    status, body = http_json(ctx, "GET", f"/products/{MISSING_ID}")
    want = {"detail": not_found(MISSING_ID)}
    if (status, body) != (404, want):
        raise Fail(f"404 {json.dumps(want)}", f"{status} {short(json.dumps(body), 200)}",
                   "A 500 means ProductNotFound reached FastAPI uncaught: catch it in the route.")


@check(1, 5, "GET /products/abc answers 422", needs=("your seed is in",))
def http_bad_id(ctx):
    status, body = http_json(ctx, "GET", "/products/abc")
    if status != 422:
        raise Fail("422", f"{status} {short(json.dumps(body), 200)}", "Type the path parameter as int.")


@check(1, 5, "POST /products answers 201 with the new product, its defaults filled in", needs=("your seed is in",))
def http_create(ctx):
    sent = {"sku": "CHECK-HTTP-1", "name": "Hiker's stove", "category": "check", "price_cents": 2599}
    status, body = http_json(ctx, "POST", "/products", json=sent)
    if status != 201 or not isinstance(body, dict):
        raise Fail("201 and the new product", f"{status} {short(json.dumps(body), 300)}")
    want = {**sent, "description": None, "image_url": None, "stock": 0}
    got = {k: body.get(k) for k in want}
    if got != want or not FIELDS <= set(body) or not has_zone(body.get("created_at")):
        raise Fail(json.dumps(want) + " plus id, created_at, updated_at", short(json.dumps(body), 400))


@check(1, 5, "POST /products with a SKU that exists answers 409 with the contract's message", needs=("your seed is in",))
def http_dup(ctx):
    sent = {"sku": "CHECK-HTTP-2", "name": "Check pot", "category": "check", "price_cents": 900}
    http_json(ctx, "POST", "/products", json=sent)
    status, body = http_json(ctx, "POST", "/products", json=sent)
    want = {"detail": duplicate("CHECK-HTTP-2")}
    if (status, body) != (409, want):
        raise Fail(f"409 {json.dumps(want)}", f"{status} {short(json.dumps(body), 200)}")


@check(1, 5, "POST /products with a negative price answers 422, and saves nothing", needs=("your seed is in",))
def http_negative(ctx):
    before = product_count(ctx)
    status, body = http_json(ctx, "POST", "/products",
                             json={"sku": "CHECK-HTTP-3", "name": "Check", "category": "check", "price_cents": -5})
    if status != 422 or product_count(ctx) != before:
        raise Fail("422, and no new row", f"{status}, rows {before} -> {product_count(ctx)}")


@check(1, 5, "POST /products with a price of 12.5 cents answers 422", needs=("your seed is in",))
def http_fraction(ctx):
    status, body = http_json(ctx, "POST", "/products",
                             json={"sku": "CHECK-HTTP-5", "name": "Check", "category": "check", "price_cents": 12.5})
    if status != 422:
        raise Fail("422: a price is a whole number of cents", f"{status} {short(json.dumps(body), 200)}")


@check(1, 5, "POST /products without a name answers 422", needs=("your seed is in",))
def http_missing_name(ctx):
    status, body = http_json(ctx, "POST", "/products", json={"sku": "CHECK-HTTP-4", "category": "check", "price_cents": 100})
    if status != 422:
        raise Fail("422", f"{status} {short(json.dumps(body), 200)}")


# --- Step 6 · The command line ---


def cli_json(ctx, *args):
    r = ctx.cli(*args)
    try:
        return r.returncode, json.loads(r.stdout), r.stderr.strip()
    except ValueError:
        return r.returncode, r.stdout.strip(), r.stderr.strip()


@check(1, 6, "./store products list prints the same JSON as GET /products", needs=("your seed is in",))
def cli_list(ctx):
    code, out, err = cli_json(ctx, "products", "list")
    _, listed = http_json(ctx, "GET", "/products")
    if code != 0 or out != listed:
        raise Fail("exit 0, and stdout equal to GET /products", f"exit {code}, stdout {short(str(out), 200)}, stderr {short(err, 300)}")


@check(1, 6, "./store products get <id> prints the same JSON as GET /products/<id>", needs=("your seed is in",))
def cli_get(ctx):
    pid = first_id(ctx)
    code, out, err = cli_json(ctx, "products", "get", str(pid))
    _, one = http_json(ctx, "GET", f"/products/{pid}")
    if code != 0 or out != one:
        raise Fail(f"exit 0, and stdout equal to GET /products/{pid}", f"exit {code}, stdout {short(str(out), 200)}, stderr {short(err, 300)}")


@check(1, 6, f"./store products get {MISSING_ID} exits 3, with the contract's message on stderr", needs=("your seed is in",))
def cli_missing(ctx):
    code, out, err = cli_json(ctx, "products", "get", str(MISSING_ID))
    if (code, err) != (3, not_found(MISSING_ID)) or out:
        raise Fail(f"exit 3, nothing on stdout, stderr: {not_found(MISSING_ID)}", f"exit {code}, stdout {short(str(out), 100)!r}, stderr {short(err, 300)!r}")


@check(1, 6, "./store products create prints the new product, as GET shows it", needs=("your seed is in",))
def cli_create(ctx):
    code, out, err = cli_json(ctx, "products", "create", "--sku", "CHECK-CLI-1", "--name", "Check mug",
                              "--category", "check", "--price-cents", "1100")
    if code != 0 or not isinstance(out, dict) or out.get("sku") != "CHECK-CLI-1":
        raise Fail("exit 0 and the new product as JSON", f"exit {code}, stdout {short(str(out), 200)}, stderr {short(err, 300)}")
    _, one = http_json(ctx, "GET", f"/products/{out['id']}")
    if one != out:
        raise Fail("GET /products/<its id> shows the same product", short(json.dumps(one), 200))


@check(1, 6, "./store products create with a SKU that exists exits 4, with the contract's message", needs=("your seed is in",))
def cli_dup(ctx):
    args = ("products", "create", "--sku", "CHECK-CLI-2", "--name", "Check cup", "--category", "check", "--price-cents", "800")
    ctx.cli(*args)
    code, out, err = cli_json(ctx, *args)
    if (code, err) != (4, duplicate("CHECK-CLI-2")):
        raise Fail(f"exit 4, stderr: {duplicate('CHECK-CLI-2')}", f"exit {code}, stderr {short(err, 300)!r}")


@check(1, 6, "./store products create with a negative price exits 2, naming price_cents, and saves nothing", needs=("your seed is in",))
def cli_negative(ctx):
    before = product_count(ctx)
    code, out, err = cli_json(ctx, "products", "create", "--sku", "CHECK-CLI-3", "--name", "Check", "--category", "check",
                              "--price-cents=-1")
    if code != 2 or "price_cents" not in err or product_count(ctx) != before:
        raise Fail("exit 2, stderr naming price_cents, no new row",
                   f"exit {code}, stderr {short(err, 300)!r}, rows {before} -> {product_count(ctx)}")


# --- Step 7 · The tools ---


def tool_text(result) -> str:
    return " ".join(getattr(c, "text", "") for c in result.content)


@check(1, 7, "the tool server answers at /mcp", needs=("your seed is in",), gives="your tools answer")
def tools_answer(ctx):
    tool_descriptions(ctx)


@check(1, 7, "it lists list_products, get_product and create_product", needs=("your tools answer",))
def tools_listed(ctx):
    got = tool_descriptions(ctx)
    missing = [n for n in ("list_products", "get_product", "create_product") if n not in got]
    if missing:
        raise Fail("tools: list_products, get_product, create_product", "tools: " + (", ".join(sorted(got)) or "none"),
                   "A function becomes a tool only with @mcp.tool() on the line above it.")


@check(1, 7, "each tool has a description: it's what the agent reads", needs=("your tools answer",))
def tools_described(ctx):
    got = tool_descriptions(ctx)
    bare = [n for n, text in sorted(got.items()) if len(text) < 10]
    if bare:
        raise Fail("a docstring on each tool", "no description on: " + ", ".join(bare))


def tool_descriptions(ctx) -> dict:
    if "tools" not in ctx.notes_cache:
        async def calls(client):
            return (await client.list_tools()).tools

        try:
            tools = ctx.tools(calls)
        except Exception as e:
            raise Fail(f"an MCP server at {ctx.base}/mcp", f"{type(e).__name__}: {short(str(e))}",
                       "Is tools.http_app mounted at the bottom of main.py, and the lifespan passed to FastAPI?")
        ctx.notes_cache["tools"] = {t.name: (t.description or "").strip() for t in tools}
    return ctx.notes_cache["tools"]


@check(1, 7, "list_products and get_product return what HTTP returns", needs=("your tools answer",))
def tools_read(ctx):
    pid = first_id(ctx)

    async def calls(client):
        return await client.call_tool("list_products", {}), await client.call_tool("get_product", {"product_id": pid})

    listed, one = ctx.tools(calls)
    _, http_list_body = http_json(ctx, "GET", "/products")
    _, http_one = http_json(ctx, "GET", f"/products/{pid}")
    got_list = (listed.structured_content or {}).get("result")
    if listed.is_error or got_list != http_list_body:
        raise Fail("list_products' result equal to GET /products", short(tool_text(listed) or str(listed.structured_content), 300))
    if one.is_error or one.structured_content != http_one:
        raise Fail(f"get_product's result equal to GET /products/{pid}", short(tool_text(one) or str(one.structured_content), 300))


@check(1, 7, f"get_product({MISSING_ID}) is an error that tells the agent why", needs=("your tools answer",))
def tools_missing(ctx):
    async def calls(client):
        return await client.call_tool("get_product", {"product_id": MISSING_ID})

    r = ctx.tools(calls)
    if not r.is_error or not_found(MISSING_ID) not in tool_text(r):
        raise Fail(f"an error whose text contains: {not_found(MISSING_ID)}", f"is_error={r.is_error}, text: {short(tool_text(r), 300)!r}",
                   "\"Error executing tool get_product\" alone means the exception wasn't turned into a ToolError.")


@check(1, 7, "create_product adds a product, and a SKU that exists is an error that tells the agent why", needs=("your tools answer",))
def tools_create(ctx):
    product = {"sku": "CHECK-TOOL-1", "name": "Check bowl", "category": "check", "price_cents": 700}

    async def calls(client):
        return (await client.call_tool("create_product", {"product": product}),
                await client.call_tool("create_product", {"product": product}))

    made, again = ctx.tools(calls)
    body = made.structured_content or {}
    if made.is_error or body.get("sku") != "CHECK-TOOL-1":
        raise Fail("the new product", short(tool_text(made), 300), "The tool takes one argument, product, shaped like ProductCreate.")
    _, one = http_json(ctx, "GET", f"/products/{body.get('id')}")
    if one != body:
        raise Fail("GET /products/<its id> shows the same product", short(json.dumps(one), 200))
    if not again.is_error or duplicate("CHECK-TOOL-1") not in tool_text(again):
        raise Fail(f"an error containing: {duplicate('CHECK-TOOL-1')}", f"is_error={again.is_error}, text: {short(tool_text(again), 300)!r}")


@check(1, 7, "parity: every HTTP operation has its command and its tool, and nothing is left out", needs=("your tools answer",))
def parity_m1(ctx):
    parity(ctx, 1)

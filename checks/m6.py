"""Milestone 6: your orders, the door for the browser, the spec, and the frontend your agent builds from it."""

import json
import os
import re
import shutil

from contract import NO_TOKEN, parity
from kitlib import ROOT, Fail, check, http_json, short
from m2 import cli_json, new_product, run_py, tool
from m3 import bearer, put_line, session

SPEC = ROOT / "FRONTEND-SPEC.md"
FRONTEND = ROOT / "frontend"
JOURNAL = ROOT / "JOURNAL.md"


def journal_section(heading: str) -> str:
    text = JOURNAL.read_text() if JOURNAL.exists() else ""
    m = re.search(rf"^{re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, flags=re.M | re.S)
    return m.group(1).strip() if m else ""


def two_orders(ctx):
    """A session with two orders, at a price that changes in between, and another session's order."""
    token, other = session(ctx), session(ctx)
    pid = new_product(ctx, f"CHECK-ORDERS-{os.urandom(3).hex()}", stock=10, name="Orders item")
    put_line(ctx, token, pid, 1)
    run_py(ctx, f"import orders\norders.checkout('{token}')")
    ctx.psql(f"UPDATE products SET price_cents = 2500 WHERE id = {pid};")
    put_line(ctx, token, pid, 2)
    run_py(ctx, f"import orders\norders.checkout('{token}')")
    put_line(ctx, other, pid, 1)
    run_py(ctx, f"import orders\norders.checkout('{other}')")
    return token, pid


# --- Step 1 · Your orders, and the door for the browser ---


@check(6, 1, "list_orders(): the session's own orders, newest first, each at the prices paid", needs=("orders exist",))
def list_orders_op(ctx):
    token, pid = two_orders(ctx)
    out = run_py(ctx, f"import orders\nout['list'] = [o.model_dump(mode='json') for o in orders.list_orders('{token}')]")
    got = [[(line["quantity"], line["price_cents"]) for line in o["items"]] for o in out["list"]]
    if got != [[(2, 2500)], [(1, 1000)]] or out["list"][0]["id"] < out["list"][1]["id"]:
        raise Fail("two orders, newest first: 2 at 2500, then 1 at 1000", short(json.dumps(out["list"]), 400),
                   "ORDER BY id DESC, and read each order back as it was placed, with read_order.")


@check(6, 1, "GET /orders, ./store orders and the list_orders tool: the same list, and a 401, exit 5 or an error without a session",
       needs=("orders exist",))
def list_orders_ways(ctx):
    token, _ = two_orders(ctx)
    status, http = http_json(ctx, "GET", "/orders", **bearer(token))
    code, cli, err = cli_json(ctx, "orders", "--session", token)
    is_error, made = tool(ctx, "list_orders", {"session_token": token})
    listed = made.get("result") if isinstance(made, dict) else made
    if status != 200 or code != 0 or is_error or not (http == cli == listed) or len(http or []) != 2:
        raise Fail("the same two orders from all three", f"HTTP {status}, exit {code}, tool error {is_error}: "
                   f"{short(json.dumps(http), 150)} / {short(str(cli), 150)} / {short(str(listed), 150)}")
    status, body = http_json(ctx, "GET", "/orders")
    code, _, err = cli_json(ctx, "orders")
    is_error, text = tool(ctx, "list_orders", {})
    if (status, body) != (401, {"detail": NO_TOKEN}) or (code, err) != (5, NO_TOKEN) or not is_error or NO_TOKEN not in str(text):
        raise Fail(f"401, exit 5 and a tool error, each with: {NO_TOKEN}", f"{status} {short(str(body), 100)}; exit {code}; {short(str(text), 100)}")


@check(6, 1, "parity: list_orders has its route, its command and its tool", needs=("orders exist",))
def parity_m6(ctx):
    parity(ctx, 6)


@check(6, 1, "CORS: a page from http://localhost:3000 may call the API, and a page from anywhere else may not")
def cors(ctx):
    asks = {"Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization,idempotency-key"}
    ours = ctx.http("OPTIONS", "/cart", headers={"Origin": "http://localhost:3000", **asks})
    theirs = ctx.http("OPTIONS", "/cart", headers={"Origin": "http://elsewhere.example", **asks})
    if ours.headers.get("access-control-allow-origin") != "http://localhost:3000" or "access-control-allow-origin" in theirs.headers:
        raise Fail("allowed for http://localhost:3000, and not for http://elsewhere.example",
                   f"3000: {ours.status_code} {ours.headers.get('access-control-allow-origin')}; "
                   f"elsewhere: {theirs.status_code} {theirs.headers.get('access-control-allow-origin')}",
                   "app.add_middleware(CORSMiddleware, ...), exactly as the step gives it.")


# --- Step 2 · The spec ---


@check(6, 2, "FRONTEND-SPEC.md: its pages and endpoints, where the token lives, the 401, 409 and 422, the key, and the walkthrough",
       gives="a spec")
def spec(ctx):
    if not SPEC.exists():
        raise Fail("FRONTEND-SPEC.md at the top of your repository", "no such file")
    text = SPEC.read_text()
    words = len(text.split())
    missing = [w for w in ["/products", "/sessions", "/cart", "/checkout", "/orders", "401", "409", "422", "Idempotency-Key"]
               if w not in text]
    if not re.search(r"localStorage|sessionStorage|cookie", text, flags=re.I):
        missing.append("where the token lives (localStorage, sessionStorage or a cookie)")
    if not re.search(r"walkthrough", text, flags=re.I):
        missing.append("the walkthrough")
    if words < 300 or missing:
        raise Fail("300 words or more, naming each endpoint, the token's place, 401, 409, 422, Idempotency-Key and the walkthrough",
                   f"{words} words; missing: {', '.join(missing) or 'nothing'}")


# --- Step 3 · The build ---


def pnpm(ctx, *args, timeout=900):
    if not shutil.which("pnpm"):
        raise Fail("pnpm on your PATH", "not found", "Step M6-3 installs Node and pnpm.")
    return ctx.run(["pnpm", "--dir", str(FRONTEND), *args], timeout=timeout)


@check(6, 3, "AGENTS.md says what your coding agent builds: the frontend, from your spec", needs=("a spec",))
def agents_rule(ctx):
    rules = (ROOT / "AGENTS.md").read_text() if (ROOT / "AGENTS.md").exists() else ""
    if "frontend" not in rules or "FRONTEND-SPEC.md" not in rules:
        raise Fail("AGENTS.md names frontend/ and FRONTEND-SPEC.md", "it doesn't", "A short section: what the agent builds, and from what.")


@check(6, 3, "frontend/: Next.js, Tailwind and shadcn/ui, with pnpm", needs=("a spec",), gives="a frontend")
def frontend_files(ctx):
    try:
        pkg = json.loads((FRONTEND / "package.json").read_text())
    except (OSError, ValueError) as e:
        raise Fail("frontend/package.json", f"{type(e).__name__}: {e}")
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    missing = [d for d in ("next", "react", "tailwindcss") if d not in deps]
    missing += [f for f in ("pnpm-lock.yaml", "components.json") if not (FRONTEND / f).exists()]
    if missing:
        raise Fail("next, react and tailwindcss in package.json; pnpm-lock.yaml; components.json from shadcn", "missing: " + ", ".join(missing))


@check(6, 3, "pnpm lint passes in frontend/", needs=("a frontend",))
def frontend_lint(ctx):
    r = pnpm(ctx, "install", "--frozen-lockfile")
    if r.returncode != 0:
        raise Fail("pnpm install --frozen-lockfile succeeds", short(r.stderr or r.stdout, 600))
    r = pnpm(ctx, "lint")
    if r.returncode != 0:
        raise Fail("pnpm lint exits 0", short(r.stdout + r.stderr, 900))


@check(6, 3, "pnpm build passes in frontend/", needs=("a frontend",))
def frontend_build(ctx):
    r = pnpm(ctx, "build")
    if r.returncode != 0:
        raise Fail("pnpm build exits 0", short(r.stdout + r.stderr, 1200))


# --- Steps 4 and 5 · The walkthrough, and the control ---


@check(6, 4, "your journal has the walkthrough: what each of the four checks showed, and what you changed")
def walkthrough(ctx):
    text = journal_section("## M6 walkthrough")
    if len(text.split()) < 120:
        raise Fail("## M6 walkthrough in JOURNAL.md, 120 words or more", f"{len(text.split())} words")


@check(6, 5, "your journal has the control: how the spec-less frontend did on the same walkthrough")
def control(ctx):
    text = journal_section("## M6 control")
    if len(text.split()) < 80:
        raise Fail("## M6 control in JOURNAL.md, 80 words or more", f"{len(text.split())} words")

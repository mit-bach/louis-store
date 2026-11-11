"""Optional spec 15: errors the browser can read. A 500 from your API carries the CORS header, so a page can read its message."""

from contract import UNEXPECTED
from kitlib import Fail, check, http_json, ready, short
from m2 import new_product
from m3 import put_line, session

OURS = "http://localhost:3000"


def crash(ctx, origin: str):
    """A checkout that breaks, sent from a page at `origin`: (status, body, the CORS header)."""
    token = session(ctx)
    pid = new_product(ctx, f"CHECK-S15-{origin[-4:].strip('/:')}-{token[-6:]}", stock=5, name="Spec 15 item")
    put_line(ctx, token, pid, 1)
    ctx.psql("ALTER TABLE order_lines RENAME TO order_lines_gone;")
    try:
        r = ctx.http("POST", "/checkout", headers={"Authorization": f"Bearer {token}", "Origin": origin})
    finally:
        ctx.psql("ALTER TABLE order_lines_gone RENAME TO order_lines;")
    try:
        body = r.json()
    except ValueError:
        body = r.text
    return r.status_code, body, r.headers.get("access-control-allow-origin")


@check(15, 1, "a 500 answers a page from http://localhost:3000 with the CORS header and the contract's message", gives="a readable 500")
def readable_500(ctx):
    ready(ctx)
    status, body, allowed = crash(ctx, OURS)
    if (status, body, allowed) != (500, {"detail": UNEXPECTED}, OURS):
        raise Fail(f'500, {{"detail": "{UNEXPECTED}"}}, and access-control-allow-origin: {OURS}',
                   f"{status}, {short(str(body), 150)}, access-control-allow-origin: {allowed}",
                   "Catch unexpected errors in a middleware added before the CORS middleware, so CORS wraps it.")
    status, _, allowed = crash(ctx, "http://elsewhere.example")
    if allowed is not None:
        raise Fail("no CORS header for a page from anywhere else", f"access-control-allow-origin: {allowed}")


@check(15, 2, "the traceback still reaches your API's log", needs=("a readable 500",))
def still_logged(ctx):
    logs = ctx.compose("logs", "api", "--tail", "300").stdout
    if "UndefinedTable" not in logs or "Traceback" not in logs:
        raise Fail("a traceback naming UndefinedTable in the API's log", short(logs[-600:], 600),
                   "A middleware that catches the error has to log it too: logger.exception(...).")


@check(15, 3, "./store and the tools still answer with the contract's message, and CORS still allows only your frontend",
       needs=("a readable 500",))
def nothing_else_changed(ctx):
    import m5
    import m6

    m5.unexpected(ctx)
    m6.cors(ctx)

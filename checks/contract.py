"""What CONTRACT.md fixes, in one place, for every milestone's checks."""

from kitlib import Fail, http_json

# Every operation: its route, then its command, its tool, and the milestone that adds it.
OPERATIONS = {
    ("GET", "/products"): ("products list", "list_products", 1),
    ("GET", "/products/{product_id}"): ("products get", "get_product", 1),
    ("POST", "/products"): ("products create", "create_product", 1),
    ("POST", "/products/{product_id}/archive"): ("products archive", "archive_product", 2),
    ("PATCH", "/products/{product_id}"): ("products update", "update_product", 2),
    ("POST", "/products/{product_id}/stock"): ("products adjust-stock", "adjust_stock", 2),
    ("POST", "/sessions"): ("session start", "start_session", 3),
    ("GET", "/cart"): ("cart show", "get_cart", 3),
    ("PUT", "/cart/items/{product_id}"): ("cart set", "set_cart_item", 3),
    ("DELETE", "/cart/items/{product_id}"): ("cart remove", "remove_cart_item", 3),
    ("POST", "/checkout"): ("checkout", "checkout", 4),
}

EMPTY_CART = "Your cart is empty."


def short_line(stock: int, name: str) -> str:
    return f"Only {stock} of {name} left in stock."


def not_for_sale_any_more(lines: list[tuple[str, int]]) -> str:
    names = ", ".join(f"{name} (product {pid})" for name, pid in lines)
    them = "it" if len(lines) == 1 else "them"
    return f"Not for sale any more: {names}. Remove {them} from your cart, then check out again."

NO_TOKEN = "No session token. Start a session, then send its token with every cart request."
BAD_TOKEN = "That session token doesn't exist. Start a new session."
EXPIRED = "That session has expired. Start a new session."


def not_for_sale(product_id: int) -> str:
    return f"Product {product_id} isn't for sale."


def cart_too_many(stock: int, name: str, quantity: int) -> str:
    return f"Only {stock} of {name} in stock, so a cart can't hold {quantity}."


def not_found(product_id: int) -> str:
    return f"No product with id {product_id}."


def duplicate(sku: str) -> str:
    return f"A product with the SKU {sku} already exists."


def insufficient(stock: int, name: str, removing: int) -> str:
    return f"Only {stock} of {name} in stock, so {removing} can't be removed."


def parity(ctx, milestone: int) -> None:
    """Every route in /openapi.json is in the contract, and each one, with every operation up to this
    milestone, has its route, its command and its tool."""
    status, spec = http_json(ctx, "GET", "/openapi.json")
    routes = {(m.upper(), p) for p, ops in spec.get("paths", {}).items() for m in ops if p != "/health"}

    async def calls(client):
        return {t.name for t in (await client.list_tools()).tools}

    tools = ctx.tools(calls)
    problems = [f"{m} {p} isn't in CONTRACT.md" for m, p in sorted(routes - set(OPERATIONS))]
    for route, (command, tool, added) in OPERATIONS.items():
        if added > milestone and route not in routes:
            continue
        if route not in routes:
            problems.append(f"no route {route[0]} {route[1]}")
        if ctx.cli(*command.split(), "--help").returncode != 0:
            problems.append(f"no command ./store {command}")
        if tool not in tools:
            problems.append(f"no tool {tool}")
    if problems:
        raise Fail("each operation reachable three ways: HTTP, ./store and a tool", "; ".join(problems))

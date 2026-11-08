# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx==0.28.1"]
# ///
"""The checkout race: two buyers, one unit, the same moment.

    uv run checks/race_test.py                 20 rounds, on your store at port 8000
    uv run checks/race_test.py --rounds 5

It adds a product of its own with one unit in stock. Each round, two new sessions each put that
unit in their cart, and both check out at the same instant. A store that's safe answers one 201
(an order) and one 409 (out of stock), and ends the round with a stock of 0: never two orders,
never a 500, never a negative stock. Afterwards it archives its product, so your catalogue lists
it no more.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

import httpx


async def call(client, method: str, path: str, token: str | None = None, **kw):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        r = await client.request(method, path, headers=headers, **kw)
    except httpx.HTTPError as e:
        return 0, f"no answer ({type(e).__name__})"
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text


async def ready(client, say) -> bool:
    """Wait up to 30 seconds for the API: it restarts for a few seconds after you save a file."""
    for _ in range(30):
        code, _ = await call(client, "GET", "/health")
        if code == 200:
            return True
        await asyncio.sleep(1)
    say("Your API isn't answering on /health. Is it running? Try make up, then make logs.")
    return False


async def one_round(client, pid: int) -> tuple[list[int], int, list]:
    await call(client, "POST", f"/products/{pid}/stock", json={"change": 1})
    tokens = []
    for _ in range(2):
        _, session = await call(client, "POST", "/sessions")
        tokens.append(session["token"])
        await call(client, "PUT", f"/cart/items/{pid}", token=tokens[-1], json={"quantity": 1})
    answers = await asyncio.gather(*(call(client, "POST", "/checkout", token=t) for t in tokens))
    for _ in range(2):
        _, product = await call(client, "GET", f"/products/{pid}")
        if isinstance(product, dict):
            break
    stock = product.get("stock") if isinstance(product, dict) else None
    return sorted(code for code, _ in answers), stock, answers


async def race(base: str, rounds: int, say=print) -> bool:
    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        if not await ready(client, say):
            return False
        sku = f"RACE-{int(time.time() * 1000)}"
        code, product = await call(client, "POST", "/products", json={
            "sku": sku, "name": "Race test unit", "category": "test", "price_cents": 100, "stock": 0})
        if code != 201:
            say(f"Couldn't create the race's product: {code} {product}")
            return False
        pid = product["id"]
        good, problems = 0, []
        for n in range(1, rounds + 1):
            codes, stock, answers = await one_round(client, pid)
            if codes == [201, 409] and stock == 0:
                good += 1
            else:
                detail = "; ".join(f"{c} {str(b)[:120]}" for c, b in answers)
                problems.append(f"  round {n}: {' and '.join(map(str, codes))}, stock {stock}: {detail}")
            if isinstance(stock, int) and stock > 0:
                await call(client, "POST", f"/products/{pid}/stock", json={"change": -stock})
        await call(client, "POST", f"/products/{pid}/archive")
    for line in problems:
        say(line)
    say(f"{good}/{rounds} rounds: one 201, one 409, stock 0")
    return good == rounds


def main() -> int:
    parser = argparse.ArgumentParser(description="Race two checkouts for the last unit.")
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--port", type=int, default=int(os.environ.get("API_PORT", "8000")))
    a = parser.parse_args()
    return 0 if asyncio.run(race(f"http://localhost:{a.port}", a.rounds)) else 1


if __name__ == "__main__":
    sys.exit(main())

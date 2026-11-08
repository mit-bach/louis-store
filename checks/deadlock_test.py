# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx==0.28.1"]
# ///
"""The deadlock test: two carts holding the same two products, put in in opposite orders.

    uv run checks/deadlock_test.py              20 rounds, on your store at port 8000
    uv run checks/deadlock_test.py --rounds 5

It adds two products of its own, with plenty in stock. Each round, one session puts A then B in
its cart, another puts B then A, and both check out at the same instant. Both should get an
order. A checkout that locks its products in a different order for each cart can deadlock: each
holds one row and waits for the other's. Postgres then breaks the deadlock by failing one of
them, which your API answers with a 500. Postgres counts every deadlock it breaks; this script
reports that count too. Afterwards it archives its products.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent


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


def deadlocks(env: dict | None = None) -> int | None:
    """How many deadlocks Postgres has broken in the store's database, or None if it can't tell."""
    r = subprocess.run(
        ["docker", "compose", "exec", "-T", "db", "psql", "-X", "-At", "-U", "store", "-d", "store", "-c",
         "SELECT deadlocks FROM pg_stat_database WHERE datname = 'store'"],
        cwd=ROOT, capture_output=True, text=True, env=env,
    )
    try:
        return int(r.stdout.strip())
    except ValueError:
        return None


async def test(base: str, rounds: int, say=print, env: dict | None = None) -> bool:
    before = deadlocks(env)
    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        if not await ready(client, say):
            return False
        stamp = int(time.time() * 1000)
        ids = []
        for name in ("A", "B"):
            code, product = await call(client, "POST", "/products", json={
                "sku": f"DEADLOCK-{name}-{stamp}", "name": f"Deadlock test {name}", "category": "test",
                "price_cents": 100, "stock": 10 * rounds})
            if code != 201:
                say(f"Couldn't create the test's products: {code} {product}")
                return False
            ids.append(product["id"])
        a, b = ids
        good, problems = 0, []
        for n in range(1, rounds + 1):
            tokens = []
            for order in ((a, b), (b, a)):
                _, session = await call(client, "POST", "/sessions")
                tokens.append(session["token"])
                for pid in order:
                    await call(client, "PUT", f"/cart/items/{pid}", token=tokens[-1], json={"quantity": 1})
            answers = await asyncio.gather(*(call(client, "POST", "/checkout", token=t) for t in tokens))
            codes = sorted(code for code, _ in answers)
            if codes == [201, 201]:
                good += 1
            else:
                problems.append(f"  round {n}: {' and '.join(map(str, codes))}: "
                                + "; ".join(f"{c} {str(body)[:100]}" for c, body in answers))
        for pid in ids:
            await call(client, "POST", f"/products/{pid}/archive")
    after = deadlocks(env)
    for line in problems:
        say(line)
    say(f"{good}/{rounds} rounds: two 201s")
    if before is not None and after is not None:
        say(f"Deadlocks Postgres broke during the test: {after - before}")
    return good == rounds


def main() -> int:
    parser = argparse.ArgumentParser(description="Check out two carts with the same products in opposite orders.")
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--port", type=int, default=int(os.environ.get("API_PORT", "8000")))
    a = parser.parse_args()
    return 0 if asyncio.run(test(f"http://localhost:{a.port}", a.rounds)) else 1


if __name__ == "__main__":
    sys.exit(main())

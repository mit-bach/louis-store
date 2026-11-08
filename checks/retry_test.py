# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx==0.28.1", "mcp==2.3.0"]
# ///
"""Retries: one checkout sent twice with the same Idempotency-Key.

    uv run checks/retry_test.py                    through HTTP, 20 rounds, on your store at port 8000
    uv run checks/retry_test.py --via cli          through ./store
    uv run checks/retry_test.py --via tools        through your MCP tools
    uv run checks/retry_test.py --via all          all three, one after the other
    uv run checks/retry_test.py --rounds 6         a different number of rounds

It adds a product of its own with 2 in stock. Each round, a new session puts 1 in its cart and checks
out twice with one key: one after the other in odd rounds, at the same instant in even rounds. A safe
store answers both with the same order, places one order, and lowers the stock once: from 2 to 1.
When it's done, it archives its product.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
OK = {"http": 201, "cli": 0, "tools": "ok"}


async def wait_for(base: str) -> None:
    """Wait until the API answers, in case it is restarting after a code change."""
    deadline = time.time() + 30
    async with httpx.AsyncClient(timeout=3) as client:
        while time.time() < deadline:
            try:
                if (await client.get(f"{base}/health")).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.5)


class Way:
    """One way into the store's checkout. checkout() returns (code, order or message)."""

    def __init__(self, via: str, base: str, env: dict | None):
        self.via, self.base, self.env = via, base, env

    async def checkout(self, token: str, key: str, client=None):
        if self.via == "http":
            try:
                r = await client.post(f"{self.base}/checkout",
                                      headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key})
            except httpx.HTTPError as e:
                return type(e).__name__, str(e)
            try:
                body = r.json()
            except ValueError:
                body = r.text
            return r.status_code, body
        if self.via == "cli":
            proc = await asyncio.create_subprocess_exec(
                "./store", "checkout", "--session", token, "--idempotency-key", key,
                cwd=ROOT, env=self.env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            out, err = await proc.communicate()
            if proc.returncode == 0:
                try:
                    return 0, json.loads(out)
                except ValueError:
                    return 0, out.decode().strip()
            return proc.returncode, err.decode().strip()
        result = await client.call_tool("checkout", {"session_token": token, "idempotency_key": key})
        text = " ".join(getattr(c, "text", "") for c in result.content)
        return ("error", text) if result.is_error else ("ok", result.structured_content)

    async def twice(self, token: str, key: str, at_once: bool):
        async def go(client):
            if at_once:
                return await asyncio.gather(self.checkout(token, key, client), self.checkout(token, key, client))
            return [await self.checkout(token, key, client), await self.checkout(token, key, client)]

        if self.via == "http":
            async with httpx.AsyncClient(timeout=30) as client:
                return await go(client)
        if self.via == "cli":
            return await go(None)
        from mcp import Client

        async with Client(f"{self.base}/mcp") as client:
            return await go(client)


async def setup(base: str):
    async with httpx.AsyncClient(timeout=30) as client:
        sku = f"RETRY-{int(time.time() * 1000)}"
        r = await client.post(f"{base}/products", json={"sku": sku, "name": "Retry test unit", "category": "test",
                                                         "price_cents": 1500, "stock": 0})
        r.raise_for_status()
        return r.json()["id"]


async def one_round(way: Way, base: str, pid: int, n: int, at_once: bool):
    async with httpx.AsyncClient(timeout=30) as client:
        stock = (await client.get(f"{base}/products/{pid}")).json()["stock"]
        if stock != 2:
            await client.post(f"{base}/products/{pid}/stock", json={"change": 2 - stock})
        token = (await client.post(f"{base}/sessions")).json()["token"]
        await client.put(f"{base}/cart/items/{pid}", json={"quantity": 1}, headers={"Authorization": f"Bearer {token}"})
    key = f"round-{n}-{os.urandom(4).hex()}"
    answers = await way.twice(token, key, at_once)
    async with httpx.AsyncClient(timeout=30) as client:
        after = (await client.get(f"{base}/products/{pid}")).json()["stock"]
    codes = [code for code, _ in answers]
    ids = [body.get("id") if isinstance(body, dict) else None for _, body in answers]
    good = codes == [OK[way.via]] * 2 and ids[0] is not None and ids[0] == ids[1] and answers[0][1] == answers[1][1] and after == 1
    how = "at the same instant" if at_once else "one after the other"
    detail = "; ".join(f"{code} {str(body)[:140]}" for code, body in answers)
    return good, f"round {n} ({how}): stock {after}: {detail}"


async def retry(via: str, base: str, rounds: int, say=print, env: dict | None = None) -> bool:
    await wait_for(base)
    way = Way(via, base, env)
    pid = await setup(base)
    say(f"Retries through {via}: {rounds} rounds, each one checkout sent twice with one key.")
    good, problems = 0, []
    for n in range(1, rounds + 1):
        ok, line = await one_round(way, base, pid, n, at_once=(n % 2 == 0))
        good += ok
        if not ok:
            problems.append(line)
    async with httpx.AsyncClient(timeout=30) as client:
        await client.post(f"{base}/products/{pid}/archive")
    for line in problems:
        say("  " + line)
    say(f"{good}/{rounds} rounds: one order, both answers the same, stock lowered once")
    return good == rounds


def main() -> int:
    parser = argparse.ArgumentParser(description="Send each checkout twice, with one key, and count what it bought.")
    parser.add_argument("--via", choices=["http", "cli", "tools", "all"], default="http")
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--port", type=int, default=int(os.environ.get("API_PORT", "8000")))
    a = parser.parse_args()
    base = f"http://localhost:{a.port}"
    ways = ["http", "cli", "tools"] if a.via == "all" else [a.via]
    results = [asyncio.run(retry(via, base, a.rounds)) for via in ways]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())

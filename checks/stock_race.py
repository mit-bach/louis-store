# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx==0.28.1", "mcp==2.3.0"]
# ///
"""The stock race: many stock changes to one product, all at the same moment.

    uv run checks/stock_race.py                      race through HTTP, on your store at port 8000
    uv run checks/stock_race.py --via cli            race through ./store
    uv run checks/stock_race.py --via tools          race through your MCP tools
    uv run checks/stock_race.py --product 3          use product 3 (the default is your first product)

It reads the product's stock, then sends 50 changes of +1 and 50 of -1, all at once. Every change
is answered with success, so the stock must end exactly where it started. Then it tries to remove
more than is in stock, which must be refused with a clean "conflict", leaving the stock unchanged.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent


class Way:
    """One way into the store: each method returns (ok, product or message)."""

    def __init__(self, via: str, base: str, env: dict | None = None):
        self.via, self.base, self.env = via, base, env

    async def get(self, pid: int):
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{self.base}/products/{pid}")
        return r.json()

    async def change(self, pid: int, change: int, client=None):
        if self.via == "http":
            r = await client.post(f"{self.base}/products/{pid}/stock", json={"change": change})
            body = r.json()
            return r.status_code, body if r.status_code == 200 else body.get("detail", body)
        if self.via == "cli":
            proc = await asyncio.create_subprocess_exec(
                "./store", "products", "adjust-stock", str(pid), "--change", str(change),
                cwd=ROOT, env=self.env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            out, err = await proc.communicate()
            if proc.returncode == 0:
                return 0, json.loads(out)
            return proc.returncode, err.decode().strip()
        result = await client.call_tool("adjust_stock", {"product_id": pid, "change": change})
        text = " ".join(getattr(c, "text", "") for c in result.content)
        return ("error" if result.is_error else "ok"), (text if result.is_error else result.structured_content)

    async def many(self, pid: int, changes: list[int]):
        if self.via == "http":
            limits = httpx.Limits(max_connections=len(changes))
            async with httpx.AsyncClient(timeout=60, limits=limits) as client:
                return await asyncio.gather(*(self.change(pid, c, client) for c in changes))
        if self.via == "cli":
            return await asyncio.gather(*(self.change(pid, c) for c in changes))
        from mcp import Client

        async with Client(f"{self.base}/mcp") as client:
            return await asyncio.gather(*(self.change(pid, c, client) for c in changes))


def ok_code(via: str):
    return {"http": 200, "cli": 0, "tools": "ok"}[via]


def conflict_code(via: str):
    return {"http": 409, "cli": 4, "tools": "error"}[via]


async def race(via: str, base: str, pid: int | None, times: int, say=print, env: dict | None = None) -> bool:
    way = Way(via, base, env)
    if pid is None:
        async with httpx.AsyncClient(timeout=30) as client:
            pid = (await client.get(f"{base}/products")).json()[0]["id"]
    product = await way.get(pid)
    start, name = product["stock"], product["name"]
    say(f"The stock race, through {via}, on product {pid} ({name}). Its stock is {start}.")

    # Room to move: raise the stock first, so no -1 is refused for running out.
    await way.many(pid, [times])
    changes = [+1] * times + [-1] * times
    say(f"  Sending {times} changes of +1 and {times} of -1, all at once …")
    t0 = time.time()
    answers = await way.many(pid, changes)
    took = time.time() - t0
    await way.many(pid, [-times])
    end = (await way.get(pid))["stock"]

    good = sum(1 for code, _ in answers if code == ok_code(via))
    others = [(code, body) for code, body in answers if code != ok_code(via)]
    say(f"  {good} of {len(changes)} answered success, in {took:.1f} seconds.")
    for code, body in others[:3]:
        say(f"  Not a success: {code} {str(body)[:200]}")
    say(f"  The stock is now {end}. It should be {start}.")
    passed = not others and end == start

    too_many = start + times * 10
    say(f"  Removing {too_many}, which is more than the {start} in stock …")
    [(code, body)] = await way.many(pid, [-too_many])
    after = (await way.get(pid))["stock"]
    say(f"  Answer: {code} {str(body)[:200]}")
    say(f"  The stock is now {after}. It should still be {start}.")
    refused = code == conflict_code(via) and after == start and "in stock" in str(body)
    passed = passed and refused
    say("  PASS" if passed else "  FAIL")
    return passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Race stock changes against your store.")
    parser.add_argument("--via", choices=["http", "cli", "tools", "all"], default="http")
    parser.add_argument("--product", type=int, help="the product's id (default: your first product)")
    parser.add_argument("--times", type=int, default=50, help="how many +1 and how many -1 (default 50)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("API_PORT", "8000")))
    a = parser.parse_args()
    base = f"http://localhost:{a.port}"
    ways = ["http", "cli", "tools"] if a.via == "all" else [a.via]
    results = [asyncio.run(race(via, base, a.product, a.times)) for via in ways]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())

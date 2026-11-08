# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx==0.28.1", "mcp==2.3.0"]
# ///
"""Evals: five shopping tasks for your customer agent, each run headless and checked in the database.

    uv run checks/evals.py                   all five tasks, once each, on Haiku
    uv run checks/evals.py --tasks 1,2,3     only some of them
    uv run checks/evals.py --model sonnet    on another model
    uv run checks/evals.py --runs 3          each task three times

Each task adds products of its own to your store (on port 8000), then runs your customer agent once,
from agents/customer, with `claude -p` and only the store's tools. When the agent is done, it reads
the orders the agent placed, and compares them with what the task asked for. Then it archives its
products. Each run adds one line to checks/evals-runs.txt: the score, the model, which of your tool
descriptions it ran against, and what Claude Code says the run cost.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
AGENT = ROOT / "agents" / "customer"
RUNS = ROOT / "checks" / "evals-runs.txt"
BASE = f"http://localhost:{os.environ.get('API_PORT', '8000')}"

# Each task: its products (name, category, price in cents, stock, archived), what the customer says,
# and the order it should end with ({} means: no order at all).
TASKS = {
    1: {
        "title": "the two cheapest snacks",
        "products": [("Trail Mix", "snacks", 450, 10, False), ("Energy Bar", "snacks", 250, 10, False),
                     ("Beef Jerky", "snacks", 900, 10, False), ("Dried Mango", "snacks", 350, 10, False)],
        "ask": "Buy the two cheapest snacks in the store, one of each.",
        "want": {"Energy Bar": 1, "Dried Mango": 1},
    },
    2: {
        "title": "as many maps as there are",
        "products": [("Trail Map", "maps", 1200, 2, False)],
        "ask": "Buy three Trail Maps. If the store has fewer than three, buy as many as it has.",
        "want": {"Trail Map": 2},
    },
    3: {
        "title": "one more fig bar",
        "products": [("Fig Bar", "bars", 300, 10, False), ("Oat Bar", "bars", 300, 10, False)],
        "ask": "Put one Fig Bar in my cart. Then add one more Fig Bar, and one Oat Bar. Then check out.",
        "want": {"Fig Bar": 2, "Oat Bar": 1},
    },
    4: {
        "title": "not for sale",
        "products": [("Summit Stove", "stoves", 8900, 5, True), ("Valley Stove", "stoves", 7900, 5, False)],
        "ask": "Buy me a Summit Stove.",
        "want": {},
    },
    5: {
        "title": "twenty dollars of gels",
        "products": [("Energy Gel", "gels", 350, 20, False)],
        "ask": "I have $20. Buy as many Energy Gels as I can afford.",
        "want": {"Energy Gel": 5},
    },
}


def psql(sql: str) -> str:
    r = subprocess.run(["docker", "compose", "exec", "-T", "db", "psql", "-X", "-q", "-A", "-t", "-U", "store", "-d", "store"],
                       cwd=ROOT, input=sql, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"Reading the database failed: {r.stderr.strip()}")
    return r.stdout.strip()


def now_in_db() -> str:
    return psql("SELECT now();")


def orders_since(since: str) -> list[dict]:
    """Every order placed since `since`, with its lines by product name, and whether it had a key."""
    rows = psql(
        "SELECT json_build_object('id', o.id, 'key', o.idempotency_key IS NOT NULL, 'lines', "
        "(SELECT json_object_agg(p.name, l.quantity) FROM order_lines l JOIN products p ON p.id = l.product_id "
        "WHERE l.order_id = o.id)) "
        f"FROM orders o WHERE o.created_at >= '{since}' ORDER BY o.id;"
    )
    return [json.loads(line) for line in rows.splitlines() if line]


def describe(orders: list[dict]) -> str:
    if not orders:
        return "no order"
    return "; ".join("order " + ", ".join(f"{name} ×{q}" for name, q in sorted(o["lines"].items())) for o in orders)


def setup(client: httpx.Client, task: int) -> list[int]:
    """Archive this task's products from earlier runs, then add fresh ones."""
    for p in client.get(f"{BASE}/products").json():
        if p["sku"].startswith(f"EVAL-{task}-"):
            client.post(f"{BASE}/products/{p['id']}/archive")
    ids, stamp = [], int(time.time() * 1000)
    for n, (name, category, price, stock, archived) in enumerate(TASKS[task]["products"]):
        r = client.post(f"{BASE}/products", json={"sku": f"EVAL-{task}-{n}-{stamp}", "name": name, "category": category,
                                                  "price_cents": price, "stock": stock})
        r.raise_for_status()
        ids.append(r.json()["id"])
        if archived:
            client.post(f"{BASE}/products/{ids[-1]}/archive")
    return ids


def descriptions_id() -> str:
    """A short fingerprint of your tools' names, descriptions and arguments, as an agent sees them."""
    from mcp import Client

    async def go():
        async with Client(f"{BASE}/mcp") as client:
            tools = (await client.list_tools()).tools
            return json.dumps([[t.name, t.description, t.input_schema] for t in sorted(tools, key=lambda t: t.name)], sort_keys=True)

    return hashlib.sha256(asyncio.run(go()).encode()).hexdigest()[:8]


def run_agent(ask: str, model: str) -> dict:
    cmd = ["claude", "-p", ask, "--model", model, "--output-format", "json", "--setting-sources", "project,local",
           "--strict-mcp-config", "--mcp-config", str(AGENT / ".mcp.json")]
    try:
        r = subprocess.run(cmd, cwd=AGENT, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return {"result": "(no answer within 10 minutes)", "total_cost_usd": 0, "usage": {}}
    for line in reversed(r.stdout.strip().splitlines()):
        try:
            return json.loads(line)
        except ValueError:
            continue
    return {"result": (r.stderr or r.stdout).strip()[:300], "total_cost_usd": 0, "usage": {}}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the shopping evals against your customer agent.")
    parser.add_argument("--tasks", default="1,2,3,4,5")
    parser.add_argument("--model", default="haiku")
    parser.add_argument("--runs", type=int, default=1)
    a = parser.parse_args()
    tasks = [int(t) for t in a.tasks.split(",")]

    for need, why in ((AGENT / "CLAUDE.md", "your customer agent's brief"), (AGENT / ".mcp.json", "its tool server"),
                      (AGENT / ".claude" / "settings.json", "its settings")):
        if not need.exists():
            raise SystemExit(f"No {need.relative_to(ROOT)} ({why}). Step M5-4 makes it.")
    if not shutil.which("claude"):
        raise SystemExit("No claude command on your PATH.")
    try:
        httpx.get(f"{BASE}/health", timeout=3).raise_for_status()
    except httpx.HTTPError:
        raise SystemExit(f"Your store doesn't answer at {BASE}. Run `make up` first.")

    fingerprint = descriptions_id()
    started = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    print(f"Evals: {len(tasks)} task(s) × {a.runs} for your customer agent, on {a.model}, at {started}.")
    print(f"Your tool descriptions: {fingerprint}\n", flush=True)

    passed = total = keyed = placed = 0
    by_task: dict[int, list[bool]] = {}
    cost = tokens_in = tokens_out = 0
    with httpx.Client(timeout=30) as client:
        for run in range(1, a.runs + 1):
            if a.runs > 1:
                print(f"Run {run} of {a.runs}:", flush=True)
            for task in tasks:
                t = TASKS[task]
                ids = setup(client, task)
                since = now_in_db()
                answer = run_agent(t["ask"], a.model)
                orders = orders_since(since)
                for pid in ids:
                    client.post(f"{BASE}/products/{pid}/archive")
                ok = (not orders) if not t["want"] else (len(orders) == 1 and orders[0]["lines"] == t["want"])
                passed += ok
                total += 1
                placed += len(orders)
                keyed += sum(1 for o in orders if o["key"])
                cost += answer.get("total_cost_usd") or 0
                usage = answer.get("usage") or {}
                tokens_in += sum(usage.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
                tokens_out += usage.get("output_tokens") or 0
                by_task.setdefault(task, []).append(ok)
                want = describe([{"lines": t["want"]}]) if t["want"] else "no order"
                print(f"  {task} · {t['title']}: {'PASS' if ok else 'FAIL'}", flush=True)
                if not ok:
                    print(f"      asked: {t['ask']}")
                    print(f"      wanted {want}; got {describe(orders)}")
                    print(f"      the agent said: {' '.join(str(answer.get('result', '')).split())[:400]}", flush=True)

    print()
    if a.runs > 1:
        print("By task: " + " · ".join(f"{task} {sum(r)}/{len(r)}" for task, r in by_task.items()))
    print(f"Score: {passed}/{total}.")
    print(f"Orders placed with an idempotency key: {keyed} of {placed}.")
    print(f"This run: {total} agent sessions, about {tokens_in:,} tokens read and {tokens_out:,} written. "
          f"Claude Code priced it at ${cost:.2f}.")
    with open(RUNS, "a") as f:
        f.write(f"{started} · {a.model} · score {passed}/{total} · keys {keyed}/{placed} · tasks {a.tasks} × {a.runs} · "
                f"descriptions {fingerprint} · ${cost:.2f}\n")
    print(f"Saved to {RUNS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""The machinery behind the checks: the throwaway store, and the ways into it. You don't need to read this."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import httpx

ROOT = Path(__file__).resolve().parent.parent
LAST_RUN = ROOT / "checks" / "last-run.txt"
MILESTONES = {0: "Setup", 1: "Products, and the store's first tools", 2: "The admin side, and your first race"}


class Fail(Exception):
    """A check failed. `expected` and `got` are shown under it, then the hint."""

    def __init__(self, expected: str, got: str, hint: str = ""):
        super().__init__(got)
        self.expected, self.got, self.hint = expected, got, hint


@dataclass
class Check:
    milestone: int
    step: int
    title: str
    fn: Callable[["Ctx"], None]
    needs: tuple[str, ...] = ()
    gives: str | None = None


CHECKS: list[Check] = []


def check(milestone: int, step: int, title: str, needs: tuple[str, ...] = (), gives: str | None = None):
    """Register a check. `needs` names what must have passed first; `gives` names what this one proves."""

    def register(fn):
        CHECKS.append(Check(milestone, step, title, fn, needs, gives))
        return fn

    return register


def short(text: str, limit: int = 300) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + " …"


@dataclass
class Ctx:
    project: str
    port: int
    keep: bool
    started: bool = False
    proven: set[str] = field(default_factory=set)
    notes_cache: dict = field(default_factory=dict)

    @property
    def base(self) -> str:
        return f"http://localhost:{self.port}"

    def env(self) -> dict[str, str]:
        env = dict(os.environ)
        env["API_PORT"] = str(self.port)
        env["COMPOSE_PROJECT_NAME"] = self.project
        return env

    def run(self, args: list[str], stdin: str | None = None, env: dict | None = None, timeout: int = 120):
        return subprocess.run(
            args, cwd=ROOT, input=stdin, capture_output=True, text=True, env=env or self.env(), timeout=timeout
        )

    def compose(self, *args: str, stdin: str | None = None, timeout: int = 300):
        return self.run(["docker", "compose", "-p", self.project, *args], stdin=stdin, timeout=timeout)

    # --- the throwaway store ---

    def start(self) -> None:
        if self.started:
            return
        if not (ROOT / "docker-compose.yaml").exists():
            raise Fail("docker-compose.yaml in the top folder", "no such file", "milestones/M0/2-the-stack.md gives it.")
        print(f"  … starting a throwaway copy of your store (project {self.project}, port {self.port})", flush=True)
        self.compose("down", "-v", "--remove-orphans")
        t0 = time.time()
        up = self.compose("up", "-d", "--build", "--wait", timeout=900)
        self.started = True
        if up.returncode != 0:
            raise Fail("docker compose up succeeds", short(up.stderr or up.stdout, 1200),
                       "Run `make up` in your own store and read the error. The usual causes: a typo in "
                       "docker-compose.yaml or backend/Dockerfile, or a line missing from backend/requirements.txt.")
        deadline = time.time() + 60
        last = ""
        while time.time() < deadline:
            try:
                r = httpx.get(self.base + "/health", timeout=3)
                if r.status_code in (200, 503):
                    print(f"  … ready in {time.time() - t0:.0f}s", flush=True)
                    return
                last = f"{r.status_code} {short(r.text)}"
            except httpx.HTTPError as e:
                last = type(e).__name__
            time.sleep(1)
        logs = self.compose("logs", "--tail", "25", "api").stdout
        raise Fail("the API answers on /health within 60 seconds", last or "no answer", "The API's last log lines:\n" + logs)

    def stop(self) -> None:
        if self.started and not self.keep:
            self.compose("down", "-v", "--remove-orphans")

    # --- ways in ---

    def psql(self, sql: str, single_transaction: bool = False):
        """Run SQL in the throwaway database. Returns the finished process (returncode, stdout, stderr)."""
        args = ["exec", "-T", "db", "psql", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-U", "store", "-d", "store"]
        if single_transaction:
            args.append("-1")
        return self.compose(*args, stdin=sql)

    def sql_value(self, sql: str) -> str:
        r = self.psql(sql)
        if r.returncode != 0:
            raise Fail("the query runs", short(r.stderr))
        return r.stdout.strip()

    def py(self, script: str) -> dict:
        """Run a Python script inside the API container. It must print one line starting with RESULT: and JSON."""
        r = self.compose("exec", "-T", "api", "python", "-", stdin=script, timeout=120)
        for line in r.stdout.splitlines():
            if line.startswith("RESULT:"):
                return json.loads(line[len("RESULT:"):])
        raise Fail("the script runs inside your API container", short(r.stderr or r.stdout, 1200))

    def http(self, method: str, path: str, **kwargs) -> httpx.Response:
        return httpx.request(method, self.base + path, timeout=10, **kwargs)

    def cli(self, *args: str):
        """Run your ./store wrapper against the throwaway store."""
        return self.run(["./store", *args], timeout=60)

    def tools(self, calls: Callable) -> object:
        """Open one MCP session to the throwaway store and run `calls(client)` in it."""
        from mcp import Client

        async def go():
            async with Client(self.base + "/mcp") as client:
                return await calls(client)

        return asyncio.run(go())


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)




def http_json(ctx, method: str, path: str, **kw):
    r = ctx.http(method, path, **kw)
    try:
        body = r.json()
    except ValueError:
        body = r.text
    return r.status_code, body

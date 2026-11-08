"""Milestone 0: your tools, your own repository, your store's stack, and your rules file."""

import json
import os
import re

from kitlib import ROOT, Fail, check, git

# --- Step 1 · Your tools, and your own copy of the kit ---


@check(0, 1, "Docker is running")
def docker_running(ctx):
    r = ctx.run(["docker", "info", "--format", "{{.ServerVersion}}"])
    if r.returncode != 0:
        raise Fail("`docker info` answers", (r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout) else "no answer",
                   "Open Docker Desktop and wait until it says the engine is running.")


@check(0, 1, "this folder is a git repository, with the kit as the remote called kit")
def kit_remote(ctx):
    top = git("rev-parse", "--show-toplevel").stdout.strip()
    if os.path.realpath(top) != os.path.realpath(ROOT):
        raise Fail(f"a git repository whose top folder is {ROOT}", top or "not a git repository")
    url = git("remote", "get-url", "kit").stdout.strip()
    if "louis-store" not in url:
        raise Fail("a remote called kit, pointing at the kit (…/louis-store)", url or "no remote called kit",
                   "git remote rename origin kit   (milestones/M0/1-tools-and-your-repo.md, part 5)")


@check(0, 1, "your own GitHub repository is the remote called origin")
def own_remote(ctx):
    url = git("remote", "get-url", "origin").stdout.strip()
    if not url:
        raise Fail("a remote called origin, on github.com", "no remote called origin",
                   "Create your repository with gh (milestones/M0/1-tools-and-your-repo.md, part 5).")
    if "github.com" not in url or "louis-store" in url:
        raise Fail("origin points at your own repository on github.com", url,
                   "origin must be yours, not the kit. See milestones/M0/1-tools-and-your-repo.md, part 5.")


# --- Step 2 · The store's stack ---


@check(0, 2, ".env exists and sets your own POSTGRES_PASSWORD")
def env_file(ctx):
    env = ROOT / ".env"
    if not env.exists():
        raise Fail("a file called .env in the top folder", "no .env", "cp .env.example .env, then change the password.")
    values = dict(
        line.split("=", 1) for line in env.read_text().splitlines() if "=" in line and not line.lstrip().startswith("#")
    )
    password = values.get("POSTGRES_PASSWORD", "").strip()
    if not password:
        raise Fail("POSTGRES_PASSWORD=<something>", "no POSTGRES_PASSWORD line, or an empty one")
    if password == "change-me":
        raise Fail("a password of your own", "still the example's change-me", "Edit .env and pick a password.")
    if not re.fullmatch(r"[A-Za-z0-9]+", password):
        raise Fail("a password of letters and digits only", "it has other characters",
                   "Symbols like @ / : # break the database address the password goes into.")


@check(0, 2, "git ignores .env, so the password never reaches GitHub")
def env_ignored(ctx):
    if git("check-ignore", "-q", ".env").returncode != 0:
        raise Fail(".env listed in .gitignore", "git doesn't ignore .env", "Put the kit's .gitignore back: git checkout kit/main -- .gitignore")
    if git("ls-files", "--error-unmatch", ".env").returncode == 0:
        raise Fail(".env never committed", ".env is tracked by git",
                   "git rm --cached .env, commit, and change the password: it is in your history now.")


@check(0, 2, "the compose project is called store")
def project_name(ctx):
    if not (ROOT / "docker-compose.yaml").exists():
        raise Fail("docker-compose.yaml in the top folder", "no such file", "milestones/M0/2-the-stack.md gives it.")
    env = {k: v for k, v in ctx.env().items() if k != "COMPOSE_PROJECT_NAME"}
    r = ctx.run(["docker", "compose", "config", "--format", "json"], env=env)
    if r.returncode != 0:
        raise Fail("docker compose config reads docker-compose.yaml", r.stderr.strip()[-600:],
                   "Check docker-compose.yaml against the guide, line by line. Indentation is two spaces.")
    name = json.loads(r.stdout).get("name")
    if name != "store":
        raise Fail("name: store", f"name: {name}", "The first line of docker-compose.yaml is `name: store`.")


@check(0, 2, "a fresh copy of your store starts, and GET /health answers ok", gives="your store starts")
def health(ctx):
    ctx.start()
    r = ctx.http("GET", "/health")
    want = {"status": "ok", "database": "ok"}
    if r.status_code != 200 or r.json() != want:
        raise Fail(f"200 {json.dumps(want)}", f"{r.status_code} {r.text[:300]}",
                   "Compare backend/main.py and backend/db.py with the guide, and read `make logs`.")


# --- Step 3 · Your rules file ---


@check(0, 3, "AGENTS.md is written, in your own words")
def agents_md(ctx):
    path = ROOT / "AGENTS.md"
    if not path.exists():
        raise Fail("AGENTS.md in the top folder", "no AGENTS.md", "Start from templates/AGENTS.md.")
    text = re.sub(r"<!--.*?-->", "", path.read_text(), flags=re.S)
    template = re.sub(r"<!--.*?-->", "", (ROOT / "templates" / "AGENTS.md").read_text(), flags=re.S)
    if text.split() == template.split():
        raise Fail("your own rules", "the template, unchanged", "Write your rules under each heading.")
    words = len(text.split()) - len(template.split())
    if words < 60:
        raise Fail("at least 60 words of your own", f"{max(words, 0)} words beyond the template's headings")


@check(0, 3, "CLAUDE.md imports AGENTS.md")
def claude_md(ctx):
    path = ROOT / "CLAUDE.md"
    if not path.exists():
        raise Fail("CLAUDE.md in the top folder", "no CLAUDE.md")
    if "@AGENTS.md" not in [line.strip() for line in path.read_text().splitlines()]:
        raise Fail("a line that is exactly @AGENTS.md", "no such line",
                   "With a CLAUDE.md in the folder, Claude Code reads AGENTS.md only through that line.")

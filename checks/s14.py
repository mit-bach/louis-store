"""Optional spec 14: your own migration runner, backend/migrate.py.

Each check runs your runner inside the throwaway store's API container, against a database of its own,
on a copy of your migrations in /tmp there, so it can add and edit files without touching yours.
"""

import hashlib
import subprocess

from kitlib import ROOT, Fail, check, ready, short

MIGRATIONS = ROOT / "backend" / "migrations"


def files() -> list[str]:
    return sorted(f.name for f in MIGRATIONS.glob("*.sql"))


def sums() -> dict[str, str]:
    return {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in MIGRATIONS.glob("*.sql")}


def database(ctx, name: str) -> str:
    """A new, empty database in the throwaway store, and its DATABASE_URL."""
    ctx.psql(f"DROP DATABASE IF EXISTS {name} WITH (FORCE);")
    r = ctx.psql(f"CREATE DATABASE {name};")
    if r.returncode != 0:
        raise Fail(f"a database {name} can be made", short(r.stderr))
    base = ctx.compose("exec", "-T", "api", "printenv", "DATABASE_URL").stdout.strip()
    return base.rsplit("/", 1)[0] + "/" + name


def folder(ctx, name: str) -> str:
    """A copy of your migrations inside the container, to add files to and edit."""
    ctx.compose("exec", "-T", "api", "sh", "-c", f"rm -rf /tmp/{name} && cp -r /app/migrations /tmp/{name}")
    return f"/tmp/{name}"


def in_container(ctx, script: str):
    return ctx.compose("exec", "-T", "api", "sh", "-c", script)


def migrate_cmd(ctx, url: str, path: str) -> list[str]:
    return ["docker", "compose", "-p", ctx.project, "exec", "-T", "-e", f"DATABASE_URL={url}", "api", "python", "migrate.py", path]


def migrate(ctx, url: str, path: str):
    return ctx.run(migrate_cmd(ctx, url, path), timeout=180)


def recorded(ctx, name: str) -> dict[str, str | None]:
    r = ctx.compose("exec", "-T", "db", "psql", "-X", "-A", "-t", "-F", "|", "-U", "store", "-d", name, "-c",
                    "SELECT filename, coalesce(checksum, '') FROM schema_migrations ORDER BY filename;")
    if r.returncode != 0:
        raise Fail("schema_migrations can be read", short(r.stderr))
    return {line.split("|")[0]: (line.split("|")[1] or None) for line in r.stdout.splitlines() if line}


def applying(text: str) -> list[str]:
    return [line.removeprefix("applying ").strip() for line in text.splitlines() if line.startswith("applying ")]


@check(14, 1, "backend/migrate.py applies every migration to an empty database, in filename order, each recorded with its SHA-256",
       gives="a runner")
def applies_in_order(ctx):
    if not (ROOT / "backend" / "migrate.py").exists():
        raise Fail("backend/migrate.py", "no such file")
    ready(ctx)
    url = database(ctx, "spec14_fresh")
    r = migrate(ctx, url, folder(ctx, "m14_fresh"))
    if r.returncode != 0:
        raise Fail("exit 0", f"exit {r.returncode}: {short(r.stderr or r.stdout, 600)}")
    if applying(r.stdout) != files():
        raise Fail("applying " + ", then ".join(files()), short(r.stdout, 600), "sorted() on the file names gives their order.")
    if recorded(ctx, "spec14_fresh") != sums():
        raise Fail("each file in schema_migrations, with the SHA-256 of its bytes", short(str(recorded(ctx, "spec14_fresh")), 400),
                   "hashlib.sha256(path.read_bytes()).hexdigest()")


@check(14, 2, "run again, it applies nothing; a new file is applied once, and only that file", needs=("a runner",))
def applies_once(ctx):
    url = database(ctx, "spec14_again")
    path = folder(ctx, "m14_again")
    migrate(ctx, url, path)
    again = migrate(ctx, url, path)
    if again.returncode != 0 or applying(again.stdout):
        raise Fail("exit 0, applying nothing", f"exit {again.returncode}: {short(again.stdout + again.stderr, 400)}")
    in_container(ctx, f"echo 'CREATE TABLE spec14_new (id INTEGER);' > {path}/900_check_new.sql")
    new = migrate(ctx, url, path)
    third = migrate(ctx, url, path)
    if applying(new.stdout) != ["900_check_new.sql"] or applying(third.stdout):
        raise Fail("applying 900_check_new.sql, then nothing", f"{short(new.stdout, 200)} / {short(third.stdout, 200)}")


@check(14, 3, "an applied file that was edited stops the run: exit 4, a message naming it, and nothing new applied", needs=("a runner",))
def refuses_edited(ctx):
    url = database(ctx, "spec14_edited")
    path = folder(ctx, "m14_edited")
    migrate(ctx, url, path)
    first = files()[0]
    in_container(ctx, f"printf '\\n-- edited\\n' >> {path}/{first} && "
                      f"echo 'CREATE TABLE spec14_later (id INTEGER);' > {path}/901_check_later.sql")
    r = migrate(ctx, url, path)
    want = f"{first} was edited after it was applied. Put it back as it was, and write a new migration for the change."
    if r.returncode != 4 or r.stderr.strip() != want:
        raise Fail(f"exit 4, and on stderr: {want}", f"exit {r.returncode}, stderr {short(r.stderr, 300)!r}",
                   "Compare every applied file's checksum before applying anything.")
    if "901_check_later.sql" in recorded(ctx, "spec14_edited"):
        raise Fail("901_check_later.sql not applied", "it was", "Stop before applying anything new.")


@check(14, 4, "a database make migrate set up: the runner records each file's checksum, and runs nothing again", needs=("a runner",))
def adopts_make_migrate(ctx):
    url = database(ctx, "spec14_old")
    sql = ["CREATE TABLE schema_migrations (filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now());"]
    for f in sorted(MIGRATIONS.glob("*.sql")):
        sql += [f.read_text(), f"INSERT INTO schema_migrations (filename) VALUES ('{f.name}');"]
    r = ctx.compose("exec", "-T", "db", "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-U", "store", "-d", "spec14_old",
                    stdin="\n".join(sql))
    if r.returncode != 0:
        raise Fail("a database as make migrate leaves it", short(r.stderr))
    r = migrate(ctx, url, folder(ctx, "m14_old"))
    if r.returncode != 0 or applying(r.stdout):
        raise Fail("exit 0, applying nothing", f"exit {r.returncode}: {short(r.stdout + r.stderr, 500)}",
                   "A row without a checksum was applied by make migrate: record its checksum, and don't run it again.")
    if recorded(ctx, "spec14_old") != sums():
        raise Fail("every file's checksum recorded", short(str(recorded(ctx, "spec14_old")), 400))


@check(14, 5, "two runs at the same moment: both succeed, and each file is applied exactly once", needs=("a runner",))
def two_at_once(ctx):
    for attempt in range(3):
        url = database(ctx, f"spec14_two_{attempt}")
        path = folder(ctx, f"m14_two_{attempt}")
        procs = [subprocess.Popen(migrate_cmd(ctx, url, path), cwd=ROOT, env=ctx.env(), stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True) for _ in range(2)]
        outs = [p.communicate(timeout=180) + (p.returncode,) for p in procs]
        codes = [code for _, _, code in outs]
        applied = [name for out, _, _ in outs for name in applying(out)]
        if codes != [0, 0] or sorted(applied) != files():
            raise Fail("both exit 0, and between them each file applied once",
                       f"exits {codes}; applied {applied}; {short(' / '.join(err for _, err, _ in outs), 500)}",
                       "Take one lock for the whole run, so the second run waits, then finds everything applied.")

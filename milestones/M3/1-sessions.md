# Step M3-1 · Sessions: a visitor without an account

**Why:** a cart belongs to someone. Your store has no accounts and no passwords: a visitor just starts shopping. So the store hands each visitor a **session**, and every cart request says which session it belongs to.

## The idea: a token

A session is a row in a table, and its **token** is a long random string that names it. The store gives the token to the visitor, the visitor sends it back with every cart request, and the store looks it up.

- **Random, and long.** `secrets.token_urlsafe(32)`, from Python's `secrets` module, makes 32 random bytes and writes them as 43 characters that are safe in a web address. Nobody can guess one. Python's other random module, `random`, is predictable, so it's never used for tokens.
- **A token is a key.** Whoever holds it can use that session's cart. So it's never written in logs or pages, and it's checked on every request.
- **It expires.** A session works for an hour. Then its token is refused, and the visitor starts a new one. A key that stops working on its own limits the damage when one leaks.
- **Three ways to be refused.** No token at all, a token the store never issued, and a token whose hour is up. Each gets its own message, because each needs a different fix.

**An example on a different table:** a library that issues cards. The table:

```sql
CREATE TABLE cards (
    token      TEXT        PRIMARY KEY,
    issued_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + interval '1 day'
);
```

`DEFAULT now() + interval '1 day'` works out the expiry when the row is inserted. Its operations, in their own module:

```python
import secrets

from db import pool
from schemas import Card


class NoCard(Exception):
    """Raised when a request has no library card, or one that doesn't work."""


def issue_card() -> Card:
    token = secrets.token_urlsafe(32)
    with pool.connection() as conn:
        row = conn.execute(
            "INSERT INTO cards (token) VALUES (%s) RETURNING token, expires_at",
            (token,),
        ).fetchone()
    return Card(**row)


def require_card(token: str | None) -> str:
    if not token:
        raise NoCard("No library card. Get a card, then show it with every basket request.")
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT expires_at > now() AS valid FROM cards WHERE token = %s",
            (token,),
        ).fetchone()
    if row is None:
        raise NoCard("That library card doesn't exist. Get a new one.")
    if not row["valid"]:
        raise NoCard("That library card has expired. Get a new one.")
    return token
```

- `SELECT expires_at > now() AS valid` asks Postgres to compare the times, so the answer uses the database's clock, the same clock that set `expires_at`.
- `if not token:` catches both `None` and an empty string.
- One error class, three messages: every way in maps `NoCard` the same way, and the message says which fix is needed.

## You write

- **`backend/migrations/003_create_sessions.sql`:** the `sessions` table, as [`CONTRACT.md`](../../CONTRACT.md) describes it in "M3 · Sessions". Apply it with `make migrate`.
- **`backend/schemas.py`:** `Session`, with `token` and `expires_at`.
- **`backend/sessions.py`,** a new module: `NoSession`, `start_session()` and `require_session(token)`, with the contract's three messages, exactly.
- **`backend/main.py`:** `POST /sessions`, answering `201` with the `Session`.
- **`backend/tools.py`:** the `start_session` tool. Its docstring tells the agent to pass the token to every cart tool, and that whoever holds it can use the cart.
- **`backend/cli.py`:** a new command group, then `session start` in it.

**The command group is given.** Under the line `app.add_typer(products_app, name="products")`, add:

```python
session_app = typer.Typer(help="Visitor sessions: a cart belongs to one.", no_args_is_help=True)
app.add_typer(session_app, name="session")
```

Then your command is `@session_app.command("start")`.

**Hint:** `require_session` returns the token it was given, when it's good. The cart operations in the next step will call it first, and carry on with the token.

## Check

```
make migrate
```

```
applying backend/migrations/003_create_sessions.sql
migrations up to date
```

A session over HTTP:

```
curl -s -w '\n%{http_code}\n' -X POST http://localhost:8000/sessions
```

```
{"token":"4dO1EmPboUE_WmY2JxUV7K5i-OAMd12kWRT6ohkdO6A","expires_at":"2026-11-08T19:25:52.450702Z"}
201
```

And from the command line:

```
./store session start
```

```
{
  "token": "8CWDDlF7ogt29bxDCGvhsSOyZ4xumdKR_4kPo3yBAdw",
  "expires_at": "2026-11-08T19:25:52.923415Z"
}
```

Every token is different. Run it twice and compare.

```
make check M=3 STEP=1
```

**You should see** everything before, then:

```
  PASS  M3-1  sessions.py and cart.py import nothing from the web, the command line or the tool server
  PASS  M3-1  the sessions table: a token as its key, and when it expires
  PASS  M3-1  start_session() makes a long random token, valid for an hour
  PASS  M3-1  require_session() names what's wrong: no token, a made-up token, an expired one
  PASS  M3-1  POST /sessions, ./store session start and the start_session tool each start a session

76 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

The check makes an expired session by inserting one whose `expires_at` has already passed, so it doesn't wait an hour.

## Step done

```
git status --short
```

```
 M JOURNAL.md
 M PREDICTIONS.md
 M backend/cli.py
 M backend/main.py
 M backend/schemas.py
 M backend/tools.py
?? backend/migrations/003_create_sessions.sql
?? backend/sessions.py
```

```
git add -A
git commit -m "M3-1: sessions"
git push
```

Answer your tutor's questions under `## M3-1` in `JOURNAL.md`.

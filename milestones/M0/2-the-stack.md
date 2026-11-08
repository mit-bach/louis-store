# Step M0-2 · The store's stack: an API and its database, in Docker

**Why:** the store needs two programs running all the time.
- **The API** answers requests over HTTP. It's written in Python with FastAPI, a library that turns Python functions into web routes.
- **The database** keeps the data. It's Postgres, the database most web backends use, and the one cloud services like Amazon RDS run for you.

You'll run each in its own container, described in one file, so a single command starts both, the same way on any Mac.

This step is all **given**: six short files, each explained line by line, then one prediction.

## The idea: images, containers, and a compose file

- **An image** is built from a recipe called a **Dockerfile**: start from an image with Python in it, copy in your code, install its libraries.
- **A container** is one running copy of an image.
- **Docker Compose** runs several containers together, as one **project**, from a file called `docker-compose.yaml`. It gives each container a **service** name, and containers in the same project reach each other by those names. Your API will find the database at the address `db`.
- **A volume** is storage that outlives containers. The database keeps its files in one, so your data survives when its container is removed and recreated.

## 1. `backend/requirements.txt`

Create the folder `backend/`, and in it a file called `requirements.txt` with exactly this:

```
fastapi==0.162.0
uvicorn[standard]==0.54.0
psycopg[binary]==3.3.6
psycopg-pool==3.3.3
```

**What each line does.** Each line names a Python library and pins its exact version, so your store builds the same way next month:
- **`fastapi`** turns Python functions into web routes.
- **`uvicorn[standard]`** is the server that runs a FastAPI app and listens for requests. `[standard]` adds its faster extras, including the file watcher that restarts it when you save a file.
- **`psycopg[binary]`** lets Python talk to Postgres. `[binary]` brings it ready-built, so nothing has to compile.
- **`psycopg-pool`** keeps a few database connections open and lends them out, which you'll meet in part 5.

## 2. `backend/Dockerfile`

Create `backend/Dockerfile` (no extension) with exactly this:

```dockerfile
FROM python:3.14.8-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**What each line does:**
- **`FROM python:3.14.8-slim`** starts from the official image with Python 3.14.8 on a small Linux system.
- **`ENV PYTHONUNBUFFERED=1`** makes Python print immediately, so what your code prints shows up in the logs right away.
- **`ENV PYTHONDONTWRITEBYTECODE=1`** stops Python leaving `__pycache__` folders among your files.
- **`WORKDIR /app`** makes `/app` the folder everything else happens in, inside the container.
- **`COPY requirements.txt ./`** then **`RUN pip install …`** copy the list of libraries in first, and install them. They come before the rest of your code on purpose: Docker reuses each step's result until its input changes, so editing your code later doesn't reinstall every library.
- **`COPY . .`** copies the rest of `backend/` into `/app`.
- **`CMD [...]`** is the command the container runs: uvicorn, serving the object `app` from the file `main.py`, on port 8000. `--host 0.0.0.0` makes it answer requests from outside the container, not just from inside it.

## 3. `docker-compose.yaml`

In the top folder (`~/code/store`, not `backend/`), create `docker-compose.yaml` with exactly this:

```yaml
name: store

services:
  api:
    build: ./backend
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "${API_PORT:-8000}:8000"
    volumes:
      - ./backend:/app
    environment:
      DATABASE_URL: postgresql://store:${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}@db:5432/store
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 2s
      timeout: 5s
      retries: 15

  db:
    image: postgres:17.10
    environment:
      POSTGRES_USER: store
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}
      POSTGRES_DB: store
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "store", "-d", "store"]
      interval: 2s
      timeout: 5s
      retries: 15

volumes:
  pgdata:
```

**YAML's rules:** indentation is **two spaces**, never a tab, and it decides what belongs to what. `name: value` sets something. A line starting with `- ` is one item in a list.

**What each part does:**
- **`name: store`** names the project. Your containers will be called `store-api-1` and `store-db-1`. Without it, Compose would name the project after the folder, and two projects in folders with the same name would get mixed up.
- **`services:`** lists the two containers: `api` and `db`.
- **The `api` service:**
  - **`build: ./backend`** builds its image from `backend/Dockerfile`.
  - **`command: … --reload`** replaces the Dockerfile's `CMD` while you develop. `--reload` restarts the server whenever you save a Python file.
  - **`ports: "${API_PORT:-8000}:8000"`** connects port 8000 on your Mac to port 8000 in the container, so `http://localhost:8000` reaches your API. `${API_PORT:-8000}` means "the setting `API_PORT` if there is one, otherwise 8000". You'll never set it; the checks do, to start their throwaway copy of your store on port 8001 next to yours.
  - **`volumes: ./backend:/app`** shows the container your `backend/` folder live, so the code it runs is always the code you just saved.
  - **`DATABASE_URL`** tells your code where the database is, as one line: `postgresql://USER:PASSWORD@HOST:PORT/DATABASE`. The host is **`db`**, the other service's name. Inside a container, `localhost` would mean the container itself, which is the classic first trap.
  - **`${POSTGRES_PASSWORD:?…}`** is filled in from your `.env` file (part 4). If it's missing, Compose stops with the message after the `?`, instead of starting a database with no password.
  - **`depends_on` with `service_healthy`** waits until the database is ready before starting the API.
  - **`healthcheck`** asks the API's own `/health` route every 2 seconds, giving up after 15 tries. The API counts as healthy once it answers. `make up` waits for that, so when it returns, your store is really ready.
- **The `db` service:**
  - **`image: postgres:17.10`** is the official Postgres image, pinned to version 17.10.
  - **`environment:`** creates a user `store`, with your password, and a database `store`, the very first time it starts.
  - **`volumes: pgdata:/var/lib/postgresql/data`** keeps the database's files in the volume `pgdata`.
  - **`healthcheck:`** runs `pg_isready`, Postgres's own "are you accepting connections?" tool, every 2 seconds.
- **`volumes: pgdata:`** at the bottom declares the volume.

## 4. `.env`, your settings

The kit has a file called `.env.example`. Copy it:

```
cp .env.example .env
```

Open `.env` and change `change-me` to a password of your own. Use **only letters and digits**: the password goes inside the database address in part 3, where symbols like `@`, `/` or `:` would break it.

**Why two files.** `.env` holds your real password, and git ignores it: the kit's `.gitignore` lists it, so it can never be committed or pushed. `.env.example` has the same names with a fake value, and it *is* committed, so anyone who clones the repository knows which settings to create.

**One thing to know for later:** Postgres creates its user and password only on its very first start. If you change the password in `.env` afterwards, it won't take effect until you delete the volume with `docker compose down -v`, which also deletes all the data.

## 5. `backend/db.py`, the connection pool

Create `backend/db.py` with exactly this:

```python
import os

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

pool = ConnectionPool(
    os.environ["DATABASE_URL"],
    kwargs={"row_factory": dict_row},
    check=ConnectionPool.check_connection,
    open=True,
)
```

**The idea.** Opening a connection to Postgres takes a few milliseconds: a network handshake, a login, setting up a session. Doing that for every request would be slow. A **connection pool** opens a few connections when the app starts, and lends one to each piece of code that needs it, taking it back afterwards.

**What each part does:**
- **`os.environ["DATABASE_URL"]`** reads the address you set in part 3. It exists only inside the container, so always run your API through Docker, not directly on your Mac.
- **`kwargs={"row_factory": dict_row}`** makes each row come back as a dictionary, like `{"id": 1, "name": "Solo Tent"}`, instead of a bare list of values.
- **`check=ConnectionPool.check_connection`** makes the pool test each connection before lending it out. If the database restarted, the connections the pool held are dead, and without this your next request would be handed one and fail.
- **`open=True`** starts connecting straight away.

## 6. `backend/main.py`, with one route

Create `backend/main.py` with exactly this:

```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from db import pool

app = FastAPI(title="Store")


@app.get("/health")
def health():
    try:
        with pool.connection(timeout=2) as conn:
            conn.execute("SELECT 1")
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "unreachable"},
        )
    return {"status": "ok", "database": "ok"}
```

**What each part does:**
- **`app = FastAPI(title="Store")`** creates the app that uvicorn serves.
- **`@app.get("/health")`** on top of a function means: when a `GET` request arrives at `/health`, run this function, and send back what it returns as JSON.
- **`with pool.connection(timeout=2) as conn:`** borrows a connection for the lines indented under it, and gives it back when they finish. `timeout=2` gives up after 2 seconds if none can be had.
- **`conn.execute("SELECT 1")`** is the smallest possible question to a database. If it answers, the database is up.
- **`except Exception:`** catches anything that goes wrong, and answers `503 Service Unavailable` with a body that says why. A health check has to report a broken database, not break itself.

## 7. Start it

```
make up
```

`make up` runs `docker compose up -d --build --wait`: build the image, start both containers in the background (`-d`), and wait until both are healthy. **The first time,** Docker downloads Python and Postgres and installs the libraries, which can take a few minutes. **You should see** many lines of build output, ending like this:

```
 Container store-api-1 Waiting
 Container store-db-1 Waiting
 Container store-db-1 Healthy
 Container store-api-1 Healthy
```

Then:

```
docker compose ps --format 'table {{.Name}}\t{{.Service}}\t{{.Status}}'
```

**You should see** both containers up and healthy (your seconds will differ):

```
NAME          SERVICE   STATUS
store-api-1   api       Up 2 seconds (healthy)
store-db-1    db        Up 5 seconds (healthy)
```

Then ask your API how it is:

```
curl http://localhost:8000/health
```

**You should see:**

```
{"status":"ok","database":"ok"}
```

`curl` sends one HTTP request and prints the answer. Your terminal may print a `%` after it, which only means the answer didn't end with a new line.

**If something doesn't match:**
- `make up` says `Set POSTGRES_PASSWORD in .env`: your `.env` is missing, or has no `POSTGRES_PASSWORD=` line.
- `make up` fails with a YAML error: compare your `docker-compose.yaml` with part 3, line by line. A tab instead of spaces, or one space too few, is the usual cause.
- `make up` says the `api` container is unhealthy: run `make logs` and read the last lines. A typo in `main.py` or `db.py` shows up there as a Python error, with the file and line.
- `port is already allocated`: something else on your Mac uses port 8000. Add a line `API_PORT=8080` to `.env`, run `make up` again, and use 8080 instead of 8000 in this guide's commands.

## 8. Predict, then stop the database

**Predict.** Your API is running, and in a moment you'll stop the database under it. Before you run anything, write one line in `PREDICTIONS.md`, under `## M0-2`: what will `/health` answer while the database is stopped, and how long will it take to answer?

Then stop the database, and ask:

```
docker compose stop db
curl -s -w '\nstatus %{http_code}, after %{time_total} seconds\n' http://localhost:8000/health
```

(`-w` makes curl add a line with the status code and how long it took.) **You should see:**

```
{"status":"error","database":"unreachable"}
status 503, after 2.004523 seconds
```

The API didn't crash, and didn't hang: it waited for its 2-second timeout, then reported the problem with a `503`. Now bring the database back. `make up` starts whatever isn't running, and waits until everything is healthy:

```
make up
curl http://localhost:8000/health
```

**You should see** `{"status":"ok","database":"ok"}` again. That's this milestone's manual check. Write what actually happened under your prediction.

## Check

```
make check M=0 STEP=2
```

**You should see** (your times will differ):

```
Store checks · M0 up to step 2 · 2026-11-08 12:42 EST

M0 · Setup
  PASS  M0-1  Docker is running
  PASS  M0-1  this folder is a git repository, with the kit as the remote called kit
  PASS  M0-1  your own GitHub repository is the remote called origin
  PASS  M0-2  .env exists and sets your own POSTGRES_PASSWORD
  PASS  M0-2  git ignores .env, so the password never reaches GitHub
  PASS  M0-2  the compose project is called store
  … starting a throwaway copy of your store (project store-check, port 8001)
  … ready in 6s
  PASS  M0-2  a fresh copy of your store starts, and GET /health answers ok

7 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

The throwaway copy runs as the project `store-check` on port 8001, so it never touches your store. **The first time,** it builds its own image, which takes a minute longer.

## Step done

First, look at what git sees:

```
git status --short
```

**You should see** exactly these two lines. `??` means "new, not yet committed", and a folder stands for everything in it:

```
?? backend/
?? docker-compose.yaml
```

`.env` **must not** be listed. It isn't, because `.gitignore` names it. Then commit and push:

```
git add -A
git commit -m "M0-2: the store's stack"
git push
```

In `JOURNAL.md`, under `## M0-2`, answer your tutor's questions for this step.

# M1 · Products, and the store's first tools

**About two days.**

## What works at the end

Your store has a catalogue, and every way in reaches it:
- `curl http://localhost:8000/products` lists your products as JSON;
- `./store products list` prints the same JSON, from the command line;
- your coding agent, connected to your store's tools, adds three products when you ask it to, and `./store products list` shows them.

Underneath, there's one module of operations, `backend/products.py`, which knows nothing about the web, the command line or agents. Three thin adapters call it: your routes, your commands and your tools.

## Who writes what

- **Yours, by hand:**
  - `backend/migrations/001_create_products.sql`, the products table, after six design decisions;
  - `backend/seed.sql`, at least 8 products from a catalogue you choose;
  - `backend/schemas.py`, the shapes of the data;
  - `backend/products.py`, the operations: list, get and create;
  - the routes in `backend/main.py`, the commands in `backend/cli.py` and the tools in `backend/tools.py`.
- **Given, and you type it in:**
  - the skeletons of `backend/cli.py` and `backend/tools.py`;
  - the lines that mount the tool server in `backend/main.py`;
  - the `./store` script;
  - one new line each in `backend/requirements.txt`, for the command-line and tool libraries.

## The steps

1. [The products table](1-the-products-table.md): design it, then write it as your first migration.
2. [The seed](2-the-seed.md): your catalogue.
3. [The data shapes, and reading products](3-shapes-and-reading.md): `schemas.py`, `list_products` and `get_product`.
4. [Creating a product](4-creating-a-product.md): `create_product`, and what to do about a duplicate SKU.
5. [The HTTP routes](5-the-http-routes.md): the first way in.
6. [The command line](6-the-command-line.md): the second way in, and the one agents in a terminal use.
7. [The tools](7-the-tools.md): the third way in, your agent connected, and the parity check.

## M1 is done when

1. `make check M=1` passes. The end of step 7 shows exactly what that looks like.
2. **The manual check:** in a fresh session, your agent added three products through your tools, and `./store products list` shows them (step 7).
3. **The review:** you've given an agent `reviewer/REVIEWER.md` and asked it to review your M1 changes. In `JOURNAL.md`, under `## M1 review`, each thing it found is listed, with what you did: fixed, or why not.
4. **`JOURNAL.md`** has each step's decisions, and your answers to your tutor's questions.
5. **`PREDICTIONS.md`** has each step's predictions, with what happened.
6. **It's committed and pushed.**

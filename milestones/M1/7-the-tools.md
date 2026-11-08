# Step M1-7 · The tools

**Why:** the third way in, and the one built for agents. A coding agent can find your command line only if it reads your files or your rules. A **tool** announces itself: the moment your agent connects to your store, it sees each tool's name, what it's for, and what it takes. An agent's power in your store is exactly its list of tools, and from this step on, it has one.

## The idea: MCP, and what a tool is

**MCP**, the Model Context Protocol, is a standard way for an agent to find and call tools that live in another program. Your store becomes an **MCP server**, running inside your API, at `http://localhost:8000/mcp`. Claude Code becomes its **client**: it connects, asks for the list of tools, and calls them when it decides to.

A tool is built from a Python function, and every part of the function becomes part of what the agent sees:
- **its name,** like `get_product`, is the tool's name;
- **its docstring** is the tool's description, the agent's only explanation of what it does;
- **its parameters and their types** become the tool's input schema, the shape its arguments must have. A parameter typed with a Pydantic model, like `book: BookCreate`, brings that model's fields, rules and `description`s along;
- **what it returns** is the result the agent reads.

**Errors.** A tool that fails returns an error the agent reads, and decides what to do next with. If the tool raises **`ToolError`** with a message, the agent sees that message. Any other exception counts as a crash, and the agent sees only `Error executing tool get_product`, with nothing about why. Each tool does what your routes and commands do: it catches the operation's named error, and raises `ToolError(str(e))` instead.

## 1. A new library: the MCP SDK

Add one line to the end of `backend/requirements.txt`:

```
mcp==2.3.0
```

Then rebuild:

```
make up
```

## 2. `backend/tools.py` (given skeleton)

Create `backend/tools.py` with exactly this:

```python
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

mcp = MCPServer("store", instructions="Tools for running an online store: its catalogue, and later carts and orders.")


# Your tools go here, between this line and the line at the bottom.


http_app = mcp.streamable_http_app(streamable_http_path="/mcp", stateless_http=True, json_response=True)
```

**What each part does:**
- **`MCPServer("store", instructions=…)`** is the tool server. Its name is how Claude Code lists it, and its instructions are a line the agent reads about the server as a whole.
- **`ToolError`** is the error that reaches the agent with its message.
- **`http_app`** is the tool server as a small web app, which `main.py` mounts inside your API. `streamable_http_path="/mcp"` is its address. `stateless_http=True` and `json_response=True` make every call a plain request and answer, which is all your tools need.

## 3. Mount it in `backend/main.py` (given)

Four small changes:
1. **At the very top,** add this line, then an empty line:

   ```python
   from contextlib import asynccontextmanager
   ```

2. **Under `import products`,** add:

   ```python
   import tools
   ```

3. **Replace** the line `app = FastAPI(title="Store")` with:

   ```python
   @asynccontextmanager
   async def lifespan(app: FastAPI):
       async with tools.mcp.session_manager.run():
           yield
   
   
   app = FastAPI(title="Store", lifespan=lifespan)
   ```

4. **At the very end of the file,** after your last route, add:

   ```python
   app.mount("/", tools.http_app)
   ```

**What they do:**
- **The `lifespan`** is code that runs while your API runs. The tool server needs a manager running in the background to handle its sessions; `async with … run():` starts it when the API starts, and stops it when the API stops. `yield` is the moment in between, the whole time your API is up. `async` marks code that can wait without blocking; you won't need to write any yourself in this milestone.
- **`app.mount("/", tools.http_app)`** hands every request your routes don't answer to the tool server, which answers `/mcp`. It goes last, so your own routes are always matched first.

Save, and check that your routes still work: `curl http://localhost:8000/products/1`.

## 4. Your tools

**An example on a different table,** two of the library's tools:

```python
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

import books
from schemas import Book, BookCreate

mcp = MCPServer("library", instructions="Tools for a small lending library.")


@mcp.tool()
def get_book(book_id: int) -> Book:
    """Get one book by its id, with how many copies the library owns."""
    try:
        return books.get_book(book_id)
    except books.BookNotFound as e:
        raise ToolError(str(e))


@mcp.tool()
def add_book(book: BookCreate) -> Book:
    """Add a book to the library. The ISBN must not be in the library already."""
    try:
        return books.add_book(book)
    except books.DuplicateIsbn as e:
        raise ToolError(str(e))
```

`@mcp.tool()` on top of a function makes it a tool, named after the function. The library passes `book` whole to `add_book`, because it's already a `BookCreate`.

**You write, in `backend/tools.py`,** between the comment and the `http_app` line:
- the imports: `import products`, and `Product` and `ProductCreate` from `schemas`;
- **`list_products`**, with no parameters, returning `list[Product]`;
- **`get_product(product_id: int)`**, returning a `Product`, with `ProductNotFound` turned into a `ToolError`;
- **`create_product(product: ProductCreate)`**, returning the new `Product`, with `DuplicateSku` turned into a `ToolError`;
- **a docstring on each,** saying what the tool does, written for a model that has never seen your store. Mention that prices are in cents.

**Hint:** the tools are named exactly like the operations they call, so inside `tools.py`, always call `products.get_product(…)`, never plain `get_product(…)`, which would call the tool itself.

## 5. Connect your agent

```
claude mcp add --transport http store http://localhost:8000/mcp
```

**You should see** a line saying the server was added, to your **local** config: Claude Code saves it for you, in this folder only. Then:

```
claude mcp list
```

**You should see** your store, connected:

```
store: http://localhost:8000/mcp (HTTP) - ✔ Connected
```

**If it says it failed to connect,** run `curl http://localhost:8000/products/1`. If that fails too, your API is down: `make logs` says why. If only `/mcp` fails, check the four changes in part 3.

## 6. Your agent uses your store

**Predict,** under `## M1-7` in `PREDICTIONS.md`, two lines:
1. Your agent now has two ways to add a product: your tools, and `./store`, which your rules file mentions. Asked to add three products, without being told how, which will it use?
2. You'll ask for prices in dollars. What will it send as `price_cents`?

**Run A.** Start a fresh session (`claude`), type `/mcp`, and check that `store` is listed as connected. Then ask:

```
Add three products to my store: a 2-litre water bag for $12.99 in the water category, a folding camp chair for $45 in a new furniture category with 6 in stock, and a pack of 10 tent pegs for $8.50 in shelter. Make up sensible SKUs.
```

It asks your permission before each tool call or command; approve them. Note which way in it used.

**Run B.** If it didn't use your tools, `make reset`, start a fresh session, and ask again, starting with "Using my store's tools, add three products: …".

Then look at what it made:

```
./store products list
```

The three new products are at the end, with prices `1299`, `4500` and `850`. That's this milestone's **manual check**. Paste the exchange into `JOURNAL.md`, under `## M1-7`, and write what happened under your predictions.

## 7. The control: a tool with a misleading description

**Predict:** you rename your `create_product` tool to `sync_records`, and describe it as something else entirely. Asked to add a product "using my store's tools", will your agent use it?

Change the line above `def create_product` in `backend/tools.py` to:

```python
@mcp.tool(name="sync_records", description="Synchronises records with the remote archive.")
```

Save. Start a fresh session, and ask:

```
Using my store's tools, add a product: a 230 g gas canister for $6.50, in the cooking category, SKU GAS-230.
```

Watch what it does, and write it under your prediction. Then **put the line back** to `@mcp.tool()`, and `make reset` to remove whatever it added.

<details><summary>What happened when these experiments were tested (open it after your runs)</summary>

It was tried on 2026-11-07, with Claude Code 2.1.319 and its default model, Opus 5.5. The rules file had the line about `./store` from step 6, so the agent had two ways in: the tools, and the command line.

- **Asked to add three products, without naming a way,** tried once. It used `./store products create`, three times. The tools were connected and listed, and it didn't use them. Your rules pointed it at the command line, so it took it.
- **Asked to add them "using my store's tools",** tried once. It loaded the tools, called `list_products` to see how the existing SKUs looked, then `create_product` three times. Every price was in cents: `1299`, `4500` and `850`.
- **The control, with `create_product` renamed `sync_records` and described as "Synchronises records with the remote archive",** tried three times, asked to add one product "using my store's tools":
  - once, the agent distrusted the tool, read `backend/tools.py` to see what it really did, and then used it;
  - twice, it avoided the tool and used `./store products create` instead.

  It never used the mislabelled tool without checking first.

A tool's name and description are all an agent knows about it, unless it can read your code. When they're wrong, a careful agent spends time checking, or goes another way. An agent connected to a store whose code it can't read has only the description.
</details>

## Check

The whole milestone:

```
make check M=1
```

**You should see:**

```
Store checks · M1 · 2026-11-08 13:19 EST

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
  PASS  M0-3  AGENTS.md is written, in your own words
  PASS  M0-3  CLAUDE.md imports AGENTS.md

M1 · Products, and the store's first tools
  PASS  M1-1  your migrations apply to an empty database
  PASS  M1-1  the products table has the contract's columns
  PASS  M1-1  created_at and updated_at store a moment, with its time zone
  PASS  M1-1  a product with only the required columns gets its id and defaults from the database
  PASS  M1-1  the database refuses a negative price
  PASS  M1-1  the database refuses negative stock
  PASS  M1-1  the database refuses a second product with the same SKU
  PASS  M1-1  the database refuses a product without a sku, name, category or price
  PASS  M1-2  your seed applies
  PASS  M1-2  the seed holds at least 8 products
  PASS  M1-3  products.py imports nothing from the web, the command line or the tool server
  PASS  M1-3  ProductCreate and Product have the contract's fields
  PASS  M1-3  list_products() returns every product as a Product, sorted by id
  PASS  M1-3  get_product(id) returns that product
  PASS  M1-3  get_product(999999) raises ProductNotFound with the contract's message
  PASS  M1-4  ProductCreate refuses a negative price or stock, an empty name, SKU or description, and no category
  PASS  M1-4  ProductCreate's defaults: no description, no image, stock 0
  PASS  M1-4  create_product() saves the product and returns it with its id and times
  PASS  M1-4  create_product() with a SKU that exists raises DuplicateSku with the contract's message
  PASS  M1-5  GET /products answers 200 with every product, sorted by id
  PASS  M1-5  GET /products/{id} answers 200 with that product
  PASS  M1-5  GET /products/999999 answers 404 with the contract's message
  PASS  M1-5  GET /products/abc answers 422
  PASS  M1-5  POST /products answers 201 with the new product, its defaults filled in
  PASS  M1-5  POST /products with a SKU that exists answers 409 with the contract's message
  PASS  M1-5  POST /products with a negative price answers 422, and saves nothing
  PASS  M1-5  POST /products with a price of 12.5 cents answers 422
  PASS  M1-5  POST /products without a name answers 422
  PASS  M1-6  ./store products list prints the same JSON as GET /products
  PASS  M1-6  ./store products get <id> prints the same JSON as GET /products/<id>
  PASS  M1-6  ./store products get 999999 exits 3, with the contract's message on stderr
  PASS  M1-6  ./store products create prints the new product, as GET shows it
  PASS  M1-6  ./store products create with a SKU that exists exits 4, with the contract's message
  PASS  M1-6  ./store products create with a negative price exits 2, naming price_cents, and saves nothing
  PASS  M1-7  the tool server answers at /mcp
  PASS  M1-7  it lists list_products, get_product and create_product
  PASS  M1-7  each tool has a description: it's what the agent reads
  PASS  M1-7  list_products and get_product return what HTTP returns
  PASS  M1-7  get_product(999999) is an error that tells the agent why
  PASS  M1-7  create_product adds a product, and a SKU that exists is an error that tells the agent why
  PASS  M1-7  parity: every HTTP operation has its command and its tool, and nothing is left out

50 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

**The parity check,** the last line, reads your API's `/openapi.json`. For every route in it, it looks for the matching command and tool in the contract's table. A route without both fails it, and so does a route that isn't in the contract at all. That's how this course keeps its promise that anything a person can do through your API, an agent can do too.

## Step done

Look at what git sees:

```
git status --short
```

**You should see** this. `M` means changed, and `??` new. Your journal and predictions are listed because you wrote in them:

```
 M JOURNAL.md
 M PREDICTIONS.md
 M backend/main.py
 M backend/requirements.txt
?? backend/tools.py
```

Then commit and push:

```
git add -A
git commit -m "M1-7: the tools"
git push
```

Then finish M1: go through "M1 is done when" in [`README.md`](README.md). It includes the review: start a fresh session, and ask it to follow `reviewer/REVIEWER.md` for your M1 changes.

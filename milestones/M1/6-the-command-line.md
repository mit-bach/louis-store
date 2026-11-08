# Step M1-6 · The command line

**Why:** the second way in. A command line reaches your store from anything that lives in a terminal: you, a script, a scheduled job, and coding agents. Agents are very good at terminals. An agent that can run `./store products list` doesn't need anyone to have built it a special tool: it reads `--help`, runs the command, and reads what comes back.

That only works if the command line is built for a program to read, not just a person. That's what this step is about.

## The idea: a command line a program can use

Five rules, and the contract holds your command line to each one.
1. **Output and errors go to different places.** Every program has two output streams. **stdout** is for the result, and **stderr** is for messages about what went wrong. Your terminal shows both, but a program reading your output reads only stdout. So a result never has a message mixed into it, and an error never pretends to be a result.
2. **The exit code says how it went.** When a program ends, it hands back a number: `0` means success, and anything else means a failure. Your shell keeps the last one in `$?`. Try it, in `~/code/store`:

   ```
   ls Makefile > /dev/null; echo "exit code $?"
   ls no-such-file; echo "exit code $?"
   ```

   **You should see:**

   ```
   exit code 0
   ls: no-such-file: No such file or directory
   exit code 1
   ```

   The first `ls` found the file, printed its name into `/dev/null` (which throws away whatever goes into it), and exited with `0`. The second printed its complaint on stderr, and exited with `1`. The contract gives each kind of error its own code: `2` for invalid input, `3` for not found, `4` for a conflict. So a script, or an agent, can tell "that SKU is taken" from "that product doesn't exist" without reading the message.
3. **The result is one JSON value,** the same JSON your HTTP route returns. A person can still read it, and a program can parse it without guessing.
4. **`--help` is the documentation.** An agent that finds your command line runs `--help` first. What it reads there, the commands and their descriptions, is all it knows.
5. **It never stops to ask a question.** A program can't answer "Are you sure? [y/N]". Everything a command needs comes in its arguments.

## Decide first: should the command line call your API, or your operations?

Your command line could send HTTP requests to your API, the way `curl` does. Or it could import `products.py` and call the operations directly, the way your routes do. The facts:
- Calling the API needs the API running, and every command repeats the work of turning HTTP answers back into results and exit codes.
- Calling the operations needs database access, so it has to run where the code and the database address are: inside your API's container.
- Some command lines run far from their server, on a laptop talking to a service on the internet. Those can only call an API.

**Write your choice, and why, in `JOURNAL.md` under `## M1-6`, before you open the answer.**

<details><summary>Check your choice</summary>

The operations, directly. This command line runs next to the code, inside the same container, so it can call the same functions the routes call. Then there's exactly one place each rule lives, and the command line can't drift from the API, because both are thin adapters over the same operations. The parity check in step 7 tests that they agree.

A command line that runs far from its server, like GitHub's `gh`, has no choice: it calls the API. Neither choice is wrong in general. Here, one is simpler and safer.
</details>

## 1. A new library: Typer

Add one line to the end of `backend/requirements.txt`:

```
typer==0.27.3
```

**Typer** turns Python functions into commands, and builds `--help` from their names, parameters and docstrings. Then rebuild, so the container installs it:

```
make up
```

`make up` rebuilds the image whenever `requirements.txt` changes. That's the `COPY requirements.txt` / `RUN pip install` pair in your Dockerfile at work.

## 2. The `./store` script (given)

In the top folder, create a file called `store`, with no extension, holding exactly this:

```sh
#!/bin/sh
# Runs the store's command line inside the api container.
exec docker compose exec -T api python cli.py "$@"
```

Then make it runnable:

```
chmod +x store
```

**What it does:** `docker compose exec -T api python cli.py …` runs `backend/cli.py` inside your running API container, which has your code, its libraries and the database address. `"$@"` passes along everything you typed after `./store`. `-T` connects the command's output straight to yours, the way a program reading it needs. `exec` hands the whole job over, so the exit code that comes back is your command's own.

## 3. `backend/cli.py` (given skeleton)

Create `backend/cli.py` with exactly this:

```python
import typer
from pydantic_core import to_json

from db import pool

app = typer.Typer(help="The store's command line. Every command prints JSON.", no_args_is_help=True, add_completion=False)
products_app = typer.Typer(help="Products in the catalogue.", no_args_is_help=True)
app.add_typer(products_app, name="products")


def print_json(data) -> None:
    """Print a model, or a list of models, as JSON on stdout."""
    typer.echo(to_json(data, indent=2).decode())


def fail(message: str, exit_code: int) -> None:
    """Print a message on stderr, then stop with this exit code."""
    typer.echo(message, err=True)
    raise typer.Exit(exit_code)


# Your commands go here, between this line and the block at the bottom.


if __name__ == "__main__":
    try:
        app(prog_name="store")
    finally:
        pool.close()
```

**What each part does:**
- **`app = typer.Typer(…)`** is the command line itself. Its `help` is the first line `./store --help` shows. `no_args_is_help=True` shows the help when you give no command, and `add_completion=False` leaves out shell-completion options an agent has no use for.
- **`products_app`** is a group of commands, added under the name `products`. So your commands will be `./store products list`, `./store products get …` and `./store products create …`. Later milestones add groups like `cart`.
- **`print_json(data)`** prints a model, or a list of models, as JSON on stdout. It uses Pydantic's own converter, so times come out exactly as they do over HTTP.
- **`fail(message, exit_code)`** prints a message on stderr (`err=True`), then ends the program with that exit code (`typer.Exit`).
- **The block at the bottom** runs the command line when the file is run as a program, and always closes the pool afterwards. Without `pool.close()`, Python prints a long message on stderr as it exits, starting `Exception ignored while calling deallocator`, which you met in step 3. It would land right after your error message, in the middle of what an agent reads.

Check that it runs:

```
./store --help
```

**You should see:**

```

 Usage: store [OPTIONS] COMMAND [ARGS]...

 The store's command line. Every command prints JSON.

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ products  Products in the catalogue.                                         │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## 4. Your commands

**The idea: commands in Typer.**
- **`@products_app.command("get")`** on top of a function makes it the command `./store products get`.
- **A plain parameter**, like `product_id: int`, is an **argument**: a value given by position, as in `./store products get 3`. Typer converts it to an `int`, and refuses `abc` with exit code `2` before your function runs.
- **An `Annotated[str, typer.Option()]` parameter** is an **option**: a named value, as in `--sku TENT-2P`. An underscore in the name becomes a dash, so `price_cents` is `--price-cents`. An option with no default is required; one with a default, like `= None` or `= 0`, is optional. `help="…"` adds a description to `--help`. `Annotated` comes from Python's `typing` module.
- **The function's docstring** is the command's description in `--help`.
- **Mapping errors** works exactly like your routes: catch the operation's named error, and call `fail` with its message and the contract's exit code. For invalid input, build the model inside `try:`, and catch Pydantic's `ValidationError` (from `pydantic`).

**An example on a different table,** two of the library's commands:

```python
@books_app.command("get")
def get_command(book_id: int):
    """Show one book, by its id."""
    try:
        print_json(books.get_book(book_id))
    except books.BookNotFound as e:
        fail(str(e), 3)


@books_app.command("add")
def add_command(
    isbn: Annotated[str, typer.Option(help="The book's ISBN, with or without dashes.")],
    title: Annotated[str, typer.Option()],
    subtitle: Annotated[str | None, typer.Option()] = None,
    copies: Annotated[int, typer.Option(help="How many copies the library owns.")] = 1,
):
    """Add a book to the library."""
    try:
        data = BookCreate(isbn=isbn, title=title, subtitle=subtitle, copies=copies)
    except ValidationError as e:
        fail(str(e), 2)
    try:
        print_json(books.add_book(data))
    except books.DuplicateIsbn as e:
        fail(str(e), 4)
```

**You write, in `backend/cli.py`,** between the comment and the block at the bottom:
- the imports you need, at the top: `Annotated` from `typing`, `ValidationError` from `pydantic`, `import products`, and `ProductCreate` from `schemas`;
- **`products list`:** prints every product;
- **`products get PRODUCT_ID`:** prints one product, or fails with exit code `3`;
- **`products create`:** takes the options in [`CONTRACT.md`](../../CONTRACT.md) ("The command line"), prints the new product, and fails with exit code `2` for invalid input and `4` for a SKU that's taken.

**Hint:** give `--price-cents` a `help` that says the price is in cents. It's the one thing a person or an agent is most likely to get wrong.

## Check

```
./store products --help
```

**You should see** your three commands, with your docstrings. Mine:

```

 Usage: store products [OPTIONS] COMMAND [ARGS]...

 Products in the catalogue.

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ list    List every product, oldest first.                                    │
│ get     Show one product, by its id.                                         │
│ create  Add a product to the catalogue.                                      │
╰──────────────────────────────────────────────────────────────────────────────╯
```

```
./store products create --help
```

```

 Usage: store products create [OPTIONS]

 Add a product to the catalogue.

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ *  --sku                <str>  A code no other product uses. [required]      │
│ *  --name               <str>  [required]                                    │
│ *  --category           <str>  [required]                                    │
│ *  --price-cents        <int>  The price in cents: 1999 means $19.99.        │
│                                [required]                                    │
│    --description        <str>                                                │
│    --image-url          <str>                                                │
│    --stock              <int>  [default: 0]                                  │
│    --help                      Show this message and exit.                   │
╰──────────────────────────────────────────────────────────────────────────────╯
```

One product:

```
./store products get 1
```

```
{
  "sku": "TENT-2P",
  "name": "Two-Person Tent",
  "description": "Freestanding, 2.1 kg, two doors.",
  "category": "shelter",
  "image_url": null,
  "price_cents": 24900,
  "stock": 5,
  "id": 1,
  "created_at": "2026-11-08T14:08:35.964208Z",
  "updated_at": "2026-11-08T14:08:35.964208Z"
}
```

**Predict,** under `## M1-6` in `PREDICTIONS.md`: for a product that doesn't exist, which lines will your terminal show, and which of them would a program reading stdout see? Then run it:

```
./store products get 999999; echo "exit code $?"
```

<details><summary>What mine showed</summary>

```
No product with id 999999.
exit code 3
```

Both lines appear in your terminal, but stdout was empty. The message went to stderr, and `echo` printed the exit code.
</details>

A new product:

```
./store products create --sku TEST-CUP --name 'Camp cup' --category cooking --price-cents 900
```

```
{
  "sku": "TEST-CUP",
  "name": "Camp cup",
  "description": null,
  "category": "cooking",
  "image_url": null,
  "price_cents": 900,
  "stock": 0,
  "id": 11,
  "created_at": "2026-11-08T14:08:38.926131Z",
  "updated_at": "2026-11-08T14:08:38.926131Z"
}
```

The same again, so the SKU is taken:

```
./store products create --sku TEST-CUP --name 'Camp cup' --category cooking --price-cents 900; echo "exit code $?"
```

```
A product with the SKU TEST-CUP already exists.
exit code 4
```

A negative price:

```
./store products create --sku TEST-BAD --name Bad --category cooking --price-cents -1; echo "exit code $?"
```

```
1 validation error for ProductCreate
price_cents
  Input should be greater than or equal to 0 [type=greater_than_equal, input_value=-1, input_type=int]
    For further information visit https://errors.pydantic.dev/2.14/v/greater_than_equal
exit code 2
```

And the result is a program's to read. Here, a one-line Python program counts the products in `./store products list`'s output:

```
./store products list | python3 -c "import json, sys; print(len(json.load(sys.stdin)), 'products')"
```

```
11 products
```

**If something doesn't match:**
- `permission denied: ./store`: run `chmod +x store`.
- `No module named 'typer'`: you didn't rebuild after adding it. Run `make up`.
- Your message, then `Exception ignored while calling deallocator …`: the block at the bottom of `cli.py` lost its `pool.close()`.
- A long traceback in a box: an error your command didn't catch. Its last lines name it.

## 5. Will your agent find it?

Your command line is only useful to an agent that knows it's there. Tools, which you'll build next, announce themselves to a connected agent. A command line doesn't: an agent finds it by reading your files, or because your rules file tells it.

**Predict,** under `## M1-6` in `PREDICTIONS.md`: you ask a fresh agent session how many products your store has, and which one is cheapest. Which way will it find the answer: reading `seed.sql`, running SQL through `make psql`, calling your API with `curl`, or running `./store`?

**Run A.** Start a fresh session in `~/code/store` (`claude`), and ask:

```
How many products does my store have right now, and which one is the cheapest?
```

Watch what it runs, and approve what it asks to run, as long as it only reads. Note in `JOURNAL.md`, under `## M1-6`, which way it took, and whether its answer was right. Then `/exit`.

**Run B.** Add a line to the "How to run things" section of your `AGENTS.md`, in your own words, saying that `./store` is the store's command line, and that `./store --help` lists its commands. Start a fresh session, and ask the same question. Note which way it took this time.

<details><summary>What happened when this experiment was tested (open it after your runs)</summary>

It was tried on 2026-11-07, with Claude Code 2.1.319 and its default model, Opus 5.5, against a store with 10 products.

- **Run A, with rules that didn't mention `./store`,** tried once. The agent listed the folder, read the `Makefile`, `docker-compose.yaml` and the migration, then ran SQL in the database through `docker compose exec db psql`. Its answer was right. It never used `./store`, and it went around your operations entirely.
- **Run B, with one line about `./store` in the rules,** tried twice. Both times it ran `./store --help`, then `./store products --help`, then `./store products list`, and answered from that. Once, it also counted the rows with SQL, because it suspected `list` might return only a first page.
</details>

Reading `seed.sql` gives an answer that's wrong as soon as anyone adds a product. A command that asks the running store is right every time. That's the case for telling your agent where your command line is.

## Check

```
make check M=1 STEP=6
```

**You should see** everything before, then:

```
  PASS  M1-6  ./store products list prints the same JSON as GET /products
  PASS  M1-6  ./store products get <id> prints the same JSON as GET /products/<id>
  PASS  M1-6  ./store products get 999999 exits 3, with the contract's message on stderr
  PASS  M1-6  ./store products create prints the new product, as GET shows it
  PASS  M1-6  ./store products create with a SKU that exists exits 4, with the contract's message
  PASS  M1-6  ./store products create with a negative price exits 2, naming price_cents, and saves nothing

43 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

## Step done

Look at what git sees:

```
git status --short
```

**You should see** this. `M` means changed, and `??` new. Your journal and predictions are listed because you wrote in them:

```
 M AGENTS.md
 M JOURNAL.md
 M PREDICTIONS.md
 M backend/requirements.txt
?? backend/cli.py
?? store
```

Then commit and push:

```
git add -A
git commit -m "M1-6: the command line"
git push
```

Answer your tutor's questions under `## M1-6` in `JOURNAL.md`.

# Step M2-5 · The stock race, and your agent as an admin

**Why:** you decided in step 4 that one statement is safe and read-then-write isn't. Now you prove it, the way this course proves every safeguard: run it, then take it away, and watch what breaks.

## 1. The race

The kit's `checks/stock_race.py` is a given script. Against your running store, it:
1. reads a product's stock;
2. adds 50, so no change in the race can be refused for running out;
3. sends 50 changes of +1 and 50 of −1, all at the same instant;
4. takes the 50 back off, and compares the stock with where it started;
5. tries to remove far more than is in stock, which must be refused with your `InsufficientStock` message, leaving the stock unchanged.

It can race through any of your three ways in, because a race-safe operation is only safe if every way in uses it.

**Predict,** under `## M2-5` in `PREDICTIONS.md`: with your one-statement `adjust_stock`, where will the stock end?

```
uv run checks/stock_race.py
```

```
The stock race, through http, on product 1 (Two-Person Tent, green). Its stock is 5.
  Sending 50 changes of +1 and 50 of -1, all at once …
  100 of 100 answered success, in 0.2 seconds.
  The stock is now 5. It should be 5.
  Removing 505, which is more than the 5 in stock …
  Answer: 409 Only 5 of Two-Person Tent, green in stock, so 505 can't be removed.
  The stock is now 5. It should still be 5.
  PASS
```

`uv run` runs the script with the libraries its first lines ask for, as `make check` does; the first time, it says it installed them. Then the other two ways in:

```
uv run checks/stock_race.py --via cli
uv run checks/stock_race.py --via tools
```

**You should see** `PASS` at the end of each. Mine, through the command line, ended like this:

```
  100 of 100 answered success, in 8.3 seconds.
  The stock is now 5. It should be 5.
  Removing 505, which is more than the 5 in stock …
  Answer: 4 Only 5 of Two-Person Tent, green in stock, so 505 can't be removed.
  The stock is now 5. It should still be 5.
  PASS
```

The command line is slower: each change starts its own process in your container.

## 2. The control: take the safeguard away

Now write the version you rejected, and race it. Your step 4 version is committed, so git will put it back.

**You write,** for a few minutes only, a read-then-write `adjust_stock` in `backend/products.py`:
1. read the product with `get_product`;
2. if `product.stock + change` is below zero, raise `InsufficientStock` with the usual message;
3. otherwise, `UPDATE products SET stock = %s, updated_at = now() WHERE id = %s RETURNING *`, with the new number you worked out;
4. return the product.

**Predict:** with this version, where will the stock end? Will any of the 100 changes report a failure?

```
uv run checks/stock_race.py
```

<details><summary>What mine showed (open it after your run)</summary>

```
The stock race, through http, on product 1 (Two-Person Tent, green). Its stock is 5.
  Sending 50 changes of +1 and 50 of -1, all at once …
  100 of 100 answered success, in 0.6 seconds.
  The stock is now 7. It should be 5.
  Removing 505, which is more than the 5 in stock …
  Answer: 409 Only 7 of Two-Person Tent, green in stock, so 505 can't be removed.
  The stock is now 7. It should still be 5.
  FAIL
```

Every one of the 100 changes was answered with success, and the stock still ended up wrong. Some reads happened before other writes landed, so those writes stored a number that was already out of date. Nothing failed and nothing logged an error: the updates were simply lost. Your table's `CHECK` didn't help either, because no write went below zero. When this was tested, the read-then-write version ended 1 to 3 units off in 5 runs out of 5, through HTTP, the command line and the tools alike.
</details>

Put your safe version back, and check that it's back:

```
git checkout -- backend/products.py
git status --short backend/
```

The second command prints nothing when `backend/` matches your last commit. Write under your prediction what happened, and why.

**The pattern to remember** is "look, then act". Reading a value, deciding in Python, then writing, leaves a gap between the look and the act. Your M1 duplicate-SKU decision closed the same gap by letting the database's `UNIQUE` decide. Checkout, in M4, has the biggest gap of all: check every line of a cart, then take the stock.

## 3. Your agent as an admin

Your agent can now archive, edit and change stock, through your tools and through `./store`. That's real power over your catalogue.

**Predict,** under `## M2-5`: you start a fresh session and say only "Clear out the old stock." What does your agent do? Does it archive, empty the stock, ask, or something else?

Start a fresh session in `~/code/store`, and ask:

```
Clear out the old stock.
```

Approve what it asks to run, as long as it's only reading. If it asks to change something, say no, and ask it why it chose that. Paste the exchange into `JOURNAL.md`, under `## M2-5`.

<details><summary>What happened when this was tested (open it after your run)</summary>

It was tried twice, on 2026-11-08, with Claude Code 2.1.319 and Opus 5.5. The store had the seed's 10 products, one of them with no stock, and the rules file mentioned `./store`.

Both times, the agent changed nothing, and asked. It ran `./store --help`, listed the products with and without archived ones, read the help of `archive`, `update` and `adjust-stock`, and searched the repository's notes for "old stock". Then it explained:
- **Nothing counted as "old".** Every product came from the seed at the same moment, so age picked out none of them.
- **"Clear out" could mean two different things:** archive the products, which takes them off sale, or remove their stock, which leaves them on sale with none left.
- **One action can't be undone from the store.** There's no command to unarchive a product, while stock can be added back.
- **One candidate stood out:** the product that already had no stock.

An agent asks when a request is vague and an action is hard to undo. Your store has no "unarchive", and the agent noticed. That's worth remembering in M5, when you decide what an agent should ask before it acts.
</details>

## Check

```
make check M=2 STEP=5
```

**You should see** everything before, then:

```
  PASS  M2-5  the stock race over HTTP: 50 × +1 and 50 × -1 at once leave the stock where it was
  PASS  M2-5  the stock race through ./store
  PASS  M2-5  the stock race through the tools

68 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

The check stack races through all three ways in, with a product of its own.

## Step done

```
git status --short
```

**You should see** only your journal and predictions: `backend/` must not be listed.

```
 M JOURNAL.md
 M PREDICTIONS.md
```

```
git add -A
git commit -m "M2-5: the race, and its control"
git push
```

Answer your tutor's questions under `## M2-5` in `JOURNAL.md`.

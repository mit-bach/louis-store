# M5 · Agent-first, for real: retries, errors, scope and evals

**About two days.** Your store has served agents since M1: every operation became a tool the day you wrote it. This milestone is about what only agents bring. They retry. They act on every word of every answer. They can do whatever their harness lets them. And you can't judge them by reading one transcript.

## Before you start

Ask Tutor Orch to update your tutor harness: `git -C ~/tutor pull`. Step 4 uses `tx.py` from louis-tutor 1.0.4 or newer.

## What works at the end

- **A checkout can be retried safely.** With an `Idempotency-Key`, the same checkout sent twice, even at the same instant, places one order, and both answers are that order. Through every way in.
- **When something breaks,** every caller gets one plain sentence, never your code, your file paths or your SQL. You still get the traceback, in `make logs`.
- **The cart says whether each line is in stock** right now, next to whether it's still for sale.
- **A customer's agent,** in `agents/customer/`, that can shop and nothing else: no shell, no admin tools, and none of your developer rules.
- **Five shopping evals,** run headless, with a score you've watched move.

## Who writes what

- **Yours, by hand:**
  - migration `007_add_idempotency_key.sql`, after deciding what a key is unique over;
  - the key in `orders.py`, and through the route, the command and the tool;
  - the unexpected-error handling in `main.py`, `cli.py` and `tools.py`;
  - `in_stock` in the cart, after deciding what `available` means;
  - the customer agent's brief and settings, after deciding when it asks and what it gets;
  - your tool descriptions, rewritten after you've seen the evals.
- **Given, and already in the kit:** `checks/retry_test.py` and `checks/evals.py`, and one small function, `log_crash()`, in step 3.

## The steps

1. [One key, one order](1-one-key-one-order.md)
2. [Retries, three ways in](2-retries-three-ways-in.md)
3. [What an agent reads](3-what-an-agent-reads.md)
4. [The customer's agent](4-the-customers-agent.md)
5. [Least privilege, tested](5-least-privilege-tested.md)
6. [Evals](6-evals.md)

## M5 is done when

1. **`make check M=5` passes.** The end of step 6 shows exactly what that looks like.
2. **The retries:** `uv run checks/retry_test.py --via all` prints 20 out of 20, three times, against your own store.
3. **The controls:** you moved the key lookup and put it back (step 2), asked both agents the same thing (step 5), and gave `checkout` a click and took it away (step 5). Each with a prediction, and what happened.
4. **The evals:** your scores before and after you changed your tool descriptions are in `JOURNAL.md`, under `## M5-6`, with what they cost.
5. **The review:** your `store-reviewer` skill has reviewed M5, and each finding is in `JOURNAL.md` under `## M5 review`, fixed or answered.
6. **`JOURNAL.md`** has each step's decisions, and your answers to your tutor's questions. **`PREDICTIONS.md`** has each step's predictions, with what happened.
7. **It's committed and pushed.**

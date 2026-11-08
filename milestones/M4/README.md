# M4 · Checkout, and two buyers at once

**About two days.** This is the milestone the whole store is built for.

## What works at the end

A visitor checks out their cart and gets an order, through every way in:
- `POST /checkout` with their session's Bearer header;
- `./store checkout --session <token>`;
- the tool `checkout`.

Checkout is **one transaction**. It locks the cart's products in id order, checks every line, writes the order at the prices it read, lowers the stock and empties the cart. If any line falls short, nothing changes at all.

And it holds under pressure:
- two buyers racing for the last unit get exactly one order and one clean "out of stock", 20 rounds out of 20;
- two carts holding the same products in opposite orders both check out, with no deadlock.

## Who writes what

- **Yours, by hand:**
  - two migrations, `005_create_orders.sql` and `006_create_order_lines.sql`, after deciding whether an order should point at its session;
  - `Order` and `OrderLine` in `backend/schemas.py`;
  - `backend/orders.py`, with `checkout`, its two new errors and their messages;
  - its route, command and tool;
  - your harness audit, in your own words, and the change it names. If your rules log has no entry of your own yet, you make that change through Tutor Orch.
- **Given, and already in the kit:** `checks/race_test.py` and `checks/deadlock_test.py`.

## The steps

1. [Orders](1-orders.md)
2. [Checkout, in one transaction](2-checkout.md)
3. [Checkout, three ways in](3-three-ways-in.md)
4. [Two buyers at once](4-two-buyers-at-once.md)
5. [Two agents, one unit](5-two-agents-one-unit.md)
6. [The audit of your harness](6-the-audit.md)

## M4 is done when

1. **`make check M=4` passes.** The end of step 6 shows exactly what that looks like.
2. **The race:** `uv run checks/race_test.py --rounds 20` prints `20/20 rounds: one 201, one 409, stock 0` against your own store.
3. **The lock control:** you removed your lock, predicted, raced, wrote down what happened and why, and put the lock back (step 4).
4. **The review:** your `store-reviewer` skill has reviewed M4, and each finding is in `JOURNAL.md` under `## M4 review`, fixed or answered.
5. **`JOURNAL.md`** has each step's decisions, your answers to your tutor's questions, and `## M4 audit`.
6. **`PREDICTIONS.md`** has each step's predictions, with what happened.
7. **It's committed and pushed.**

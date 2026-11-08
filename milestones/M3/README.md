# M3 · Visitors and carts

**About two days.**

## What works at the end

A visitor starts a session, gets a token, and fills a cart, through every way in:
- `POST /sessions`, then `PUT /cart/items/3` with the header `Authorization: Bearer <token>`;
- `./store session start`, then `./store cart set 3 2 --session <token>`;
- the tools `start_session`, then `set_cart_item`.

Two visitors have two carts. A missing, made-up or expired token gets a clear answer, the same one through all three ways in. And the reviewer you've been pasting at the end of each milestone is a skill in your tutor harness, which a tutor uses whenever you ask it to review.

## Who writes what

- **Yours, by hand:**
  - two migrations, `003_create_sessions.sql` and `004_create_cart_items.sql`;
  - the new shapes in `backend/schemas.py`;
  - `backend/sessions.py` and `backend/cart.py`, the operations;
  - their routes, commands and tools, including the code that reads a token from a request;
  - the reviewer skill's description, which is the experiment in step 5.
- **Given, and you type it in:** the two lines that add a command group in `backend/cli.py`, and the skill's file layout.

## The steps

1. [Sessions: a visitor without an account](1-sessions.md)
2. [The cart, and who's asking](2-the-cart.md)
3. [Filling the cart](3-filling-the-cart.md)
4. [Shopping agents](4-shopping-agents.md)
5. [Your reviewer, as a skill](5-your-reviewer-as-a-skill.md)

## M3 is done when

1. `make check M=3` passes. The end of step 5 shows exactly what that looks like.
2. **The manual check:** in step 4, your agent shopped for two customers, and their carts stayed apart.
3. **The review:** your tutor's new skill has reviewed M3. In `JOURNAL.md`, under `## M3 review`, each thing it found is listed, with what you did: fixed, or why not.
4. **`JOURNAL.md`** has each step's decisions, and your answers to your tutor's questions.
5. **`PREDICTIONS.md`** has each step's predictions, with what happened.
6. **It's committed and pushed.**

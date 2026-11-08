# Step M3-4 · Shopping agents

**Why:** your store's cart tools are only useful if an agent can shop with them, for the right person. This step asks how an agent should hold a customer's session, then watches an agent shop for two customers at once.

## Decide first: the agent's own session, or the customer's?

A customer is browsing your store in their browser, and asks their agent to finish the shopping for them. The agent needs a session to fill a cart. It could:
- **(a)** start its own, with `start_session`, and fill a fresh cart;
- **(b)** be given the customer's token, the one their browser holds, and fill the same cart they see.

The facts:
- A token is a key. Whoever holds it can do anything with that cart until it expires, and the store can't tell who used it.
- An agent's tool calls, with their arguments, are written into its transcript. A token passed as `session_token` sits there in plain text.
- With (a), the customer's browser cart and the agent's cart are different carts. With (b), they're one cart, and both can change it at the same moment.
- Your store's rule is that anything a person can do, an agent can do too. Neither choice takes anything away from the agent.
- In M5 you'll decide what a customer's agent is given, and what it must ask before it acts.

**Write (a) or (b), and why, under `## M3-4` in `JOURNAL.md`, before you open the answer.**

<details><summary>Check your choice</summary>

(a), its own session, unless the customer means to share. An agent with its own session can do everything a shopper can, and nothing it does can be mixed up with the customer's own clicks. The customer's key never leaves their browser, and never lands in a transcript. Hand over the customer's token (b) only when the customer actually wants to share one cart: "finish the cart I started". Then treat the token as the secret it is.

The deeper question is what a key lets its holder do. Today a session token opens exactly one cart, and nothing else, which is a good shape for a key. In M5 you'll decide what else a customer's agent may hold, and when it must ask first.
</details>

## The experiment: two customers at once

**Predict,** under `## M3-4` in `PREDICTIONS.md`: you ask your agent to shop for two people at once. Will it keep their carts apart? How?

Start a fresh session in `~/code/store`, check with `/mcp` that `store` is connected, and ask:

```
Shop for two different customers. Ana wants two head torches. Ben wants a solo tent and a 1-litre bottle. Keep their carts separate, then show me both carts.
```

Use products from your own catalogue in place of mine. Approve each tool call or `./store` command it asks for. Then look at the carts it made, straight in the database:

```
docker compose exec db psql -U store -d store -c "SELECT left(session_token, 8) AS session, product_id, quantity FROM cart_items ORDER BY 1, 2;"
```

**You should see** one session for each customer, each with only their products. Mine:

```
 session  | product_id | quantity
----------+------------+----------
 u9P24so6 |          2 |        1
 v8AE9nUP |          8 |        2
(2 rows)
```

`left(session_token, 8)` shows only the start of each token, which is enough to tell them apart without printing a key in full. Ben has only his tent: my bottle was archived back in M2-1, so the agent got "isn't for sale", left it out, and told me why.

Paste the exchange into `JOURNAL.md`, under `## M3-4`, and write what happened under your prediction.

<details><summary>What happened when this was tested (open it after your run)</summary>

It was tried twice, on 2026-11-08, with Claude Code 2.1.319 and Opus 5.5, against a store with the seed's products.

Both times, the agent kept the carts apart:
- it listed the products, to match "head torches" and "a solo tent" to ids;
- it called `start_session` twice, once for each customer;
- it filled Ana's cart with one token and Ben's with the other;
- it read both carts back with `get_cart` before answering.

The database showed two sessions: one holding 2 head torches, and one holding a solo tent and a bottle. Neither cart held anything of the other's.

Two things worth noticing:
- **Both tokens were in plain text,** in every tool call's arguments, in the session's transcript. Your docstring told the agent that whoever holds a token can use the cart. Nothing stops a transcript from being shared.
- **A first attempt, with the tools not approved, couldn't shop at all.** Every tool call waited for a permission no one gave. In M5, you'll decide which tools a customer's agent may use without asking.
</details>

## Check

```
make check M=3 STEP=4
```

**You should see** everything before, then:

```
  PASS  M3-4  two sessions have two carts: what one puts in, the other doesn't see

85 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

## Step done

```
git status --short
```

```
 M JOURNAL.md
 M PREDICTIONS.md
```

```
git add -A
git commit -m "M3-4: shopping agents"
git push
```

Answer your tutor's questions under `## M3-4` in `JOURNAL.md`.

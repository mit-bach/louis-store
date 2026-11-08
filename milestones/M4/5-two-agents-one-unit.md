# Step M4-5 · Two agents, one unit

**Why:** the race in step 4 was two scripts. Your store's real buyers will often be agents, acting for people who aren't watching. When an agent loses the race, the only thing its customer learns is what the agent tells them. This step shows what that is.

## The experiment

Make a product with exactly one unit in stock, for the race. Mine:

```
./store products create --sku LANTERN-1 --name 'Storm Lantern' --category lighting --price-cents 4900 --stock 1
```

**Predict,** under `## M4-5` in `PREDICTIONS.md`: two agents are each told to buy it, at the same moment. How many orders will there be? And what will the losing agent tell its customer?

Open **two** fresh sessions in `~/code/store`, side by side in cmux. Check with `/mcp` in each that `store` is connected. Type the same request into both, and then press Enter in one and straight away in the other:

```
Buy one Storm Lantern for me: start a session, put it in the cart, and check out. Then tell me what happened.
```

Use the name of your own product. Approve each tool call or command each agent asks for, as fast as you can, so neither waits on you. Then count the orders for it:

```
docker compose exec db psql -U store -d store -c "SELECT p.sku, p.stock, count(l.order_id) AS orders FROM products p LEFT JOIN order_lines l ON l.product_id = p.id WHERE p.sku = 'LANTERN-1' GROUP BY p.sku, p.stock;"
```

**You should see** exactly one, and a stock of 0:

```
    sku    | stock | orders
-----------+-------+--------
 LANTERN-1 |     0 |      1
(1 row)
```

Paste both agents' final answers into `JOURNAL.md`, under `## M4-5`, and write what happened under your predictions.

<details><summary>What happened when this was tested (open it after your run)</summary>

It was tried three times, on 2026-11-08, with Claude Code 2.1.319 and Opus 5.5. Each time, a fresh product had 1 unit in stock, and two agent sessions were started at the same moment with the same request.

- **Each time, exactly one order was placed,** and the stock ended at 0.
- **The winners** each told their customer the order number and the price, and checked afterwards that the stock and the cart had changed.
- **In the first two runs, the losers lost at the cart.** By the time each tried to add the lantern, the other agent had already bought it, so the store answered "Only 0 of Storm Lantern in stock, so a cart can't hold 1." Each told its customer plainly that someone else had bought the last one a second or two earlier, and that nothing was ordered or charged.
- **In the third run, both agents got the lantern into their carts,** and the loser lost at checkout: "Only 0 of Storm Lantern left in stock." It told its customer that nothing was bought, and that its cart still held the lantern because the checkout failed as a whole. It chose not to raise the stock to force the sale. It also asked a fair question: its cart still showed the lantern as `available` with a total of $49.00, at a stock of 0. Should "available" mean "can be bought right now"?
- **Two losers went further,** to explain what happened. They queried the database directly, through `docker compose exec db psql`, and so saw another customer's session and order. Their customers got a good explanation. They also saw a stranger's data, because each agent had the same access to your Mac as you do.

Two lessons for M5. A clear refusal message travels: the losing agents repeated it almost word for word. And what an agent can see is everything its tools and commands can reach, which today is far more than a customer should.
</details>

**Three things to take from this:**
- **A refusal is the losing customer's whole story.** Your message, "Only 0 of … left in stock", went through the agent nearly word for word. A `500` would have reached them as "something went wrong".
- **"Nothing changed" is the second half of a good refusal.** The agents could promise their customers they weren't charged, because your checkout changes nothing when it refuses.
- **An agent sees what its tools reach.** In M5 you'll decide what a customer's agent gets.

## Check

There's no new check in this step. Everything before still passes:

```
make check M=4 STEP=5
```

## Step done

```
git add -A
git commit -m "M4-5: two agents, one unit"
git push
```

Answer your tutor's questions under `## M4-5` in `JOURNAL.md`.

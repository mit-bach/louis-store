# Step M4-4 · Two buyers at once

**Why:** checkout passed every check with one buyer at a time. The store's real promise is about two at once: one unit, two customers, the same instant. This step proves the promise, then takes the lock away to see what it was doing.

## 1. The race

`checks/race_test.py` is a given script. It adds a product of its own with one unit in stock. Then, for each round:
1. two new sessions each put that unit in their cart;
2. both check out at the same instant;
3. it reads the stock, and puts one unit back for the next round.

A safe store answers one `201` and one `409` every round, and ends each round with a stock of 0. When it's done, it archives its product, so your catalogue stops listing it.

**Predict,** under `## M4-4` in `PREDICTIONS.md`: out of 20 rounds, how many end with one order and one clean "out of stock"?

```
uv run checks/race_test.py --rounds 20
```

**You should see:**

```
Installed 7 packages in 8ms
20/20 rounds: one 201, one 409, stock 0
```

## 2. The control: take the lock away

Your step 3 work is committed. In `backend/orders.py`, delete the line `FOR UPDATE OF p` from your locking read, and save. Keep `ORDER BY p.id`. Give the server about 10 seconds to restart; `make logs` shows `Application startup complete.` when it has.

**Predict:** without the lock, both buyers can read a stock of 1 before either writes. What happens to the second buyer's checkout? Can the stock go below zero?

```
uv run checks/race_test.py --rounds 20
```

<details><summary>What mine showed (open it after your run)</summary>

```
  round 1: 201 and 500, stock 0: 201 {'id': 25, 'items': [{'product_id': 13, 'sku': 'RACE-1794165577133', 'name': 'Race test unit', 'quantity': 1, 'price_cen; 500 Internal Server Error
  round 2: 201 and 500, stock 0: 201 {'id': 27, 'items': [{'product_id': 13, 'sku': 'RACE-1794165577133', 'name': 'Race test unit', 'quantity': 1, 'price_cen; 500 Internal Server Error
  round 3: 201 and 500, stock 0: 201 {'id': 29, 'items': [{'product_id': 13, 'sku': 'RACE-1794165577133', 'name': 'Race test unit', 'quantity': 1, 'price_cen; 500 Internal Server Error
  round 4: 201 and 500, stock 0: 201 {'id': 31, 'items': [{'product_id': 13, 'sku': 'RACE-1794165577133', 'name': 'Race test unit', 'quantity': 1, 'price_cen; 500 Internal Server Error
  round 5: 201 and 500, stock 0: 201 {'id': 33, 'items': [{'product_id': 13, 'sku': 'RACE-1794165577133', 'name': 'Race test unit', 'quantity': 1, 'price_cen; 500 Internal Server Error
  round 6: 201 and 500, stock 0: 201 {'id': 35, 'items': [{'product_id': 13, 'sku': 'RACE-1794165577133', 'name': 'Race test unit', 'quantity': 1, 'price_cen; 500 Internal Server Error
  round 8: 201 and 500, stock 0: 201 {'id': 38, 'items': [{'product_id': 13, 'sku': 'RACE-1794165577133', 'name': 'Race test unit', 'quantity': 1, 'price_cen; 500 Internal Server Error
  round 9: 201 and 500, stock 0: 201 {'id': 40, 'items': [{'product_id': 13, 'sku': 'RACE-1794165577133', 'name': 'Race test unit', 'quantity': 1, 'price_cen; 500 Internal Server Error
  round 10: 201 and 500, stock 0: 201 {'id': 42, 'items': [{'product_id': 13, 'sku': 'RACE-1794165577133', 'name': 'Race test unit', 'quantity': 1, 'price_cen; 500 Internal Server Error
  round 11: 201 and 500, stock 0: 201 {'id': 44, 'items': [{'product_id': 13, 'sku': 'RACE-1794165577133', 'name': 'Race test unit', 'quantity': 1, 'price_cen; 500 Internal Server Error
  round 12: 201 and 500, stock 0: 201 {'id': 46, 'items': [{'product_id': 13, 'sku': 'RACE-1794165577133', 'name': 'Race test unit', 'quantity': 1, 'price_cen; 500 Internal Server Error
  round 13: 201 and 500, stock 0: 201 {'id': 48, 'items': [{'product_id': 13, 'sku': 'RACE-1794165577133', 'name': 'Race test unit', 'quantity': 1, 'price_cen; 500 Internal Server Error
  round 14: 201 and 500, stock 0: 201 {'id': 50, 'items': [{'product_id': 13, 'sku': 'RACE-1794165577133', 'name': 'Race test unit', 'quantity': 1, 'price_cen; 500 Internal Server Error
  round 15: 201 and 500, stock 0: 201 {'id': 52, 'items': [{'product_id': 13, 'sku': 'RACE-1794165577133', 'name': 'Race test unit', 'quantity': 1, 'price_cen; 500 Internal Server Error
  round 16: 201 and 500, stock 0: 201 {'id': 54, 'items': [{'product_id': 13, 'sku': 'RACE-1794165577133', 'name': 'Race test unit', 'quantity': 1, 'price_cen; 500 Internal Server Error
  round 18: 201 and 500, stock 0: 201 {'id': 57, 'items': [{'product_id': 13, 'sku': 'RACE-1794165577133', 'name': 'Race test unit', 'quantity': 1, 'price_cen; 500 Internal Server Error
  round 20: 201 and 500, stock 0: 500 Internal Server Error; 201 {'id': 60, 'items': [{'product_id': 13, 'sku': 'RACE-1794165577133', 'name': 'Race test unit', 'quantity': 1, 'price_cen
3/20 rounds: one 201, one 409, stock 0
```

Most rounds ended with one order and one `500`. Without the lock, both checkouts read a stock of 1, both decided "enough", and both went on to write. The second `UPDATE products SET stock = stock - 1` would have taken the stock to −1, and your M1 `CHECK (stock >= 0)` refused it. Postgres raised `CheckViolation`, nothing caught it, and FastAPI answered `500`. The stock never went negative and nobody got the unit twice: the `CHECK` held. But a crash is a terrible answer to a customer, and an agent can't act on "Internal Server Error". The rounds that came out clean were the ones where one checkout happened to finish before the other read. In testing, without the lock, 3 to 7 rounds out of 20 were clean.
</details>

`make logs` shows the `CheckViolation` behind each `500`. Write under your prediction what happened, and why. Then put the lock back:

```
git checkout -- backend/orders.py
```

Give the server 10 seconds again, and race once more. **You should see** `20/20` again.

**The lesson in one line:** the `CHECK` stopped the oversell, and the lock turned the crash into a clean answer. Each does a different job.

## 3. The deadlock test

`checks/deadlock_test.py` is given too. It adds two products of its own, A and B, with plenty in stock. Each round, one session puts A then B in its cart, the other puts B then A, and both check out at once. Both should get an order.

```
uv run checks/deadlock_test.py --rounds 20
```

**You should see:**

```
Installed 7 packages in 5ms
20/20 rounds: two 201s
Deadlocks Postgres broke during the test: 0
```

The last line comes from Postgres itself, which counts every deadlock it has had to break.

## 4. The second control: take the order away

Now delete only `ORDER BY p.id` from your locking read, keep `FOR UPDATE OF p`, and save. Wait for the restart.

**Predict:** without `ORDER BY`, will two carts with opposite orders deadlock?

```
uv run checks/deadlock_test.py --rounds 20
```

<details><summary>What happened when this was tested (open it after your run)</summary>

```
20/20 rounds: two 201s
Deadlocks Postgres broke during the test: 0
```

No deadlock, and not in 160 rounds of testing either. That's not because `ORDER BY` doesn't matter. Without it, the order of the locks is whatever order Postgres happens to read the rows in, and here its plan read `products` in id order anyway: in storage order when the table was small, through its primary key when it held 20,000 rows. So both checkouts happened to lock A then B.

Nothing promises that the plan stays that way. An index, a bigger table or a newer Postgres can change it. `ORDER BY p.id` makes the order a rule instead of a coincidence.

What did deadlock in testing was option (a) from step 2: a checkout that runs one `UPDATE` per line, in the cart's order. It deadlocked in every run, but rarely: 16 times in 660 rounds over three runs, and only once in a run of 100. Rare is exactly what makes deadlocks dangerous: they pass most tests, then appear on a busy day. That's why the check runs this test for 500 rounds, which takes about 15 seconds. At the rate seen in testing, 500 rounds catch that checkout nearly every time. No number of rounds can promise it.
</details>

Put `ORDER BY` back:

```
git checkout -- backend/orders.py
```

## Check

```
make check M=4 STEP=4
```

**You should see** everything before, then:

```
  PASS  M4-4  the checkout race: 20 rounds of two buyers and one unit, each round one 201, one 409, stock 0
  PASS  M4-4  the deadlock test: 500 rounds of two carts with the same two products, put in in opposite orders, all bought

97 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

The check races 20 rounds, and runs the deadlock test for 500.

## Step done

`git status` should list only your journal and predictions: `backend/` must match your step 3 commit.

```
git status --short
```

```
 M JOURNAL.md
 M PREDICTIONS.md
```

```
git add -A
git commit -m "M4-4: two buyers at once"
git push
```

Answer your tutor's questions under `## M4-4` in `JOURNAL.md`.

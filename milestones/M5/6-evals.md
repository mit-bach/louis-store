# Step M5-6 · Evals

**Why:** an agent does slightly different things each time. One good transcript tells you it *can* do a task, not that it usually does, or what a change to your store did to it. You measure an agent the way you measure anything that varies: the same tasks, many times, each checked against what should have happened, and a score. Those tasks are called **evals**.

## The idea

`checks/evals.py` is a given script. It holds five shopping tasks. For each one, it:
1. adds the task's products to your store, at port 8000;
2. runs your customer agent once, **headless**: `claude -p "<the customer's request>"`, from `agents/customer`, with only the store's tools. Headless means no conversation and nobody to approve anything: it runs, answers once, and exits. That's how agents run on errands, and it's what step 5's control showed;
3. reads the orders the agent placed, straight from the database, and compares them with what the task asked for;
4. archives the task's products.

The five tasks:
1. "Buy the two cheapest snacks in the store, one of each."
2. "Buy three Trail Maps. If the store has fewer than three, buy as many as it has." (It has 2.)
3. "Put one Fig Bar in my cart. Then add one more Fig Bar, and one Oat Bar. Then check out."
4. "Buy me a Summit Stove." (It's been archived. A Valley Stove is for sale.) The right result is no order at all.
5. "I have $20. Buy as many Energy Gels as I can afford." (They're $3.50.)

It runs on **Haiku**, Claude's smallest model, unless you pass `--model`. That keeps it cheap, and a smaller model shows a weakness in your tools that a bigger one would cover for. Each run adds a line to `checks/evals-runs.txt`. The line holds the score, and a short fingerprint of your tool descriptions, so you can see which version of them each score belongs to.

**What it costs.** Each task is a whole agent session. In testing, one run of the five on Haiku cost about $0.015 by Claude Code's own estimate, and the same run on Opus cost $0.33 to $0.52. The script prints the estimate for every run. If you use Claude Code through a Claude subscription, you aren't charged that amount. The same usage counts toward your plan's limits instead.

## 1. Your score

**Predict,** under `## M5-6` in `PREDICTIONS.md`: how many of the five will your agent pass?

```
uv run checks/evals.py
```

**You should see** each task and whether it passed, then the score. A failed task also shows what it wanted, what it got, and what the agent said. Mine:

```
Evals: 5 task(s) × 1 for your customer agent, on haiku, at 2026-11-08 16:45.
Your tool descriptions: 0c4a59dd

  1 · the two cheapest snacks: PASS
  2 · as many maps as there are: PASS
  3 · one more fig bar: PASS
  4 · not for sale: PASS
  5 · twenty dollars of gels: PASS

Score: 5/5.
Orders placed with an idempotency key: 4 of 4.
This run: 5 agent sessions, about 581,187 tokens read and 4,947 written. Claude Code priced it at $0.01.
Saved to checks/evals-runs.txt
```

If a task failed, read that session. `tx.py` shows every tool call it made:

```
python3 ~/tutor/orchestrator/tools/tx.py $(ls -t ~/.claude/projects/*store-agents-customer/*.jsonl | head -1) | grep -E "TOOL|ASSIST"
```

`head -1` is the last task run. Use `head -2 | tail -1` for the one before it, and so on.

## 2. The control: vague descriptions

Your step 2 and step 3 work is committed. In `backend/tools.py`, replace every tool's docstring with a single word, like `"""Cart."""`. Then delete every `description="…"` from the tools' arguments. Save, and give the server 10 seconds.

**Predict:** with descriptions that say almost nothing, what happens to the score?

A model does slightly different things each time, so one run is one sample. For the controls, run each task three times, which costs about $0.05 on Haiku:

```
uv run checks/evals.py --runs 3
```

<details><summary>What mine showed (open it after your run)</summary>

```
By task: 1 3/3 · 2 2/3 · 3 3/3 · 4 3/3 · 5 3/3
Score: 14/15.
Orders placed with an idempotency key: 11 of 11.
This run: 15 agent sessions, about 1,733,763 tokens read and 15,708 written. Claude Code priced it at $0.04.
Saved to checks/evals-runs.txt
```
</details>

## 3. The control: one wrong description

Put your descriptions back:

```
git checkout -- backend/tools.py
```

Now make one description wrong, the way a docstring goes stale when the code under it changes. Make `set_cart_item`'s docstring say that it **adds** the quantity to what's already in the cart, and make its quantity's description say `How many to add.`

**Predict:** which task fails, if any? And what will the agent do when it notices?

```
uv run checks/evals.py --runs 3
```

<details><summary>What mine showed (open it after your run)</summary>

Mine, without the lines for tasks that passed:

```
Evals: 5 task(s) × 3 for your customer agent, on haiku, at 2026-11-08 16:49.
Your tool descriptions: ac661da3

Run 1 of 3:
  3 · one more fig bar: FAIL
      asked: Put one Fig Bar in my cart. Then add one more Fig Bar, and one Oat Bar. Then check out.
      wanted order Fig Bar ×2, Oat Bar ×1; got no order
      the agent said: I stopped before checkout. Your cart has one Fig Bar and one Oat Bar, not the two Fig Bars you asked for, and I haven't bought anything. **Cart now:** Fig Bar × 1 ($3.00) and Oat Bar × 1 ($3.00), total $6.00. **What happened:** The first Fig Bar add worked. The second Fig Bar add, sent three times, still left the Fig Bar quantity at 1. The store's tool description says an add goes on top of what's
Run 2 of 3:
  3 · one more fig bar: FAIL
      asked: Put one Fig Bar in my cart. Then add one more Fig Bar, and one Oat Bar. Then check out.
      wanted order Fig Bar ×2, Oat Bar ×1; got no order
      the agent said: I didn't check out. The cart has 1 Fig Bar and 1 Oat Bar ($6.00), not the 2 Fig Bars and 1 Oat Bar you asked for. The store's add tool didn't stack: I added a Fig Bar three times and the cart still shows quantity 1 for it. The tool's description says each call adds to what's already there, so the behaviour doesn't match the docs. Because the cart doesn't match your request, I bought nothing, and I
Run 3 of 3:

By task: 1 3/3 · 2 3/3 · 3 1/3 · 4 3/3 · 5 3/3
Score: 13/15.
Orders placed with an idempotency key: 10 of 10.
This run: 15 agent sessions, about 1,882,951 tokens read and 20,847 written. Claude Code priced it at $0.04.
Saved to checks/evals-runs.txt
```

Tested on 2026-11-08 with Claude Code 2.1.319 and Haiku 5.5, against the course's own reference store and a customer agent like the one step 4 asks for.

- **Precise descriptions:** 82 of 85 tasks passed, over 17 runs.
- **Vague descriptions:** 44 of 45, over 9 runs, and 5 of 5 on Opus. The names did the work. `set_cart_item` says "set", and `idempotency_key` says what it is: every order was still sent with a key.
- **One wrong description** (`set_cart_item` "adds"): task 3 failed in 4 of 6 runs. Every time, the agent believed the description, and "added" a second Fig Bar that left one in the cart. Then, when it looked at its cart, it either set the line to 2 itself and passed, or stopped and told its customer the cart didn't match, as its brief says to.
- **Two failures had nothing to do with descriptions:**
  - **Task 1, once:** Haiku picked Trail Mix at $4.50 over Dried Mango at $3.50. A slip.
  - **Task 2, three times in about 30 runs:** the agent asked before buying 2 Trail Maps instead of 3, though the customer had already said to buy as many as there were. Its brief said to ask before buying a different quantity, and it put the brief ahead of the request. That's a brief to sharpen, not a tool.
</details>

Write under each prediction what happened, and why. **The lesson:** an agent reads your tool's name, its arguments' names and its description, and believes all of them. Where the names already say it, a vague description costs little. A wrong one misleads the agent every time. Whether that costs you the task depends on whether the agent happens to check what it did, and you can't count on that.

## 4. Your rewrite

Put the descriptions back once more (`git checkout -- backend/tools.py`). Then read each of your tools as an agent would, seeing only its name, its arguments and its description. Where does the name leave something out? `set_cart_item` doesn't say "set, not add" loudly enough to survive a careless reading. Does `checkout` say what a refusal changes, and when to reuse a key? Improve what you find, save, and run the evals once more. If a task still fails, read what the agent said before you change anything: not every failure is your tools'. In testing, task 2 sometimes failed because the agent's brief said to ask before buying a different quantity, and the agent put that ahead of the customer's own "buy as many as it has". That's a brief to sharpen, not a description.

```
uv run checks/evals.py
```

A last caution. These five tasks are now the tasks you tune against. If you kept rewriting until all five passed every time, you'd be fitting your descriptions to these five, and the score would stop telling you how your agent shops in general. The usual fix is to keep some tasks aside: you tune against some, and judge against others you never looked at while tuning. You'll meet that idea again, with **training, validation and test** sets, in a later project. Here, it's enough to know that the score is only as honest as the tasks behind it.

Write under `## M5-6` in `JOURNAL.md`: each run's score, with what you'd changed before it, and what each one cost. `checks/evals-runs.txt` has them all:

```
cat checks/evals-runs.txt
```

```
2026-11-08 16:45 · haiku · score 5/5 · keys 4/4 · tasks 1,2,3,4,5 × 1 · descriptions 0c4a59dd · $0.01
2026-11-08 16:46 · haiku · score 14/15 · keys 11/11 · tasks 1,2,3,4,5 × 3 · descriptions e8c29b11 · $0.04
2026-11-08 16:49 · haiku · score 13/15 · keys 10/10 · tasks 1,2,3,4,5 × 3 · descriptions ac661da3 · $0.04
2026-11-08 16:57 · haiku · score 4/5 · keys 3/3 · tasks 1,2,3,4,5 × 1 · descriptions 0c4a59dd · $0.01
```

## Check

The whole milestone. The last check reads `checks/evals-runs.txt`, and wants at least two runs, against two versions of your descriptions:

```
make check M=5
```

**You should see** every M0 to M4 check pass, then:

```
  PASS  M5-1  orders has idempotency_key, and the database refuses a second order with the same session and key
  PASS  M5-1  checkout(token, key) twice: the same order back, one order placed, the stock lowered once
  PASS  M5-1  a key belongs to its session; without a key, checkout is as in M4; a refused checkout records nothing
  PASS  M5-2  the Idempotency-Key header, --idempotency-key and the tool's idempotency_key: the same key twice, the same order
  PASS  M5-2  the retry test through HTTP: 20 rounds, each checkout sent twice with one key
  PASS  M5-2  the retry test through ./store: 6 rounds
  PASS  M5-2  the retry test through the tools: 10 rounds
  PASS  M5-3  when something breaks, every way in answers with the contract's message, never a traceback, and nothing changes
  PASS  M5-3  each cart line says in_stock: whether its quantity is in stock right now, through every way in
  PASS  M5-4  agents/customer has the customer agent's brief, in your words, its tool server, and its settings
  PASS  M5-4  its permissions: every customer tool allowed; the shell, the web and every admin tool denied
  PASS  M5-4  every tool your store has is either allowed or denied for the customer agent
  PASS  M5-4  the customer agent doesn't load your developer rules: the top CLAUDE.md is excluded, its own isn't
  PASS  M5-5  checks/evals-runs.txt has your eval runs: at least two, against two versions of your tool descriptions

112 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

## Step done

```
git status --short
```

```
 M JOURNAL.md
 M PREDICTIONS.md
?? checks/evals-runs.txt
```

```
git add -A
git commit -m "M5-6: evals"
git push
```

That's M5. Go through "M5 is done when" in [`README.md`](README.md), including the review by your `store-reviewer` skill.

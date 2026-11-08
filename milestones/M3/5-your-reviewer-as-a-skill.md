# Step M3-5 · Your reviewer, as a skill

**Why:** at the end of M1 and M2, you pasted `reviewer/REVIEWER.md` into a fresh session to get a review. Instructions you paste every time belong in your harness, where an agent finds them on its own. That's what a **skill** is. This step makes your reviewer one, in your tutor harness, and tests the one line that decides whether an agent ever uses it.

## The idea: a skill

A skill is a folder holding a file called `SKILL.md`, which starts with a short header between two `---` lines, and then has instructions:

```markdown
---
name: store-reviewer
description: …
---

The instructions an agent follows when it uses the skill.
```

- **When a session starts,** Claude Code reads the `name` and `description` of every skill it can see, and nothing else.
- **When a task looks like it matches a description,** the agent loads that skill's instructions, and follows them. You can also ask for a skill by name.
- **So the description is the trigger.** It's the same job a tool's docstring does in M1-7: the only thing an agent knows about it before it chooses.

Skills in `~/tutor/.claude/skills/` are seen by every session started in your tutor harness, your store tutor included, even though it starts in a course folder below. That was tested with Claude Code 2.1.319.

Your harness's skills are part of the harness, so this is a harness change: you make it through Tutor Orch, with a prediction and a line in `RULES-LOG.md`, as in M2-7.

## 1. The skill, through Tutor Orch

Open "Tutor Orch" in Berth, and ask it to create a skill called `store-reviewer` in your harness, from your store's reviewer prompt. Tell it:
- the file is `~/tutor/.claude/skills/store-reviewer/SKILL.md`;
- the instructions are `~/code/store/reviewer/REVIEWER.md`, from the line that starts "You are reviewing" to the end;
- the description, for now, is exactly: `Helps with code.`

That vague description is on purpose: it's the first half of the experiment. Tutor Orch logs the change, with your prediction.

## 2. The experiment: a vague description, then a precise one

**Predict,** under `## M3-5` in `PREDICTIONS.md`, two lines:
1. With the description "Helps with code.", you tell your store tutor "review my diff". Will it use the skill?
2. With a description that says what the skill reviews and when to use it, will it?

**Run A, vague.** Your store tutor reads skills when it starts, so close it and open it again in Berth. Send it exactly:

```
review my diff
```

When an agent loads a skill, the session shows it, naming the skill. Note which skill was loaded, if any, and what it reviewed: your store, or something else.

**Run B, precise.** Ask Tutor Orch to change the description to one of your own words. It should say:
- what the skill does: reviews your store code against the contract and the guides, and names problems without fixing them;
- when to use it: when you ask to review your diff, your changes, a step or a milestone.

Close and reopen your store tutor, send `review my diff` again, and note what happens. Tutor Orch fills in the log entry's outcome.

<details><summary>What happened when this was tested (open it after your runs)</summary>

It was tried on 2026-11-08, with Claude Code 2.1.319 and Opus 5.5, in a copy of this tutor harness. The store had one uncommitted change, which pasted a value into SQL with an f-string. Each run was a fresh store tutor, sent "review my diff".

- **"Helps with code.":** the skill was used 0 times out of 3. Every time, the tutor chose a different skill instead: Claude Code's own `code-review`, whose description says it reviews the current diff. That skill reviewed the wrong repository: the tutor harness's own uncommitted files, not the store. It reported 15 problems, none of them in Louis's code.
- **A precise description,** saying what it reviews and when to use it, including "review his diff": the skill was used 3 times out of 3. Each review read the store's diff, and named the f-string in the SQL as a problem.

The description isn't just a label. Every skill a session can see competes for each request, on its description alone. A vague one loses to any skill that describes the task better, even one that does the wrong job. The same is true of your tools' docstrings in M1-7.
</details>

## 3. Use it: the M3 review

With the precise description in place, ask your store tutor to review M3. Copy each finding into `JOURNAL.md`, under `## M3 review`, with what you did about it: fixed, or why not.

## Check

The whole milestone. The last check reads your harness's skills, and wants one whose description mentions reviewing, and whose instructions use `CONTRACT.md`:

```
make check M=3
```

**You should see** every M0, M1 and M2 check pass, then:

```
M3 · Visitors and carts
  PASS  M3-1  sessions.py and cart.py import nothing from the web, the command line or the tool server
  PASS  M3-1  the sessions table: a token as its key, and when it expires
  PASS  M3-1  start_session() makes a long random token, valid for an hour
  PASS  M3-1  require_session() names what's wrong: no token, a made-up token, an expired one
  PASS  M3-1  POST /sessions, ./store session start and the start_session tool each start a session
  PASS  M3-2  the cart_items table: one line per session and product, a quantity above zero, and lines that go with their session
  PASS  M3-2  get_cart() joins each line to its product, totals it, and leaves archived products out of the total
  PASS  M3-2  GET /cart: 200 with a live token; 401 with the contract's message without one, or with a bad or expired one
  PASS  M3-2  ./store cart show and the get_cart tool: the cart with a live token, the same three messages without one
  PASS  M3-3  set_cart_item() sets a line's quantity, replaces it the second time, and refuses what can't be sold
  PASS  M3-3  PUT and DELETE /cart/items/{id}: the cart back, 422 for quantity 0, 409, 404 and 401 with their messages
  PASS  M3-3  ./store cart set and remove, and the set_cart_item and remove_cart_item tools: the same results and errors
  PASS  M3-3  parity: the session and cart operations each have a route, a command and a tool
  PASS  M3-4  two sessions have two carts: what one puts in, the other doesn't see
  PASS  M3-5  your tutor harness has the reviewer as a skill, with a name and a description that says when to use it

86 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

## Step done

Your skill lives in `~/tutor`, not in this repository, so here only your journal and predictions have changed:

```
git status --short
```

```
 M JOURNAL.md
 M PREDICTIONS.md
```

```
git add -A
git commit -m "M3-5: the reviewer, as a skill"
git push
```

That's M3. Go through "M3 is done when" in [`README.md`](README.md).

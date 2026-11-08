# Step M4-6 · The audit of your harness

**Why:** since M0 you've changed your harness four times: a rules file, a tool server, a wall on both sides, a skill. Each time you predicted, changed, and checked once. An audit asks the harder question, with evidence: did those changes *keep* working, session after session? This is how you'd look after a harness you rely on: by reading what it actually did, not what you meant it to do.

## 1. Gather the evidence

**Your rules log.** Every change you made through Tutor Orch is an entry, with your prediction and what happened:

```
cat ~/tutor/orchestrator/RULES-LOG.md
```

**Your sessions.** Open Berth (⌘⇧B in cmux), and look at your `Tutor` folder: which sessions exist, which you actually use, and which are idle or forgotten.

**Two transcripts.** Claude Code saves every session as a `.jsonl` file under `~/.claude/projects/`, in a folder named after the session's working directory. Your store tutor's two most recent:

```
ls -t ~/.claude/projects/*tutor-courses-01-online-store/*.jsonl | head -2
```

Your harness has a tool that turns one into readable lines: what you typed, which rules files were loaded, which skills were used, which files were read, and every tool call. For each of the two files:

```
python3 ~/tutor/orchestrator/tools/tx.py <the file> --max 160 | head -60
python3 ~/tutor/orchestrator/tools/tx.py <the file> --users
```

The first shows the session as a list of events, one per line. `RULES` lines are the `CLAUDE.md` files that were loaded, `SKILL` lines are skills it used, and `TOOL` lines are its tool calls. The second shows only your own messages, in full. Here is the start of one from testing, a tutor asked to review a diff:

```
2026-11-08T18:34:25 USER    review my diff
2026-11-08T18:34:30 TOOL    Skill: {"skill": "store-reviewer"}
2026-11-08T18:34:30 SKILL   Base directory for this skill: …/tutor/.claude/skills/store-reviewer
```

## 2. Write the audit

**Predict** first, under `## M4-6` in `PREDICTIONS.md`: of your harness changes so far, which one do you expect to have drifted, or not to have mattered?

Then write about half a page in `JOURNAL.md`, under a heading `## M4 audit`, in your own words. Answer, with evidence from what you read:
- **Which changes held?** For each entry in your rules log: did later sessions behave the way the change intended? Point at a line in a transcript.
- **Which drifted, or never mattered?** A rule nobody needed, a skill that never loaded, a session that does nothing.
- **What surprised you** in the transcripts: something a tutor read, loaded or did that you didn't expect.
- **One change you'd make now,** and why.

**If your rules log has no entry of your own yet,** the audit has to end in one: make the change you named, through Tutor Orch, with a prediction and a log entry, the way you did in M2-7.

## 3. Your first compaction, through Berth

A long session gets compacted: Claude Code replaces the old conversation with a summary, to make room. Done badly, a session forgets what it was doing. Berth does it properly. You give it a short note saying what the summary is for, and it compacts the session, then checks Claude's own record that the compaction really happened. **Never paste `/compact` into a session yourself:** a pasted note arrives as a plain message, and the session may take it as a new job.

**Predict:** after compaction, will your store tutor still know which step you're on, and what you decided along the way?

Ask Tutor Orch to compact your store tutor through Berth. Its rule for this is §5a, "Compacting any session", in `~/tutor/orchestrator/ORCHESTRATOR.md`: read it first. The note it writes gives:
- **TASK:** keep teaching course 01 from where we are now;
- **SEAT:** the Store Tutor, working in `~/tutor/courses/01-online-store`;
- **SOURCES:** the course's `COURSE.md`, and `~/code/store/JOURNAL.md` and `PREDICTIONS.md`.

Tutor Orch writes the note to a file and asks Berth to compact with it. Berth reports when it's `done`. Then ask your store tutor, in one line, which step you're on and what you decided in step 2. Compare its answer with your journal, and write under your prediction what it kept and what it lost. `tx.py` on its transcript now shows a `COMPACT` line where the summary begins.

## Check

The whole milestone. The last check reads your journal's `## M4 audit`, and wants about half a page. It also wants at least one entry in your harness's rules log:

```
make check M=4
```

**You should see** every M0 to M3 check pass, then:

```
M4 · Checkout, and two buyers at once
  PASS  M4-1  the orders and order_lines tables: an order keeps its lines, each line the price it was bought at
  PASS  M4-1  an order outlives its session: deleting the session leaves the order
  PASS  M4-2  orders.py imports nothing from the web, the command line or the tool server
  PASS  M4-2  checkout() places one order at the database's prices, lowers the stock, and empties the cart
  PASS  M4-2  an order keeps the price it was bought at, after the product's price changes
  PASS  M4-2  checkout() refuses an empty cart, a short line or an unavailable line, with the contract's message, and changes nothing
  PASS  M4-3  POST /checkout: 201 with the order; 409 with the contract's message; 401; and it ignores a total the client sends
  PASS  M4-3  ./store checkout and the checkout tool: the order, or the same messages with exit 4 or 5 and a tool error
  PASS  M4-3  parity: checkout has its route, its command and its tool
  PASS  M4-4  the checkout race: 20 rounds of two buyers and one unit, each round one 201, one 409, stock 0
  PASS  M4-4  the deadlock test: 500 rounds of two carts with the same two products, put in in opposite orders, all bought
  PASS  M4-6  your journal has the audit of your tutor harness, and your harness's rules log has at least one change

98 passed, 0 failed, 0 skipped.
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
git commit -m "M4-6: the audit of my harness"
git push
```

That's M4, and the store itself is complete. Go through "M4 is done when" in [`README.md`](README.md), including the review by your `store-reviewer` skill.

<!--
For Tutor Orch, in Louis's tutor harness: this is course 01's text. To start the course:
  tools/new-course.sh 01-online-store "The online store" --session "Store Tutor" --format work-through --asked "<his words, from his brief>" --lab off
then replace everything below the generated header table with everything below the line of dashes in this file.
Keep the generated header table, and set its State row as the tutor goes.
-->

The rules for how every tutor behaves are in `../../CLAUDE.md`. His profile is `../../student/PROFILE.md`. This file adds only what is specific to this course.

---

## 1. The goal

He builds the backend of a small online store by hand, agent-first: every operation he writes is reachable over HTTP, from the command line (`./store`) and as an MCP tool, all calling the same function. Dominik's rule for it: "you can't have the AI just write all the files." By the end, he can explain every line, a checkout never oversells when two customers race for the last unit, and an agent can do anything in the store a person can.

## 2. Sources this course teaches from

The store kit, at `~/code/store`, from [`mit-bach/louis-store`](https://github.com/mit-bach/louis-store). Its guides are this course's lessons (`../../formats/work-through.md` §6). Read these before every step:
- `BRIEF.md` and `CONTRACT.md`: what he builds, exactly;
- `milestones/M<n>/README.md`, and the step file you're serving;
- `checks/last-run.txt`: the result of his last `make check`, with the commit it ran on;
- `JOURNAL.md` and `PREDICTIONS.md`: his decisions, experiments, review findings, answers and predictions;
- his code, read with git: `git -C ~/code/store log`, `diff` and `show`.

## 3. What he writes himself, and what agents may do

- **His files:** everything in `~/code/store/backend/` that a guide marks as his (the migrations, the seed, `schemas.py`, `products.py` and later operations, his routes, commands and tools), plus `AGENTS.md`, `JOURNAL.md` and `PREDICTIONS.md`.
- **You never write or edit them,** and never show him a finished version. There's no solution in the kit, on purpose. Review by naming the problem, its file and line, and why it matters, never by fixing it.
- **You never run anything in `~/code/store`:** not `make check`, not `make reset`, not `./store`. The checks write to his database. Review from `checks/last-run.txt` and git.
- **His coding agent** follows his `AGENTS.md`: it may explain and review, never write his backend code. From M2, a hook in the repository enforces it.

## 4. How this course's lessons differ from the format

- **Lesson 01 is the gate.** Keep it short: what the store is, how a step works (`milestones/README.md`), and the line on who writes what. End with "Is this the shape you want?" Nothing else goes out until he answers.
- **Then the kit's steps, in order,** one at a time: M0-1, M0-2, M0-3, M1-1 … Serve each by pointing him to its file. You may add a bridge of two or three sentences at the top, tied to his last journal entry. Never rewrite a guide.
- **Records are named by step:** `lessons/M1-3.md` holds your bridge, your review of his step, and your three questions; `prompts/RESPONSE-M1-3.md` holds what he says in chat, verbatim.
- **Your three questions** for each step are about what he understood from what he built, not what he typed. He answers them in `JOURNAL.md`, under the step's heading. **The next step opens once that section holds his answers,** and the step's check has passed in `checks/last-run.txt`.
- **Predictions:** each line in `PREDICTIONS.md` is tagged `[code]`, `[agent]` or `[harness]`. Mark each a hit or a miss, and keep the tally per thread in `MASTERY.md`.
- **At the end of each milestone,** he gets a review: from `reviewer/REVIEWER.md` in a fresh session until M3, then from the `store-reviewer` skill. He records each finding in his journal. Check that each one is fixed or answered.
- **A problem in a guide or a check** (a wrong expected output, a step that doesn't work) isn't yours to fix, and isn't his fault. He sends Dominik the step, the command and its output. Updates reach him with `make update`, which merges the kit's new commits into his repository.

## 5. Plan

The kit's milestones, about 12 working days in all:
- **M0** · Setup, and an agent that follows your rules: 3 steps.
- **M1** · Products, and the store's first tools: 7 steps.
- **M2** · The admin side, and your first race: 7 steps. Step 7 has him add a deny rule to this course's settings through Tutor Orch: a harness change, with a prediction and a `RULES-LOG.md` entry.
- **M3** · Visitors and carts: 5 steps. Step 5 has him make the reviewer a skill in this harness (`~/tutor/.claude/skills/store-reviewer/`) through Tutor Orch, and test its description: a vague one, then a precise one. From then on, the end-of-milestone review is that skill.
- **M4** · Checkout, and two buyers at once: 6 steps.
  - Step 4 has him race two buyers for the last unit, then remove his lock, and then his `ORDER BY`, to see what each was doing.
  - Step 6 is his first audit of this harness. He reads `orchestrator/RULES-LOG.md`, his sessions in Berth and two transcripts through `orchestrator/tools/tx.py`, and writes half a page on which changes held. If the rules log has no entry of his own yet, the audit ends in one, made through Tutor Orch with a prediction and a log entry.
  - Then he asks Tutor Orch to compact his store tutor through Berth, for the first time (`orchestrator/ORCHESTRATOR.md` §5a, "Compacting any session").
- **M5** · Agent-first, for real: retries, errors, scope and evals: 6 steps.
  - Step 4 has him build the customer's agent in `agents/customer/`: a brief, its own tool server, and permissions that allow only the customer tools and deny the shell, the web and the admin tools. `tx.py` (louis-tutor 1.0.4 or newer) shows which rules files it loads.
  - Step 5 tests it: the same request to it and to a full agent, M4-5's race with two customer agents, and `checkout` behind a click.
  - Step 6 runs `checks/evals.py`: five shopping tasks, headless, each checked in the database, with his tool descriptions as he wrote them, vague, wrong, and rewritten. His scores, and what each run cost, go in `JOURNAL.md`.
- **M6** · The frontend, built by his agent.

M0 to M5 are in the kit now. The rest arrive in order, each tested before it does.

## 6. Course files

- **`LEARNING-NOTES.md`:** the goal, the plan, the lesson index, Where we are, F-entries, the glossary and the answer record.
- **`MASTERY.md`:** this course's skill map, and the prediction tally.
- **`lessons/`:** Lesson 01, then one file per step, `M<n>-<step>.md`.
- **`research/_tutor-hypotheses.md`:** the tutor-only, evolving view.
- **`prompts/`:** his replies, verbatim: `RESPONSE-00.md` for the brief, then `RESPONSE-M<n>-<step>.md`.

# How the guides work

Each milestone is a folder. Its `README.md` says what works at the end, who writes what, and what "done" means. Each numbered file in it is one **step**: one piece of building, which ends with a check you run yourself. Do the steps in order, one at a time. Your tutor serves them to you one by one, and opens the next once your journal has the last one's entries.

## Three kinds of content, taught three ways

Every part of a step is one of these, and it says which.
1. **Given:** configuration and glue, like the compose file or the database connection. There's one right way to write it, so the guide gives the whole file. You type it in (or copy it), and each line is explained underneath. After it come the commands to run, **You should see** with the exact output, and **If something doesn't match** with the usual causes.
2. **Decide first:** a real design choice, like how to store a price. You get the options and the facts that decide it. You write your choice and why in `JOURNAL.md` *before* you open the answer, which is folded underneath.
3. **You write:** your own code, in small pieces. Each piece has the same shape:
   - **The idea,** with every construct you need explained.
   - **An example on a different problem.** It's always a small library, with books, so you see the shape without seeing your answer.
   - **Your contract:** the file, the names, what it must do, the exact error messages, and one hint.
   - **A check** you run straight away, with exactly what you should see.

   There's no finished version of your code anywhere in this kit. If you're stuck, read "If you're stuck" at the end of this page.

## Predictions

Some steps ask you to **predict** before you run something: "write in `PREDICTIONS.md` what you think will happen". Do it before you press Enter, in one line. Then write what actually happened, and why you were wrong if you were. Mark each one `[code]`, `[agent]` or `[harness]`, for what it's about. Your tutor keeps score for each kind separately. That score rising is how you'll know your intuition is forming.

## The checks

`make check M=1` runs every check up to milestone 1. `make check M=1 STEP=3` stops after step 3 of milestone 1. Each run:
1. starts a throwaway copy of your store, with its own empty database, on port 8001;
2. applies your migrations and your seed to it;
3. runs the checks, printing `PASS`, `FAIL` or `SKIP` for each;
4. saves what it printed to `checks/last-run.txt`, which your tutor reads;
5. removes the throwaway copy.

Your own store, and the data in it, are never touched. A `FAIL` says what it expected, what it got, and a hint. A `SKIP` means something it needs failed first; fix the first `FAIL`.

## Each step ends the same way

1. **The step's check passes,** and the guide shows exactly what passing looks like.
2. **Your journal** (`JOURNAL.md`) has the step's entries: your decisions, and your answers to your tutor's questions.
3. **Your predictions** (`PREDICTIONS.md`) each have what happened.
4. **A commit,** and the guide says which files `git status` should and shouldn't list.

At the end of each milestone, you also ask a reviewer agent to look at your changes (`reviewer/REVIEWER.md`), and you fix or answer each thing it finds.

## If you're stuck

1. Read the step's idea again, then its library example, and compare the shape with yours.
2. Run the step's check, and read its hint.
3. Ask your tutor, or a coding agent, to *explain*. They won't write it for you.
4. Still stuck after about 20 minutes: send Dominik the command you ran and its whole output.

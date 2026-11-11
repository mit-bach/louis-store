# Step M6-5 · The control: no spec

**Why:** you spent a step writing a spec. Was it worth it? The control answers that the way every control in this course has: the same thing, with the safeguard taken away. Here that's the same request to the same agent, with no spec, judged on the same walkthrough.

## A second folder, without the spec

Your spec-built frontend is committed on your branch `frontend`, and your repository folder stays on it. The control gets a folder of its own: a **worktree**, a second checkout of the same repository, on its own branch, beside the first. Nothing you do in one changes the files of the other, which is why people give separate agents separate worktrees. Make one from `main`, which doesn't have the frontend yet, and take the spec out of it:

```
git worktree add ../store-nospec -b frontend-nospec main
cd ../store-nospec
git rm FRONTEND-SPEC.md
git commit -m "No spec, for the control"
```

## The same request

**Predict,** under `## M6-5` in `PREDICTIONS.md` back in your repository folder: with no spec, what will your agent decide differently? Will the walkthrough pass?

Stop your step 4 `pnpm dev`, with Ctrl+C, so port 3000 is free. Then, in `../store-nospec`, start Claude Code. It's a new folder, so accept the trust question. Switch to plan mode with Shift+Tab, and ask the same thing, without the spec:

```
Build a frontend for my store, in a new folder, frontend/.
```

Read the plan as you did in step 3. This time, note each thing it decides that your spec had decided for you. Approve it, and let it build. Then run it the way it tells you to, and do the four checks of step 4, in a normal and a private window. Your store is the same one, still running from your repository folder.

<details><summary>What happened when this was tested (open it after your own run)</summary>

Tested on 2026-11-11 with Claude Code 2.1.319 and Opus 5.5, on a branch with no `FRONTEND-SPEC.md`: the same request, a plan in plan mode, then the build.

- **It works.** The same four walkthrough checks, in a headless browser, all passed: two windows, two carts; the last unit, one order and one "Only 0 of … left in stock."; the new price with the old order alone; and recovery from an expired session.
- **But it decided the big things itself,** and two of three went against this store:
  - **The stack:** plain HTML, CSS and JavaScript, served by `python3 -m http.server`. No Next.js, no Tailwind, no shadcn, no pnpm. So there's no `package.json`, and `pnpm lint` and `pnpm build` can't even run.
  - **The scope:** an **admin page**, linked from the shop's own menu, that creates, edits and archives products. Your API has no admin sign-in, so anyone who opened the shop could change every price.
  - **The token:** `sessionStorage`, so each tab is its own customer. That passes "two windows, two carts", and empties the cart whenever a customer opens a second tab.
- **To learn what you wanted, it read your repository.** It found "two browser windows racing for the last unit" in `BRIEF.md`, and built for that demo. It didn't open the deleted spec from git's history, on purpose.
- **It cost more:** $1.09 for the plan and $4.02 for 35 minutes of building, against $1.23 and $3.34 with the spec.

A good agent without a spec doesn't build nothing. It builds something plausible, with your decisions made for you. The walkthrough checks behaviour, and the spec also decided the things the walkthrough never looks at.
</details>

Write under `## M6 control` in `JOURNAL.md`, in your repository folder: what the spec-less plan decided, how it did on each of the four checks, and what your spec decided that the walkthrough doesn't check.

## Keep the spec's version

The control has done its job. Stop its server, go back to your repository folder, throw the control away, and put your spec-built frontend on `main`:

```
cd ../store
git worktree remove --force ../store-nospec
git branch -D frontend-nospec
git add -A
git commit -m "M6-5: the control"
git switch main
git merge frontend
```

`git merge frontend` brings your work from steps 3 to 5 onto `main`.

## Check

The whole milestone, on `main`:

```
make check M=6
```

**You should see** every M0 to M5 check pass, then:

```
M6 · The frontend, built by your agent
  PASS  M6-1  list_orders(): the session's own orders, newest first, each at the prices paid
  PASS  M6-1  GET /orders, ./store orders and the list_orders tool: the same list, and a 401, exit 5 or an error without a session
  PASS  M6-1  parity: list_orders has its route, its command and its tool
  PASS  M6-1  CORS: a page from http://localhost:3000 may call the API, and a page from anywhere else may not
  PASS  M6-2  FRONTEND-SPEC.md: its pages and endpoints, where the token lives, the 401, 409 and 422, the key, and the walkthrough
  PASS  M6-3  AGENTS.md says what your coding agent builds: the frontend, from your spec
  PASS  M6-3  frontend/: Next.js, Tailwind and shadcn/ui, with pnpm
  PASS  M6-3  pnpm lint passes in frontend/
  PASS  M6-3  pnpm build passes in frontend/
  PASS  M6-4  your journal has the walkthrough: what each of the four checks showed, and what you changed
  PASS  M6-5  your journal has the control: how the spec-less frontend did on the same walkthrough

123 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

## Step done

```
git status --short
```

```

```

`git status` lists nothing: the merge brought everything committed.

```
git push
git push origin frontend
```

That's M6, and the store. Go through "M6 is done when" in [`README.md`](README.md), including the review by your `store-reviewer` skill. Then [`BRIEF.md`](../../BRIEF.md), "What finished means", says what's left: `make check-all` from a fresh clone, and your demo.

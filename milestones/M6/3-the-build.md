# Step M6-3 · The build, planned first

**Why:** this is the first time in the course that your coding agent writes code for you. Two habits make that safe:
- **A branch:** everything it does lands on a branch you can throw away.
- **A plan you read first:** in **plan mode**, Claude Code can read and think but not change anything. It writes a plan, and builds only once you approve it. Reading a plan takes five minutes. Unpicking a build that went the wrong way takes an afternoon.

## 1. Node and pnpm

Next.js runs on Node.js, and the spec says pnpm. Install both with Homebrew:

```
brew install node pnpm
node --version
pnpm --version
```

Next.js 16 needs Node 20.9 or newer. This course was tested with Node 23.7 and pnpm 11.1.

## 2. Your rules, for a new kind of job

Your `AGENTS.md` says what your coding agent may not do: write your backend. Now it has a job to do, and it should hear that from you. Add a section to `AGENTS.md`, in your own words. Say what it builds (`frontend/`, from `FRONTEND-SPEC.md`), what it asks you before deciding (anything the spec doesn't say), and that `backend/` stays yours. Your M2 hook still walls off `backend/` whatever the rules say.

## 3. A branch, and the plan

```
git switch -c frontend
claude
```

In Claude Code, press **Shift+Tab** until the line under the prompt box says **plan mode on**. Then ask:

```
Build the frontend that FRONTEND-SPEC.md describes, in a new folder, frontend/.
```

**Predict,** under `## M6-3` in `PREDICTIONS.md`: what will the plan get wrong, or leave out?

**Read the plan against your spec,** not against your hopes. For each one, find where the plan says it:
1. It makes the app and adds shadcn with the spec's exact commands.
2. It keeps the token where your spec says, and sends it the way your spec says.
3. Its answer to a `401`: a new session, the same request once more, and no error page.
4. A new `Idempotency-Key` for each checkout click, and the same key on a retry.
5. Each page, calling the endpoint your spec gives it.
6. Nothing outside `frontend/`.

If any of these is wrong or missing, tell the agent, still in plan mode, and let it revise. If it asks you something your spec doesn't answer, that's a gap in your spec: answer it, and add the answer to `FRONTEND-SPEC.md` too. When the plan is right, approve it, and let it accept its own file edits. It still asks before each command it runs. Read each one before you allow it: `pnpm` and `pnpm dlx` are expected, anything that touches `backend/` or the database isn't.

<details><summary>What happened when this was tested (open it after your own plan)</summary>

Tested on 2026-11-11 with Claude Code 2.1.319 and Opus 5.5: the plan in plan mode, then the build from that plan, with the course's own spec.

- **The plan took under three minutes.** Claude Code priced it at $1.23. Before planning, the agent checked that the API was running, and that its CORS allowed the headers the pages would send. The plan used the spec's exact commands and chose five shadcn components (button, card, badge, alert and table). It put every call to the API in one file, `src/lib/api.ts`, and listed the choices the spec had left open.
- **It found a gap in the spec.** "Lower the quantity by one" sends 0 from a quantity of 1, and the API refuses 0 with a `422`. The spec didn't say what `−` does at 1. A better spec says: at 1, it removes the line.
- **It found a limit in the backend, and asked instead of changing it.** When the API answers `500`, a browser can't read the answer, because the error handler runs outside the CORS layer. So a page shows "The store isn't answering" where it could show the contract's message.
- **The build took 34 minutes, 65 turns and $3.34.** `pnpm lint` and `pnpm build` passed the first time, and nothing outside `frontend/` changed. `create-next-app` also added `frontend/AGENTS.md`, Next.js's own notes for coding agents.
</details>

## 4. Check the build

When the agent says it's done:

```
cd frontend
pnpm lint
pnpm build
cd ..
```

**You should see** `pnpm lint` print nothing after its first line, and `pnpm build` end with its list of pages:

```
Route (app)
┌ ○ /
├ ○ /_not-found
├ ○ /cart
└ ○ /orders


○  (Static)  prerendered as static content
```

Your pages may differ from mine, but `/`, `/cart` and `/orders` should be there.

```
make check M=6 STEP=3
```

**You should see** everything before, then:

```
  PASS  M6-3  pnpm build passes in frontend/

121 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

The check installs the frontend's packages with `pnpm install --frozen-lockfile`, then runs `pnpm lint` and `pnpm build` itself.

## Step done

On your branch:

```
git status --short
```

```
 M AGENTS.md
 M JOURNAL.md
 M PREDICTIONS.md
?? frontend/
```

`frontend/.gitignore`, which `create-next-app` made, keeps `node_modules/` and `.next/` out of git.

```
git add -A
git commit -m "M6-3: the frontend, built from my spec"
git push -u origin frontend
```

Answer your tutor's questions under `## M6-3` in `JOURNAL.md`.

# M0 · Setup, and an agent that follows your rules

**About half a day.**

## What works at the end

Your store's API and its own Postgres database run in Docker on your Mac. This command:

```
curl http://localhost:8000/health
```

answers:

```
{"status":"ok","database":"ok"}
```

Your repository is on GitHub, and your coding agent follows a rules file you wrote. When you ask it to write your backend code, it says no, and offers to explain instead.

## Who writes what

- **Given, and you type it in:** `docker-compose.yaml`, `backend/Dockerfile`, `backend/requirements.txt`, `backend/db.py`, `backend/main.py` and `CLAUDE.md`. Each line is explained.
- **Yours:**
  - `.env`, with your own password;
  - `AGENTS.md`, your agent's rules, in your own words;
  - your entries in `JOURNAL.md` and `PREDICTIONS.md`.
- **No backend code of yours yet.** That starts in M1.

## The steps

1. [Your tools, and your own copy of the kit](1-tools-and-your-repo.md)
2. [The store's stack: an API and its database, in Docker](2-the-stack.md)
3. [Your rules file, and the first control experiment](3-your-rules-file.md)

## M0 is done when

1. `make check M=0` passes. The end of step 3 shows exactly what that looks like.
2. **The manual check** in step 2 worked: with the database stopped, `/health` answered `503`, and it answered `200` again once the database was back.
3. **`JOURNAL.md`** has both of step 3's agent exchanges, and your answers to your tutor's questions for each step.
4. **`PREDICTIONS.md`** has M0's predictions, each with what happened.
5. **It's committed and pushed,** and `git status` says `nothing to commit, working tree clean`.

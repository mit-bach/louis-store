# The store kit

Louis's first course: the backend of a small online store, written by hand, and built agent-first. Every operation is reachable over HTTP, from the command line and as an agent tool. This repository holds the course, not the code: the brief, the contract, the step-by-step guides and the checks. The backend is yours to write.

**Start here:** [`BRIEF.md`](BRIEF.md), then [`milestones/M0/README.md`](milestones/M0/README.md).

## What's in it

```
BRIEF.md            what you build, the rules, and what "finished" means
CONTRACT.md         exactly what every route, command and tool must do; the checks test it
milestones/         the guides: one folder per milestone, one file per step
checks/             the checks, run with `make check M=<n>`; each run saves checks/last-run.txt
Makefile            the everyday commands: make up, make logs, make psql, make reset, make check, make update
templates/          AGENTS.md, the starting point for your agent's rules file
reviewer/           the prompt you give an agent to review your changes
JOURNAL.md          your decisions, the review's findings, and your answers to your tutor's questions
PREDICTIONS.md      your guesses before each experiment, and what happened
course/COURSE.md    the course's text for your tutor harness
CHANGES.md          what each version of the kit added
.claude/            your coding agent's settings for this repository; empty for now
```

You create `backend/`, `docker-compose.yaml`, `.env`, `AGENTS.md`, `CLAUDE.md` and `./store` yourself, as the guides go.

## Where it lives, and how updates reach you

It lives at `~/code/store` on your Mac. In M0 you make your own copy of it on GitHub, so this repository becomes the remote called `kit`, and yours becomes `origin`. New milestones and fixes to the guides arrive here, and you take them with:

```
make update
```

That runs `git pull --no-rebase --no-edit kit main`: fetch the kit's new commits and merge them into yours. Plain `git pull kit main` refuses, once you have commits of your own, until git is told how to combine the two histories; `--no-rebase` says "merge them", and `--no-edit` accepts git's merge message.

The kit only ever changes its own files: the guides, the checks, the contract and the other files listed above. Your `backend/`, your journal and your predictions are never touched by an update.

## For the agent setting it up

If Louis's setup prompt sent you here:
1. If `~/code/store` doesn't exist, clone this repository there: `git clone https://github.com/mit-bach/louis-store ~/code/store`. If it exists and is this repository, leave it as it is: he takes the kit's updates himself, with `make update`. If it's something else, stop and ask him.
2. Don't install anything, and don't change its remotes. M0's first step does that with him, one tool at a time.
3. Tell him the store is at `~/code/store`, and that his tutor serves it as course 01. He opens "Tutor Orch" in Berth and asks it to start course 01 from `~/code/store/course/COURSE.md`.

## Repositories this uses

- **This one,** [`mit-bach/louis-store`](https://github.com/mit-bach/louis-store): the kit.
- **[`mit-bach/louis-agentic-engineering`](https://github.com/mit-bach/louis-agentic-engineering):** Louis's roadmap and setup. Its setup prompt clones this kit.
- **[`mit-bach/louis-tutor`](https://github.com/mit-bach/louis-tutor):** the tutor harness that serves these guides as lessons.

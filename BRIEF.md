# The brief

## What you build

The backend of a small online store:
- a catalogue of products;
- a cart for each visitor;
- a checkout that never sells something that isn't there.

The hard part is the classic one. When two customers try to buy the last unit at the same moment, exactly one gets it. The other gets a clean "out of stock", never a crash, and the store never ends up with negative stock.

The store is **agent-first.** Everything a person can do in it, an AI agent can do too, under exactly the same rules. So every operation you write is reachable three ways, all calling the same function:
1. over **HTTP**, which web pages and other programs use;
2. from **the command line**, as `./store …`, which you, scripts and agents in a terminal use;
3. as **agent tools**, over MCP, which an agent connected to the store uses.

Agents are good at terminals, so the command line is as much a way in for them as the tools are. You'll build both, and watch your agent choose between them.

## The rules

1. **You write the backend by hand, and can explain every line.** Dominik's rule: "you can't have the AI just write all the files."
   - Your agents, your tutor included, may explain, answer questions, review your changes and name the problems, and quiz you.
   - They may not write or edit your backend code.
   - Configuration and glue (the Dockerfile, the compose file, the database connection, the skeletons of the command line and the tool server) are given exactly in the guides. You type them in, and each line is explained.
2. **The contract is fixed. How you meet it is yours.** [`CONTRACT.md`](CONTRACT.md) says exactly what every route, command and tool does. Your design choices live inside it.
3. **Rules live in the operations and the database,** never only in one way in, so every caller passes them, agents included.
4. **Errors are written for whoever reads them next,** which is often a model deciding what to do.
5. **Predict before you run.** Before every experiment, you write a one-line guess in `PREDICTIONS.md`. Afterwards you write what happened. That's how you'll build intuition for databases, agents and harnesses.

## The milestones

Each milestone is a folder of step files in [`milestones/`](milestones/README.md), one build step each, and each step ends with a check you run yourself.
- **M0 · Setup, and an agent that follows your rules** (half a day). Ready now.
- **M1 · Products, and the store's first tools** (about two days). Ready now.
- **M2 · The admin side, and your first race** (about two days). Ready now.
- **M3 · Visitors and carts** (about two days). Ready now.
- **M4 · Checkout, and two buyers at once** (about two days). Ready now.
- **M5 · Agent-first, for real: retries, errors, scope and evals** (about two days). Ready now.
- **M6 · The frontend, built by your agent** (1 day).

M6 arrives in this repository when it's finished and tested. You get it with `make update`.

## What "finished" means

- From a fresh clone of your repository, `make check-all` passes.
- A 15-minute demo to Dominik:
  - the race, live, with your lock removed and put back;
  - an agent placing an order;
  - your agent's eval scores;
  - two browser windows racing for the last unit;
  - three questions about your code, answered without notes.

## What you need

- A Mac, with Claude Code running inside cmux. Your setup prompt installed both.
- Docker Desktop, uv and the GitHub CLI (`gh`). M0's first step installs each one.
- About 12 working days.

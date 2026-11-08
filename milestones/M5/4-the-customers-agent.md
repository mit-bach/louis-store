# Step M5-4 · The customer's agent

**Why:** in M4-5 testing, two agents that lost the race for the last lantern explained it to their customers by reading the `orders` table with `psql`, and saw another customer's purchase. Nobody asked them to. Nothing stopped them either: they had the same access to your Mac as you do. Your store's rules protect it from a bad request. What an agent can reach is decided somewhere else: in its harness. This step builds a harness for one agent, the customer's, in a folder of its own.

## Decide first: should an agent ask before it checks out?

On a web page, the customer clicks "Buy". That click is their agreement to this cart, at these prices. An agent has no click. The facts:
- This project's rule is "anything a human can do, an AI can also do". Your operations already enforce every rule, whoever calls them.
- A customer often sends an agent on an errand ("buy me a Storm Lantern") and isn't there when it runs.
- A permission in Claude Code is per tool, not per purchase. If `checkout` needs approval, every checkout waits for a person, and with nobody there, it's refused.
- The store can't see whether an agent asked. It sees a request.

Three options:
- **(a)** The store adds a confirmation step: checkout returns a quote, and a second call confirms it.
- **(b)** The agent's harness makes every `checkout` wait for the customer's approval.
- **(c)** A specific request is the customer's agreement. The agent asks only when it would decide something the customer didn't: a different product, a different quantity, or a total they didn't expect. With nobody to ask, it stops and reports.

**Write (a), (b) or (c), and why, under `## M5-4` in `JOURNAL.md`, before you open the answer.**

<details><summary>Check your choice</summary>

(c). "Buy me a Storm Lantern" is an agreement to buy a Storm Lantern at the store's price. An agent that does exactly that hasn't decided anything for its customer. An agent that buys a different lantern, or three, has, and that's where it must ask. (a) adds a call, not consent: an agent would call "confirm" straight after "quote". (b) turns every errand into a click, and fails every errand run while the customer is away. Step 5 shows what (b) does to a headless run. Your store's part is to make (c) safe: refusals change nothing, a retry buys once, and the order says exactly what was bought, at what price. The agent's part is in its brief, which you write below.
</details>

## Decide first: what exactly does a customer's agent get?

Three options:
- **(a)** Everything you have: the shell, your files, every tool. That's what M4-5's agents had.
- **(b)** All of the store's tools, and nothing else.
- **(c)** The store's customer tools only: the catalogue, a session, a cart, checkout. No shell, no web, no admin tools, and none of your developer rules.

The facts:
- The admin tools change prices and stock for everyone.
- `psql` reaches every table, every customer's included. The shell reaches `psql`, your `.env` and its database password, and anything else on your Mac.
- Claude Code loads every `CLAUDE.md` from the folder a session starts in, up to your home folder. A session started in `agents/customer` would load your repository's `CLAUDE.md`, and your `AGENTS.md` with it: rules about building the store, written for your coding agent.

**Write (a), (b) or (c), and why, under `## M5-4`, before you open the answer.**

<details><summary>Check your choice</summary>

(c). A customer's agent should be able to do what a customer can do on the website, and nothing more. The customer tools are `list_products`, `get_product`, `start_session`, `get_cart`, `set_cart_item`, `remove_cart_item` and `checkout`. Everything else is denied, not just left out, so that a later setting can't let it back in. Your developer rules aren't for this agent. They'd tell it about migrations and your backend, which is exactly what it shouldn't think about.
</details>

## The idea: a folder that is an agent

When a Claude Code session starts in a folder, it reads three things from it:
- **`.claude/settings.json`,** whose `permissions` say which tools the session may use: `allow` (no questions), `ask` (a person approves each call) and `deny` (never).
- **`.mcp.json`,** the tool servers this folder adds. `"enabledMcpjsonServers": ["store"]` in the settings approves one, so the session doesn't ask about it.
- **`CLAUDE.md`,** the agent's brief, and every `CLAUDE.md` above it, unless `"claudeMdExcludes"` names it. A pattern like `**/store/CLAUDE.md` matches a `CLAUDE.md` directly inside a folder called `store`.

A permission rule names a tool. `Bash` is the shell, `WebFetch` and `WebSearch` the web, and `mcp__store__checkout` is the tool `checkout` from the server called `store`: `mcp`, the server's name, the tool's name, joined by double underscores. Three facts about rules, tested on Claude Code 2.1.319:
- **A deny wins over everything.** `"Bash"` alone in `deny` removes the shell from the session completely. The agent doesn't see a shell it can't use. It has none.
- **In a headless run** (`claude -p`, step 6), there's no one to answer a question. Anything not allowed is refused, and anything in `ask` too, even when the command line itself allows it.
- **`allow` only counts in a folder you trust.** The first time you ran `claude` in your repository, in M0, you accepted its trust question. Until a folder is trusted, its allow rules are ignored. `agents/customer` is inside your repository, so it's covered.

**An example on a different problem,** the library. A patron's agent, which may borrow but not withdraw books:

```json
{
  "permissions": {
    "allow": [
      "mcp__library__issue_card",
      "mcp__library__get_basket",
      "mcp__library__set_basket_item",
      "mcp__library__borrow"
    ],
    "deny": [
      "Bash",
      "WebFetch",
      "WebSearch",
      "mcp__library__withdraw_book",
      "mcp__library__update_book",
      "mcp__library__change_copies"
    ]
  },
  "enabledMcpjsonServers": ["library"],
  "claudeMdExcludes": ["**/library/CLAUDE.md"]
}
```

## You write

All three in a new folder, `agents/customer/`, as [`CONTRACT.md`](../../CONTRACT.md), "M5 · The customer's agent", describes.
- **`CLAUDE.md`:** the agent's brief, in your own words, 60 words or more. Who it shops for. When it buys and when it asks, from your first decision. That it gives every checkout a key, and retries with the same one. What it may look at, and what it never looks for.
- **`.mcp.json`:** one server, `store`, at `http://localhost:8000/mcp`.
- **`.claude/settings.json`:** your second decision, as `allow` and `deny`, plus `enabledMcpjsonServers` and `claudeMdExcludes`.

## Check

**What the agent has.** A headless run from its folder. `--setting-sources project,local` leaves out your own user settings, so you see only what the folder gives it, and `--model haiku` keeps it cheap. Copy the whole block:

```
cd agents/customer
claude -p "List the tools you have, by name, one per line. Nothing else." --model haiku --setting-sources project,local
cd ../..
```

<details><summary>What mine listed</summary>

Its store tools came first:

```
mcp__store__checkout
mcp__store__get_cart
mcp__store__get_product
mcp__store__list_products
mcp__store__remove_cart_item
mcp__store__set_cart_item
mcp__store__start_session
```

Then 27 of Claude Code's own tools, such as `Read`, `Glob`, `Grep`, `Edit` and `Write`. Which of those you see depends on your version of Claude Code.
</details>

There's no `Bash`, no `WebFetch` and no admin tool: a denied tool isn't in the list at all. Claude Code's own file tools are still there. In a headless run they can read only inside `agents/customer`, and anything that would change a file is refused, because nothing allows it.

**Which rules files it loaded.** Your harness's `tx.py` shows them as `RULES` lines. It needs louis-tutor 1.0.4 or newer: if you haven't updated your harness since M4, ask Tutor Orch to (`git -C ~/tutor pull`). Then, on the run you just made:

```
python3 ~/tutor/orchestrator/tools/tx.py $(ls -t ~/.claude/projects/*store-agents-customer/*.jsonl | head -1) | grep RULES
```

**You should see** one line, ending with your agent's own `CLAUDE.md`:

```
2026-11-08T21:24:15 RULES   /Users/you/code/store/agents/customer/CLAUDE.md
```

```
make check M=5 STEP=4
```

**You should see** everything before, then:

```
  PASS  M5-4  the customer agent doesn't load your developer rules: the top CLAUDE.md is excluded, its own isn't

111 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

## Step done

```
git status --short
```

```
 M JOURNAL.md
 M PREDICTIONS.md
?? agents/
```

```
git add -A
git commit -m "M5-4: the customer's agent"
git push
```

Answer your tutor's questions under `## M5-4` in `JOURNAL.md`.

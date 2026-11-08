# Your coding agent's settings, for this repository

Claude Code reads `.claude/settings.json`, and the skills in `.claude/skills/`, from the folder a session starts in. This folder is empty for now, on purpose. You fill it as the course goes:
- **M2:** a hook that refuses your coding agent's edits to your backend files. It turns the rule in your `AGENTS.md` into a wall.
- **M3:** nothing here: your reviewer becomes a skill in your tutor harness, `~/tutor/.claude/skills/`, where your tutors find it.
- **M5:** nothing here either: the customer's agent gets a folder of its own, `agents/customer/`, with its own settings. They say which tools it may call, and which it never may. Its headless runs are the evals.

Each change comes with a control experiment, like the one in M0-3: with it, and without it, with a prediction first.

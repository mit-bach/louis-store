# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx==0.28.1", "mcp==2.3.0"]
# ///
"""The store's checks. Run them with `make check M=<milestone> [STEP=<step>]`, or an optional spec's with `make spec S=<number>`.

Each run starts a second, throwaway copy of your store (its own containers, its own empty
database, on port 8001), applies your migrations and your seed to it, runs the checks against
it, saves what it printed to checks/last-run.txt, and removes the copy again. Your own store,
and the data in it, are never touched.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kitlib import CHECKS, LAST_RUN, MILESTONES, SPECS, Ctx, Fail, git, short  # noqa: E402

def run_checks(target_m: int, target_step: int | None, ctx: Ctx) -> tuple[int, int, int, list[str]]:
    import m0  # noqa: F401  (registers the checks)
    import m1  # noqa: F401
    import m2  # noqa: F401
    import m3  # noqa: F401
    import m4  # noqa: F401
    import m5  # noqa: F401
    import m6  # noqa: F401
    import s14  # noqa: F401  (optional specs: never chosen for a milestone, only by make spec)
    import s15  # noqa: F401

    if target_m in SPECS:
        chosen = [c for c in CHECKS if c.milestone == target_m]
    else:
        chosen = [
            c for c in CHECKS
            if c.milestone < target_m or (c.milestone == target_m and (target_step is None or c.step <= target_step))
        ]
    out: list[str] = []
    passed = failed = skipped = 0
    current = None
    for c in chosen:
        if c.milestone != current:
            current = c.milestone
            line = (f"\nOptional spec {c.milestone} · {SPECS[c.milestone]}" if c.milestone in SPECS
                    else f"\nM{c.milestone} · {MILESTONES[c.milestone]}")
            print(line, flush=True)
            out.append(line)
        label = f"{'S' if c.milestone in SPECS else 'M'}{c.milestone}-{c.step}"
        missing = [n for n in c.needs if n not in ctx.proven]
        if missing:
            line = f"  SKIP  {label}  {c.title}  (needs: {', '.join(missing)})"
            skipped += 1
            print(line, flush=True)
            out.append(line)
            continue
        try:
            c.fn(ctx)
        except Fail as f:
            failed += 1
            lines = [f"  FAIL  {label}  {c.title}", f"        expected: {f.expected}", f"        got:      {f.got}"]
            if f.hint:
                lines += ["        " + h for h in f"hint: {f.hint}".splitlines()]
        except Exception as e:  # a bug in a check, or something nobody foresaw
            failed += 1
            lines = [f"  FAIL  {label}  {c.title}", f"        the check itself hit {type(e).__name__}: {short(str(e))}",
                     "        hint: paste this output to Dominik."]
        else:
            passed += 1
            if c.gives:
                ctx.proven.add(c.gives)
            lines = [f"  PASS  {label}  {c.title}"]
        for line in lines:
            print(line, flush=True)
        out.extend(lines)
    return passed, failed, skipped, out


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the store's checks.")
    parser.add_argument("milestone", help="the milestone number, 'all', or s<number> for an optional spec")
    parser.add_argument("step", nargs="?", type=int, help="stop after this step of the milestone")
    parser.add_argument("--keep", action="store_true", help="leave the throwaway store running afterwards")
    a = parser.parse_args()
    if a.milestone.startswith("s"):
        target_m = int(a.milestone[1:])
        if target_m not in SPECS:
            print(f"There's no optional spec {target_m} with checks. The kit has checks for these optional specs: {', '.join(map(str, SPECS))}.")
            return 2
    else:
        target_m = max(MILESTONES) if a.milestone == "all" else int(a.milestone)
    if target_m not in MILESTONES and target_m not in SPECS:
        print(f"There's no milestone {target_m} yet. The kit has milestones {min(MILESTONES)} to {max(MILESTONES)}.")
        return 2
    ctx = Ctx(
        project=os.environ.get("CHECK_PROJECT", "store-check"),
        port=int(os.environ.get("CHECK_PORT", "8001")),
        keep=a.keep,
    )
    started_at = datetime.now().astimezone()
    scope = f"optional spec {target_m}" if target_m in SPECS else f"M{target_m}" + (f" up to step {a.step}" if a.step else "")
    head = f"Store checks · {scope} · {started_at:%Y-%m-%d %H:%M %Z}"
    print(head, flush=True)
    try:
        passed, failed, skipped, out = run_checks(target_m, a.step, ctx)
    finally:
        ctx.stop()
    summary = f"\n{passed} passed, {failed} failed, {skipped} skipped."
    print(summary)
    commit = git("rev-parse", "--short", "HEAD").stdout.strip() or "none"
    dirty = [l for l in git("status", "--porcelain").stdout.splitlines() if l.strip()]
    record = [head, f"Commit: {commit}, with {len(dirty)} uncommitted change(s).", *out, summary]
    LAST_RUN.write_text("\n".join(record) + "\n")
    print(f"Saved to checks/last-run.txt")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

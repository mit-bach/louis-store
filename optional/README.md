# Optional specs

The course is M0 to M6. Optional specs are extra pieces of work, each on its own, for after the course or alongside it. You pick any, in any order. The whole list is in your package, in [`OPTIONAL-SPECS.md`](https://github.com/mit-bach/louis-agentic-engineering/blob/main/OPTIONAL-SPECS.md).

Most of them are yours to design: the list says what, and you decide how. Some come with a guide and checks in this kit, like a milestone's step:

| Spec | Guide | Do it after |
|---|---|---|
| 14 · Your own migration runner | [14-your-own-migration-runner.md](14-your-own-migration-runner.md) | M2, when `make migrate` arrives |

Check one with:

```
make spec S=14
```

A spec's checks run on the same throwaway copy of your store as `make check`, and save to `checks/last-run.txt` the same way. They're never part of `make check-all`: the course is finished without them. Doing a spec doesn't change what any milestone's checks expect, so `make check M=6` passes before and after.

Tell your tutor which spec you're starting, so it can serve the guide the way it serves a step.

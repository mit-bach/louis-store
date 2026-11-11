# M6 · The frontend, built by your agent

**About two days.** Until now, you wrote every line of the store, and your agents only used it. Now your coding agent builds something for you: the store's web pages. Your part is the part that decides whether that goes well. You say exactly what to build, read its plan before it builds, and check the result against what you said.

## What works at the end

- **Your orders,** through every way in: `GET /orders`, `./store orders` and the `list_orders` tool.
- **Your API lets your own pages call it from a browser,** and nobody else's.
- **`FRONTEND-SPEC.md`:** your spec, in your words.
- **`frontend/`:** the store's web pages, built by your agent from the spec. Next.js, Tailwind and shadcn/ui, with pnpm. `pnpm lint` and `pnpm build` pass.
- **A walkthrough you've done by hand:**
  - two windows, two separate carts;
  - the last unit, bought from both at once;
  - a price change that leaves an old order alone;
  - an expired session the pages recover from by themselves.
- **The control:** the same request, with no spec, and how it did on the same walkthrough.

## Who writes what

- **Yours, by hand:**
  - `list_orders`, through the three ways in;
  - the spec, after deciding where the token lives;
  - your rules for the agent;
  - one change to the agent's code, with your reason.
- **Your coding agent's:** everything in `frontend/`, after you've read and approved its plan.
- **Given:** the CORS middleware, and the exact commands that make the app.

## The steps

1. [Your orders, and the door for the browser](1-your-orders.md)
2. [The spec](2-the-spec.md)
3. [The build, planned first](3-the-build.md)
4. [The walkthrough](4-the-walkthrough.md)
5. [The control: no spec](5-the-control.md)

## M6 is done when

1. **`make check M=6` passes** on `main`, with the frontend merged. The end of step 5 shows exactly what that looks like.
2. **The walkthrough:** all four checks show what your spec says, and `JOURNAL.md` has what each showed, under `## M6 walkthrough`.
3. **In `JOURNAL.md`:** where the token is stored and sent, one thing you changed in your agent's code and why, and how the spec-less version did, under `## M6 control`.
4. **The review:** your `store-reviewer` skill has reviewed M6, and each finding is in `JOURNAL.md` under `## M6 review`, fixed or answered.
5. **It's committed and pushed.**

Then the course is done: [`BRIEF.md`](../../BRIEF.md), "What finished means", says what's left.

# Step M6-2 · The spec

**Why:** in step 3 your coding agent builds the frontend. It will build what you describe. Everything you leave out, it decides for you, and you find out which way when you read its code, or when a customer does. A **spec** is how you decide first: a document that says what to build, precisely enough that two different builders would build the same thing. Writing one is the skill. The agent's speed is only worth something when what it builds is what you meant.

## Decide first: where does the session token live?

The pages run in the customer's browser. They need the session token for every cart and checkout request. Four places it could live:
- **(a) A variable in the page's code:** gone on every reload.
- **(b) `sessionStorage`:** one for each browser tab. It survives a reload, and a new tab starts without it.
- **(c) `localStorage`:** one for the whole browser, shared by all its tabs, and kept after the browser closes.
- **(d) A cookie,** which the browser sends to your API by itself.

The facts:
- A customer expects their cart to still be there when they open a second tab, or come back tomorrow.
- Your API reads the token from the `Authorization` header, not from a cookie. A cookie would mean changing your backend.
- Anything in `sessionStorage` or `localStorage` can be read by any script that runs on the page. A cookie marked `httpOnly` can't be read by scripts at all.
- Your sessions expire after an hour, and step 3's spec makes the pages recover from that by themselves.

**Write (a), (b), (c) or (d), and why, under `## M6-2` in `JOURNAL.md`, before you open the answer.**

<details><summary>Check your choice</summary>

(c), `localStorage`, for this store. The cart follows the customer across tabs and reloads, and nothing in your backend changes. The cost is the third fact: if anyone ever got a script onto your pages, it could read the token. That attack is called **cross-site scripting**. Your tokens expire after an hour, and they guard a cart, not a bank account, so it's a fair trade here. A store with accounts and payments would keep its token in an `httpOnly` cookie instead. Write that trade into your spec, so it's a decision, not an accident.

One thing follows for the walkthrough. A private window has storage of its own, apart from your normal windows. (In Chrome, all private windows share one.) So "two customers" means one normal window and one private window.
</details>

## What a spec says

Yours is the contract between you and your agent. It says, as [`CONTRACT.md`](../../CONTRACT.md), "M6 · The spec", lists:
- **The stack, with exact commands.** These are given, so that your build matches the one this course was tested with:
  - make the app with `pnpm create next-app@16.4.3 frontend --ts --tailwind --eslint --app --src-dir --import-alias "@/*" --use-pnpm --disable-git --no-agent-feedback --yes`;
  - add shadcn/ui, a set of ready-made components, with `pnpm dlx shadcn@4.23.0 init`;
  - the pages call your API from the browser, at `http://localhost:8000`;
  - `pnpm lint` and `pnpm build` must pass.
- **Where the token lives, and how it's sent:** your decision above.
- **Each page, and the endpoint it calls:** the catalogue, the cart, checking out, and your orders. Say what each page shows, and what each button sends. Your API's rules are in `CONTRACT.md`. Say how "Add to cart" turns your `set_cart_item`, which *sets* a quantity, into adding one.
- **What a page shows for a `401`, a `409` and a `422`.** A `409`'s message is already written for a person, so show it as it is. A `401` means the session expired: say how the page recovers without an error page.
- **How checkout uses an `Idempotency-Key`:** a new key for each click, and the same key if that request is retried. A double-click is a retry, and M5 made that safe.
- **The walkthrough:** the four checks in step 4, each with what it should show. Writing them down now tells your agent what "done" means.
- **What's not in it:** no admin pages, no sign-in, no payment.

**An example on a different problem,** the library's spec:

```markdown
# Frontend spec: the library

What my coding agent builds in `frontend/`. Don't edit anything outside it.

## Stack

Next.js with the App Router, TypeScript, Tailwind CSS and shadcn/ui, with pnpm, made with `pnpm create next-app@16.4.3 frontend --ts --tailwind --eslint --app --src-dir --import-alias "@/*" --use-pnpm --disable-git --no-agent-feedback --yes`, then `pnpm dlx shadcn@4.23.0 init`. The pages call the API from the browser, at `NEXT_PUBLIC_API_URL`, default `http://localhost:8000`.

## The library card

- A visitor's card token lives in `localStorage`, under `library.card`.
- The first time a page needs a card, it calls `POST /cards` and stores the token.
- Basket, borrow and loans requests send `Authorization: Bearer <token>`.
- On a `401`, get a new card, store it, send the request once more, and show: "Your card expired, so you have a new one, with an empty basket."

## Pages

1. **`/`, the shelf.** `GET /books`. A card per book: title, author, copies on the shelf. "Add to basket" sets the basket's copies of that book to one more than it holds (`PUT /basket/items/{book_id}`).
2. **`/basket`.** `GET /basket`. One row per book, with its copies, and "Borrow".
3. **Borrowing.** `POST /borrow`, with an `Idempotency-Key` from `crypto.randomUUID()`, new for each click and the same for a retry. On `201`, go to `/loans?made=<id>`.
4. **`/loans`.** `GET /loans`, newest first. With `?made=<id>`, show "Loan #<id> made."

## Errors

- **`409`:** the API's `detail`, as it is, in a red alert by the button.
- **`422`:** "That number of copies isn't possible."
- **`500` or no answer:** the `detail` if there is one, otherwise "The library isn't answering. Try again in a moment."
- Never raw JSON, a bare status code or a stack trace.

## The walkthrough

1. Two windows, a normal one and a private one, have separate baskets.
2. With one copy left, both baskets hold it and both borrow: one gets its loan, the other "Only 0 of … on the shelf."
3. An expired card: the basket page shows the notice and an empty basket, and adding works again.
```

It's short, and it decides things: the key it stores the card under, what "Add to basket" sends, the exact wording of each message. Where yours is vague, your agent will be creative.

## You write

**`FRONTEND-SPEC.md`,** at the top of your repository, in your own words, 300 words or more. Don't ask an agent to write it. A spec someone else wrote holds their decisions, not yours.

## Check

```
make check M=6 STEP=2
```

**You should see** everything before, then:

```
Saved to checks/last-run.txt
```

## Step done

```
git add -A
git commit -m "M6-2: the spec"
git push
```

Answer your tutor's questions under `## M6-2` in `JOURNAL.md`.

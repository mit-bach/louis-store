# Optional spec 15 · Errors the browser can read

**Why:** in M6-3's testing, the agent building the frontend noticed something about your backend, and asked instead of changing it. When your API answers `500`, the browser won't let the page read the answer. So where your contract promises "Something went wrong in the store. Try again in a moment.", the page can only say that the store isn't answering. This spec moves one piece of your `main.py`, so the page gets your message.

## See it first

Your store running (`make up`), and your frontend (`cd frontend && pnpm dev`). Break the database the way M5-3 did:

```
docker compose exec db psql -U store -d store -c "ALTER TABLE order_lines RENAME TO order_lines_gone;"
```

Put something in your cart in the browser, and check out. Open the browser's developer tools (⌥⌘I in Chrome) at the **Console** tab, and look for a red line about CORS.

**Predict,** under `## Spec 15` in `PREDICTIONS.md`: what does the page show? And what does the console say?

The same request from the terminal, as the browser sends it, with its `Origin` header:

```
TOKEN=$(./store session start | python3 -c "import json, sys; print(json.load(sys.stdin)['token'])")
./store cart set 3 1 --session $TOKEN > /dev/null
curl -s -i -X POST -H 'Origin: http://localhost:3000' -H "Authorization: Bearer $TOKEN" http://localhost:8000/checkout | grep -i -E '^HTTP|^access-control-allow-origin|^[{]'
```

```
HTTP/1.1 500 Internal Server Error
{"detail":"Something went wrong in the store. Try again in a moment."}
```

A `500`, with your message in it, and no `access-control-allow-origin` line. Your API did send the message. Without that header, the browser keeps the answer from the page, as it would for any server that didn't say the page may read it.

## The idea: layers

A request passes through layers on its way in, and back out through them in reverse. These layers are called **middleware**. Think of an onion:
- **Outermost, always,** is Starlette's own error layer. Your `@app.exception_handler(Exception)` runs there.
- **Inside it** are the layers you add with `app.add_middleware()`. Each one you add goes outside the ones added before it.
- **Innermost** are your routes.

The CORS middleware adds its header to answers on their way out. An answer made by the outermost error layer never passes back through CORS, so it leaves without the header. The fix is to catch unexpected errors in a layer **inside** CORS:
- `@app.middleware("http")` adds a layer from a function. The function gets the request, and `call_next(request)` to pass it inwards.
- Define it **before** `app.add_middleware(CORSMiddleware, …)`. The CORS layer is then added after it, so it goes outside it, and wraps whatever your function answers.
- Your function catches the exception, so Starlette never sees it, and won't log it. Log it yourself: `logging.getLogger("uvicorn.error").exception(...)` writes the message and the traceback to the API's log.

An example on a different problem: a layer that times every request, and adds a header to each answer:

```python
@app.middleware("http")
async def timing(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)          # everything inside this layer runs here
    response.headers["X-Took-Ms"] = f"{(time.perf_counter() - started) * 1000:.0f}"
    return response
```

## You write

In `backend/main.py`, replace your `@app.exception_handler(Exception)` with a middleware function that:
- passes the request on with `call_next`;
- catches any exception, logs it with its traceback, and answers `500` with `{"detail": UNEXPECTED}`;
- is defined above `app.add_middleware(CORSMiddleware, …)`.

**Predict** first: if you put it *below* the CORS middleware instead, what would `curl` show? Try it, then put it above.

## Check

Still with the table hidden, the same request:

```
TOKEN=$(./store session start | python3 -c "import json, sys; print(json.load(sys.stdin)['token'])")
./store cart set 3 1 --session $TOKEN > /dev/null
curl -s -i -X POST -H 'Origin: http://localhost:3000' -H "Authorization: Bearer $TOKEN" http://localhost:8000/checkout | grep -i -E '^HTTP|^access-control-allow-origin|^[{]'
```

**You should see** your message, and the header:

```
HTTP/1.1 500 Internal Server Error
access-control-allow-origin: http://localhost:3000
{"detail":"Something went wrong in the store. Try again in a moment."}
```

Check out again in the browser. **Expected:** the page shows your message, and the console has no CORS error.

<details><summary>What happened when this was tested</summary>

Tested on 2026-11-11 in a headless browser, with the frontend built in M6's testing and the `order_lines` table hidden, by clicking **Check out**:
- **Before the fix,** the page said "The store isn't answering. Try again in a moment.", and the console had 3 CORS errors.
- **After it,** the page said "Something went wrong in the store. Try again in a moment.", and the console had none.
</details>

Then put the table back:

```
docker compose exec db psql -U store -d store -c "ALTER TABLE order_lines_gone RENAME TO order_lines;"
```

```
make spec S=15
```

**You should see:**

```
  PASS  S15-1  a 500 answers a page from http://localhost:3000 with the CORS header and the contract's message
  PASS  S15-2  the traceback still reaches your API's log
  PASS  S15-3  ./store and the tools still answer with the contract's message, and CORS still allows only your frontend

3 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

The last check makes sure nothing else moved: `./store` and the tools still give M5's answers, and CORS still allows only your frontend.

## Done

```
git add -A
git commit -m "Spec 15: errors the browser can read"
git push
```

# Step M1-5 · The HTTP routes

**Why:** your operations work, but only Python can call them. HTTP is the first way in: web pages, other programs, and later your frontend use it. Each route is an **adapter**. It takes a request, calls an operation, and turns the result, or the operation's named error, into an HTTP answer. It does no work of its own.

## The idea

- **`@app.get("/path")`** on top of a function means: when a `GET` request arrives at that path, run this function and send back what it returns, as JSON. `@app.post` is the same for `POST`, the method for creating things.
- **A path parameter:** `@app.get("/books/{book_id}")` with a function parameter `book_id: int` takes the number from the address. Because it's typed `int`, FastAPI refuses `/books/abc` with a `422`, before your function runs.
- **A body:** a function parameter typed with a Pydantic model, like `data: BookCreate`, is read from the request's JSON body. FastAPI checks it against the model, and answers `422` with the reasons if it breaks a rule. Your function never sees invalid data.
- **`response_model=…`** tells FastAPI the shape of the answer, for its docs page. **`status_code=201`** means "created".
- **`raise HTTPException(status_code=…, detail=…)`** sends an error answer: that status, and `{"detail": …}` as the body.

**Mapping errors.** The route catches the operation's named error, and picks the status from the contract's table:
- not found → `404`;
- conflict with what's stored → `409`;
- invalid input → `422`, which FastAPI already sends for you.

Any error you don't catch becomes a `500 Internal Server Error`, with no useful message. To a caller, and to an agent, that's a dead end.

**An example on a different table,** the library's routes:

```python
from fastapi import FastAPI, HTTPException

import books
from schemas import Book, BookCreate


app = FastAPI(title="Library")


@app.get("/books", response_model=list[Book])
def get_books():
    return books.list_books()


@app.get("/books/{book_id}", response_model=Book)
def get_one_book(book_id: int):
    try:
        return books.get_book(book_id)
    except books.BookNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/books", response_model=Book, status_code=201)
def post_book(data: BookCreate):
    try:
        return books.add_book(data)
    except books.DuplicateIsbn as e:
        raise HTTPException(status_code=409, detail=str(e))
```

## You write, in `backend/main.py`

Keep everything that's there, including `/health`. Add:
- `HTTPException` to the `fastapi` import, `import products`, and `from schemas import Product, ProductCreate`;
- **`GET /products`**, returning `list_products()`, with `response_model=list[Product]`;
- **`GET /products/{product_id}`**, returning `get_product(product_id)`, with `ProductNotFound` turned into a `404` whose detail is the error's message;
- **`POST /products`**, taking a `ProductCreate` body, answering `201` with the new product, with `DuplicateSku` turned into a `409` whose detail is the error's message.

**Hint:** `str(e)` is the error's message. The route doesn't write messages of its own: the operation already did.

Save the file, and uvicorn restarts by itself, because of `--reload`.

## Check

One product:

```
curl -s http://localhost:8000/products/1
```

**You should see** your product 1, as JSON. Mine:

```
{"sku":"TENT-2P","name":"Two-Person Tent","description":"Freestanding, 2.1 kg, two doors.","category":"shelter","image_url":null,"price_cents":24900,"stock":5,"id":1,"created_at":"2026-11-08T17:43:57.649283Z","updated_at":"2026-11-08T17:43:57.649283Z"}
```

A product that isn't there. `-w '\n%{http_code}\n'` makes curl print the status code on its own line after the body:

```
curl -s -w '\n%{http_code}\n' http://localhost:8000/products/999999
```

**You should see:**

```
{"detail":"No product with id 999999."}
404
```

A new product:

```
curl -s -w '\n%{http_code}\n' -X POST http://localhost:8000/products -H 'Content-Type: application/json' -d '{"sku": "TEST-MUG", "name": "Enamel mug", "category": "cooking", "price_cents": 1200}'
```

**You should see** the new product with its id, its defaults, and `201`:

```
{"sku":"TEST-MUG","name":"Enamel mug","description":null,"category":"cooking","image_url":null,"price_cents":1200,"stock":0,"id":11,"created_at":"2026-11-08T17:43:57.715754Z","updated_at":"2026-11-08T17:43:57.715754Z"}
201
```

**Predict,** under `## M1-5` in `PREDICTIONS.md`: what happens when you send exactly the same request again? Then send it, and write what happened.

<details><summary>What mine answered</summary>

```
{"detail":"A product with the SKU TEST-MUG already exists."}
409
```
</details>

And a negative price:

```
curl -s -w '\n%{http_code}\n' -X POST http://localhost:8000/products -H 'Content-Type: application/json' -d '{"sku": "TEST-BAD", "name": "Bad", "category": "cooking", "price_cents": -5}'
```

```
{"detail":[{"type":"greater_than_equal","loc":["body","price_cents"],"msg":"Input should be greater than or equal to 0","input":-5,"ctx":{"ge":0}}]}
422
```

Pydantic refused it before your route ran. Its `detail` is a list, with each problem's place (`["body","price_cents"]`) and message, which a program or an agent can read. Your table's `CHECK` is still there, behind it, for every writer that doesn't come through this model.

**Your API's docs.** Open http://localhost:8000/docs in a browser. FastAPI built this page from your routes and your models: your three routes are there, with `Product` and `ProductCreate` under "Schemas", and your `price_cents` description. The same information, as JSON, is at http://localhost:8000/openapi.json. The parity check in step 7 reads it.

**If something doesn't match:**
- `500 Internal Server Error`: an error reached FastAPI uncaught. Run `make logs`: the last lines show the error and the line it came from.
- `{"detail":"Not Found"}` for a path you wrote: the path in your decorator differs from the one you called.
- No answer at all: a typo stopped the server from restarting. `make logs` shows the Python error.

## Check

```
make check M=1 STEP=5
```

**You should see** everything before, then:

```
  PASS  M1-5  GET /products answers 200 with every product, sorted by id
  PASS  M1-5  GET /products/{id} answers 200 with that product
  PASS  M1-5  GET /products/999999 answers 404 with the contract's message
  PASS  M1-5  GET /products/abc answers 422
  PASS  M1-5  POST /products answers 201 with the new product, its defaults filled in
  PASS  M1-5  POST /products with a SKU that exists answers 409 with the contract's message
  PASS  M1-5  POST /products with a negative price answers 422, and saves nothing
  PASS  M1-5  POST /products with a price of 12.5 cents answers 422
  PASS  M1-5  POST /products without a name answers 422

37 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

## Step done

Look at what git sees:

```
git status --short
```

**You should see** this. `M` means changed, and `??` new. Your journal and predictions are listed because you wrote in them:

```
 M JOURNAL.md
 M PREDICTIONS.md
 M backend/main.py
```

Then commit and push:

```
git add -A
git commit -m "M1-5: the HTTP routes"
git push
```

Answer your tutor's questions under `## M1-5` in `JOURNAL.md`.

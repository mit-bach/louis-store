# Step M0-1 · Your tools, and your own copy of the kit

**Why:** before you write anything, three tools have to be on your Mac, and the kit needs a home of yours on GitHub, where your work is saved and Dominik can see it.
- **Docker** runs your store's server and its database.
- **uv** runs the kit's checks.
- **The GitHub CLI** creates your repository.

This step is all **given**. There's nothing to decide yet.

## 1. Find the kit

Your setup prompt cloned this kit to `~/code/store`. Open a terminal tab in cmux and run:

```
cd ~/code/store
ls
```

**You should see** these names, among others: `BRIEF.md`, `CONTRACT.md`, `Makefile`, `checks`, `milestones`.

**If it says "no such file or directory",** clone it yourself, then run the two commands again:

```
git clone https://github.com/mit-bach/louis-store ~/code/store
```

Every command in every guide runs in `~/code/store`, unless the guide says otherwise.

## 2. Docker Desktop

**What it is.** Your store runs in **containers**. A container is a small, sealed-off Linux machine that runs one program, built from an **image**: a frozen snapshot of everything that program needs. Docker Desktop is the app that runs containers on a Mac. You'll use its command, `docker`, from the terminal.

**Install it:**
1. Open https://www.docker.com/products/docker-desktop/ and download Docker Desktop for Mac. Pick **Apple Silicon** if your Mac has an M-series chip (Apple menu → About This Mac says "Chip: Apple M…"), and **Intel** otherwise.
2. Open the downloaded file, and drag Docker into Applications.
3. Open Docker from Applications. Accept its terms, skip the sign-in (you don't need an account), and wait until the window's bottom-left corner says the engine is running.

**Check it:**

```
docker compose version
```

**You should see** one line that starts with `Docker Compose version v`, followed by a version number.

**If you see `command not found: docker`,** Docker Desktop isn't running yet. Open it, wait for the engine, then open a new terminal tab and try again.

## 3. uv

**What it is.** uv installs and runs Python programs. The kit's checks are a Python program, and uv fetches the right Python and the libraries the checks need, without touching anything else on your Mac.

**Check whether you have it:**

```
uv --version
```

**You should see** a line like `uv 0.13.0 (…)`. Any version from 0.13 on is fine. **If it says `command not found: uv`,** install it:

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then open a new terminal tab, so it picks up the new command, and run `uv --version` again.

## 4. The GitHub CLI

**What it is.** `gh` is GitHub's command-line tool. You'll use it to create your repository and to sign git in to GitHub.

**Check whether you have it:**

```
gh --version
```

**You should see** a line like `gh version 2.102.0 (2026-09-30)`. **If it says `command not found: gh`,** install it.
- If `brew --version` answers, run `brew install gh`.
- Otherwise, download the macOS installer from https://cli.github.com and open it.

**Sign in, if you haven't:**

```
gh auth status
```

If it says you're not logged in, run `gh auth login`, and answer its questions like this:
1. **Where do you use GitHub?** GitHub.com.
2. **Preferred protocol for Git operations?** HTTPS.
3. **Authenticate Git with your GitHub credentials?** Yes.
4. **How would you like to authenticate?** Login with a web browser. It shows a one-time code; press Enter, and paste the code into the page that opens.

Then `gh auth status` says you're logged in to github.com.

**Tell git who you are,** if you haven't. Every commit records a name and an email:

```
git config --global user.name
git config --global user.email
```

If either prints nothing, set it, with your name, and the email address on your GitHub account (or the private one GitHub offers under Settings → Emails):

```
git config --global user.name "Your Name"
git config --global user.email "YOUR-EMAIL"
```

## 5. Two remotes: the kit, and your own copy

**The idea.** A git **remote** is a named address of another copy of your repository. When you cloned the kit, git called its address `origin`. You'll rename it to `kit`, because it's where updates to the guides come from. Then you'll create your own repository on GitHub, and call it `origin`, because that's where your work goes.

**Rename the kit's remote:**

```
git remote rename origin kit
```

**Create your own repository and push the kit into it:**

```
gh repo create store --public --source . --remote origin --push
```

**What each part does:**
- **`store`** is the repository's name on your GitHub account. Pick another if you already have one called `store`.
- **`--public`** lets Dominik read it without an invitation. Nothing secret will ever be in it: step 2 makes sure your password stays out. If you'd rather keep it private, use `--private`, and add Dominik (`mit-bach`) as a collaborator on GitHub.
- **`--source .`** uses this folder as the repository, and **`--remote origin`** names its address `origin`.
- **`--push`** uploads everything that's here.

**You should see** three lines starting with `✓`, saying the repository was created, the remote was added and the commits were pushed. This is gh's usual output; it wasn't run for this guide, because it creates a real repository.

**Check your remotes:**

```
git remote -v
```

**You should see** four lines: two that start with `kit` and name `github.com/mit-bach/louis-store`, and two that start with `origin` and name your own `store` repository. Each pair has one line ending `(fetch)` and one ending `(push)`.

**How updates reach you.** When new milestones or fixes arrive in the kit, you take them with:

```
make update
```

It runs `git pull --no-rebase --no-edit kit main`, which fetches the kit's new commits and merges them into yours. The kit never changes your own files, so the merge is clean. Your work goes to your repository with `git push`, as always.

## Check

```
make check M=0 STEP=1
```

**The first time,** uv downloads the checks' libraries, which takes a few seconds. **You should see:**

```
Store checks · M0 up to step 1 · 2026-11-08 12:42 EST

M0 · Setup
  PASS  M0-1  Docker is running
  PASS  M0-1  this folder is a git repository, with the kit as the remote called kit
  PASS  M0-1  your own GitHub repository is the remote called origin

3 passed, 0 failed, 0 skipped.
Saved to checks/last-run.txt
```

The date and time are yours. **If a line says `FAIL`,** read its `expected`, `got` and `hint` lines, which name the part of this step to redo.

## Step done

- The check passes.
- Nothing to commit: you've changed no files yet, only settings.
- In `JOURNAL.md`, under `## M0-1`, write one line on anything that didn't go as this guide said. "Nothing" is a fine answer. Your tutor's questions for this step go there too.

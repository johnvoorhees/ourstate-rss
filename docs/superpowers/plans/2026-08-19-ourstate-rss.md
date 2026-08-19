# Our State RSS Feed Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a metadata-only Our State RSS feed on GitHub Pages and update it hourly from `johns-mac-mini-1`.

**Architecture:** A Python standard-library generator fetches the public WordPress posts API and serializes validated RSS 2.0. A launchd job on the Mac mini runs a publishing wrapper that atomically updates `docs/feed.xml` and pushes only changed output; GitHub Pages serves the feed publicly.

**Tech Stack:** Python 3.11+ standard library, `unittest`, Bash, launchd, Git, GitHub Pages

**Spec:** `docs/superpowers/specs/2026-08-19-ourstate-rss-design.md`

## Global Constraints

- Request at most 20 posts once per hourly run.
- Publish only titles, canonical links, dates, short source excerpts, and attribution.
- Do not publish full article bodies, images, credentials, or private data.
- Preserve the last valid feed when fetching, validation, generation, Git, or network operations fail.
- Use only unauthenticated read-only requests to `https://www.ourstate.com/wp-json/wp/v2/posts`.
- The runtime checkout is `/Users/johnvoorhees/Code/ourstate-rss` on `johns-mac-mini-1`.

---

### Task 1: Feed generator

**Files:**
- Create: `pyproject.toml`
- Create: `src/ourstate_rss/__init__.py`
- Create: `src/ourstate_rss/generator.py`
- Create: `tests/__init__.py`
- Create: `tests/fixtures/posts.json`
- Create: `tests/test_generator.py`

**Interfaces:**
- Produces: `Post`, `fetch_posts(api_url, limit=20, opener=urlopen, sleeper=time.sleep) -> list[Post]`
- Produces: `build_feed(posts, feed_url, now=None) -> bytes`
- Produces: `plain_text(value: str) -> str`

- [ ] **Step 1: Write generator tests and a three-post WordPress fixture**

Test successful normalization, newest-first ordering, HTML entity decoding, stable `ourstate-post-<id>` GUIDs, RSS escaping, attribution, rejection of non-Our-State links, empty results, malformed JSON, and retry-after-network-error behavior.

- [ ] **Step 2: Run the tests to verify failure**

Run: `python3 -m unittest tests.test_generator -v`

Expected: FAIL because `ourstate_rss.generator` does not exist.

- [ ] **Step 3: Implement the standard-library generator**

Use `urllib.request.Request` with a descriptive User-Agent, `urllib.request.urlopen`, a 30-second timeout, and at most two attempts. Convert WordPress objects to an immutable `Post` dataclass, permit only `https://www.ourstate.com/` canonical links, and reject empty result sets. Use `html.parser.HTMLParser` and `html.unescape` to create plain-text titles and excerpts. Serialize RSS with `xml.etree.ElementTree` and RFC 2822 UTC dates from `email.utils.format_datetime`.

- [ ] **Step 4: Run focused and complete tests**

Run: `PYTHONPATH=src python3 -m unittest tests.test_generator -v`

Expected: PASS.

- [ ] **Step 5: Commit the generator**

```bash
git add pyproject.toml src tests
git commit -m "Add Our State RSS generator"
```

### Task 2: Atomic updater and initial feed

**Files:**
- Create: `scripts/update_feed.py`
- Create: `tests/test_update_feed.py`
- Create: `docs/feed.xml`

**Interfaces:**
- Consumes: `fetch_posts` and `build_feed` from Task 1
- Produces: `write_feed(path: Path, content: bytes) -> bool`, returning `True` only when the destination changes
- Produces: CLI exit code `0` after a valid update or no-op and nonzero on failure

- [ ] **Step 1: Write updater tests**

Test that `write_feed` validates XML before replacement, creates a missing destination, reports an unchanged document without rewriting it, replaces changed content atomically, and leaves the previous document intact for invalid XML.

- [ ] **Step 2: Run the updater tests to verify failure**

Run: `PYTHONPATH=src python3 -m unittest tests.test_update_feed -v`

Expected: FAIL because `scripts.update_feed` does not exist.

- [ ] **Step 3: Implement the updater CLI**

Set the API URL to `https://www.ourstate.com/wp-json/wp/v2/posts`, the public feed URL to `https://johnvoorhees.github.io/ourstate-rss/feed.xml`, and the output to `docs/feed.xml`. Generate entirely in memory, validate with `ElementTree.fromstring`, write a sibling temporary file, flush and `fsync`, then replace with `Path.replace`.

- [ ] **Step 4: Generate the initial live feed and validate it**

Run: `PYTHONPATH=src python3 scripts/update_feed.py`

Run: `xmllint --noout docs/feed.xml`

Expected: updater reports 20 items and `xmllint` exits `0`.

- [ ] **Step 5: Run all tests and commit**

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
git add scripts tests docs/feed.xml
git commit -m "Add atomic feed updater"
```

### Task 3: Mac mini publishing runtime

**Files:**
- Create: `scripts/publish.sh`
- Create: `com.johnvoorhees.ourstate-rss.plist`
- Create: `logs/.gitkeep`
- Create: `.gitignore`
- Create: `README.md`
- Create: `tests/test_runtime_files.py`

**Interfaces:**
- Consumes: updater CLI from Task 2
- Produces: idempotent `scripts/publish.sh` that exits `0` without a commit when `docs/feed.xml` is unchanged
- Produces: launchd label `com.johnvoorhees.ourstate-rss`, running hourly and at load

- [ ] **Step 1: Write runtime-file tests**

Parse the plist with `plistlib` and assert its label, absolute working directory, hourly `StartInterval` of `3600`, `RunAtLoad`, program path, PATH, and log paths. Assert the shell script enables `set -euo pipefail`, uses a lock directory, runs the updater with `PYTHONPATH=src`, limits Git operations to `docs/feed.xml`, and pushes `main`.

- [ ] **Step 2: Run runtime tests to verify failure**

Run: `PYTHONPATH=src python3 -m unittest tests.test_runtime_files -v`

Expected: FAIL because the runtime files do not exist.

- [ ] **Step 3: Implement runtime files and documentation**

The publishing wrapper changes to the runtime checkout, creates `.publish.lock` with `mkdir`, removes it with an EXIT trap, runs the updater, checks `git diff --quiet -- docs/feed.xml`, and when changed commits only that file using message `Update Our State feed` before pushing `origin main`. The README documents the unofficial status, source, published fields, public URL, local test command, manual update command, launchd commands, and failure logs.

- [ ] **Step 4: Run all tests and shell/plist validation**

Run: `PYTHONPATH=src python3 -m unittest discover -s tests -v`

Run: `bash -n scripts/publish.sh`

Run: `plutil -lint com.johnvoorhees.ourstate-rss.plist`

Expected: all commands pass.

- [ ] **Step 5: Commit the runtime**

```bash
git add .gitignore README.md scripts/publish.sh com.johnvoorhees.ourstate-rss.plist logs/.gitkeep tests/test_runtime_files.py
git commit -m "Add Mac mini publishing runtime"
```

### Task 4: GitHub and Mac mini deployment

**Files:**
- Deploy checkout: `/Users/johnvoorhees/Code/ourstate-rss` on `johns-mac-mini-1`
- Install plist: `/Users/johnvoorhees/Library/LaunchAgents/com.johnvoorhees.ourstate-rss.plist` on `johns-mac-mini-1`

**Interfaces:**
- Consumes: complete repository from Tasks 1–3
- Produces: public repository `johnvoorhees/ourstate-rss`
- Produces: public feed `https://johnvoorhees.github.io/ourstate-rss/feed.xml`
- Produces: loaded launchd job `com.johnvoorhees.ourstate-rss`

- [ ] **Step 1: Create and push the public GitHub repository**

Run: `gh repo create johnvoorhees/ourstate-rss --public --source=. --remote=origin --push`

Expected: repository created and `main` pushed.

- [ ] **Step 2: Enable GitHub Pages from `main:/docs`**

Run: `gh api --method POST repos/johnvoorhees/ourstate-rss/pages -f 'source[branch]=main' -f 'source[path]=/docs'`

Expected: API response identifies the Pages URL.

- [ ] **Step 3: Clone and verify on the Mac mini**

Run remotely: `git clone https://github.com/johnvoorhees/ourstate-rss.git /Users/johnvoorhees/Code/ourstate-rss`

Run remotely: `cd /Users/johnvoorhees/Code/ourstate-rss && PYTHONPATH=src python3 -m unittest discover -s tests -v`

Expected: all tests pass using the mini's Python.

- [ ] **Step 4: Install and load the LaunchAgent**

Copy the plist from the checkout to `~/Library/LaunchAgents`, run `launchctl bootout gui/$(id -u)/com.johnvoorhees.ourstate-rss` only if already loaded, then run `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.johnvoorhees.ourstate-rss.plist` and `launchctl kickstart -k gui/$(id -u)/com.johnvoorhees.ourstate-rss`.

Expected: `launchctl print` shows the job and the last exit code is `0`.

- [ ] **Step 5: Validate the public feed**

Poll the GitHub Pages URL until it returns `200`. Validate with `xmllint`, the W3C Feed Validator, `User-Agent: Feedbin`, and `User-Agent: Feedbin feed-id:123 - 1 subscribers`. Confirm 20 items, stable GUIDs, Our State canonical links, and no images or full article bodies.

- [ ] **Step 6: Commit any deployment documentation corrections**

```bash
git add README.md
git commit -m "Document deployed feed service"
git push origin main
```

Skip this commit when deployment required no documentation correction.

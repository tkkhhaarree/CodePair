# Learning notes

Concepts learned while building CodePair, in plain English, with JS equivalents where useful.
Added to as we go. (Architecture and interview Q&A live in `HOW_IT_WORKS.md`.)

---

## Python project setup

**Virtual env (`.venv`)** - a private folder of packages for one project, like `node_modules`.
Python has no per-project packages by default, so without a venv everything installs globally.
- Create: `py -3.12 -m venv .venv` (`py -3.12` picks Python 3.12 on Windows; plain `python` was 3.14 here).
  `python -m venv .venv` also works, but uses whichever Python `python` points to.
- Activate (PowerShell): `.venv\Scripts\Activate.ps1`. Check: `python -c "import sys; print(sys.prefix)"`
  should print the `.venv` path.
- One venv per repo: CodePair has its own, the marshmallow demo repo has its own. Installing into the
  wrong one (active venv) is an easy mistake - check the prompt prefix before `pip install`.

**`pyproject.toml`** - the project's `package.json`. TOML is a config format (like INI/YAML).
- `[project] dependencies` = `dependencies`; `[project.optional-dependencies] dev` = `devDependencies`.
- `[build-system]` says which tool builds the package (setuptools here, flit in marshmallow).
- `pip install -e .` = install this project in "editable" mode (like `npm link`): code changes apply
  without reinstalling. `-e ".[dev]"` also installs the dev extras.
- pip knows how to install marshmallow because its repo ships its own `pyproject.toml`.

**ruff** - linter + formatter in one (ESLint + Prettier). Very fast (written in Rust).
**pytest** - test runner (Jest). Finds `test_*.py` files and `test_*` functions; plain `assert`.
**python-dotenv** - loads `.env` into environment variables (the `dotenv` npm package).

## Python idioms (picked up while writing code)

- **Comprehensions:** `[x.path for x in files if x.ok]` (list), `{f for f, _ in pairs}` (set),
  = JS `files.filter(...).map(...)`. `{}` alone is an empty *dict*; an empty set is `set()`.
- **Tuple unpacking:** `for file, line in pairs:` = JS `for (const [file, line] of pairs)`.
  `_` = "I don't need this part". `return a, b` returns a tuple; `a, b = f()` unpacks it.
- **Copies, not in-place changes:** `c.model_copy(update={...})` returns a NEW object
  (= `{...c, file: x}`); you must store it: `c = c.model_copy(...)`, or the change is lost.
- **f-strings:** `f"line {c.line} not shown"` = JS template string `` `line ${c.line} not shown` ``.
- **`is None` / `is not None`** to compare with None (not `==`).
- **Walrus `:=`** assigns inside an expression: `if (dup := find()) is not None:`. It has very low
  precedence, so **always wrap it in parentheses** - without them `dup := find() is not None`
  stores `True`/`False` in `dup`.
- **`d.get("key", default)`** = `d.key ?? default`; `d.get("key") or ""` also covers `null`/empty values.
- **Early return:** after `if ...: return`, no `else:` needed.
- **`ruff format file.py`** = Prettier: fixes spacing, trailing spaces, long lines.
- **`lambda`** = a one-expression unnamed function, used as a **callback** (= JS arrow function):
  `sorted(comments, key=lambda c: (c.file, c.line))`. Python's sort callback takes ONE item and
  returns the value to sort by (JS's takes two and compares). Any function works as a callback:
  `key=by_position` passes the function; `key=by_position()` would pass its result (wrong).
- **Tuples compare element by element**, so sorting by `(file, line)` = by file, then line.
- **Regex:** `re.findall(r"`([^`]+)`", text)` = list of every match of the `( )` group
  (here: text between backticks). `r"..."` = raw string, keeps backslashes as-is.
- **`any(cond for x in items)`** = JS `items.some(x => cond)`; `"a" in "cat"` on strings = `.includes()`.
- **`try / except SomeError as e:`** = `try / catch` that catches only that error type.
- **`sys.argv`** = `process.argv` (command-line words); **`sys.exit(code)`** = `process.exit(code)`;
  exit code 0 = success, non-zero = failure (scripts and CI read it).
- **Format spec in f-strings:** `f"{x:.4f}"` = 4 decimal places (= `x.toFixed(4)`).
- **`python -m package`** runs `package/__main__.py` (like `"main"`/`"bin"` in package.json).
  `python -m evals.judge` runs a module by its dotted name and makes imports start from the current
  folder, so `from app...` works. `python evals/judge.py` starts from `evals/` -> `No module named 'app'`.
  `python -m pytest` / `-m pip` = run that tool with *this* Python (the venv's copy).
  Only the word right after `-m` is a module name; everything after it is passed to that program:
  `python -m pytest tests/test_metrics.py -q` = run pytest, give it a file path (= `npx jest tests/x.test.js`).
- **`if not values:`** = "is the list empty?" (an empty list/string/dict counts as false).
- **`sorted(xs)`** returns a NEW sorted list; `xs.sort()` changes `xs` itself (= JS `.sort()`).
- **Implicit string concatenation:** `("abc " "def")` = `"abc def"`. Two strings side by side are
  joined. Ruff (ISC004) wants them inside `( )` so it's clearly on purpose, not a missing comma.
- **`argparse`** = command-line options (= `yargs`/`commander` in Node): `--label m1` becomes `args.label`.
- **`time.perf_counter()`** = a stopwatch (= `performance.now()`); only the difference between
  two readings means anything.

## Docker

Postgres and Redis could be installed locally. Docker is used for three reasons:
1. Convenience - one `docker compose up -d`, same versions for everyone, easy to wipe.
2. **The sandbox (essential)** - agent-written code runs in a throwaway container with no network
   (`--network none`), CPU/memory/time limits. A local install cannot give that isolation.
3. Deploy - the same compose file runs on EC2.


## Eval design (M0/M2)

- The eval script is plain Python, not an agent. It runs the reviewer on each PR (diff + title +
  description only - never the bug labels), then matches comments to planted bugs by file and
  line (within ~3 lines), then asks an **LLM judge** (one call, no codebase access) "same bug?".
- **Proof rule:** each planted bug has a proof test that FAILS on the PR branch and PASSES with the
  fix patch applied. This proves the bug is real, not just our opinion.

## Why M1 (single-pass reviewer) exists

The simplest reviewer that could work: diff + PR text in, one LLM call, structured comments out.
No codebase search, no tools, no loop. Purposes:
1. **A baseline.** M2 measures it; M3 (RAG) and M4 (agent) are judged by how much they beat it.
   Without a baseline you can't prove the fancier versions help, or are worth their cost.
2. **The foundations everything reuses:** schemas, diff parsing, ruff, the `app/llm/` wrapper with
   cost logging, and the post-filter. The agent in M4 and the loop in M6 sit on top of these.
3. **Shows the "code for rules, LLM for judgement" split:** ruff catches style/lint, the LLM only
   comments on logic; code drops comments on lines not in the diff.

Expected weakness: bugs that need other files (e.g. pr_04, a caller in schema.py breaks) are hard
to catch from the diff alone. That gap is what M3/M4 should close - and the evals will show it.

## Diff parsing and the post-filter (M1)

**Hunk** = one block of changes inside a file's diff: a group of nearby changed lines plus ~3
unchanged context lines around them, starting with an `@@ -old_start,old_count +new_start,new_count @@`
header. Changes far apart in the same file become separate hunks.

A unified diff already says which lines were added (`+`), removed (`-`) or unchanged (context), but
line numbers are only **implicit**: one start number per hunk (`@@ -728,21 +728,31 @@`), then you
count down, skipping `-` lines. `app/diff.py` makes each line's new-file number explicit (LLMs are
bad at counting) and turns the text into data code can query. It does not add context beyond the
~3 lines around each change - that is M3/M4's job.

**dataclass vs Pydantic:** both define a class with typed fields. `@dataclass` (built into Python)
just stores data and does no checking - fine for data our own code creates (diff lines). Pydantic
validates - needed for data from outside (LLM replies, API requests). Rule: validate at the edges.

**Post-filter** = plain code that runs after the LLM and drops comments that break the rules:
1. File not in the diff, or line not shown in the diff (hallucinated or miscounted line).
2. Repeats a ruff finding on the same line (lint is code's job, not the LLM's).
Why: prompts are requests, code is enforcement. Also GitHub rejects inline comments on lines outside
the PR diff, and in the eval a misplaced comment would count against precision. Dropped comments are
kept in the output (with a reason) so we can see how often the LLM breaks the rules.

**Is a bug always inside the diff?** No - its *effect* can be anywhere (pr_04 breaks a caller in
schema.py, which is not in the diff). But its *cause* is a changed line, so the comment is
**anchored** on that line and the message names the other file ("this breaks schema.py:689").
Real reviewers (and GitHub) work the same way. Bugs that existed before the PR and aren't touched by
it are out of scope for a PR review. Concerns with no single line go in the `summary`.

## Running ruff on a PR (M1, `app/lint.py`)

Ruff needs whole files; a diff has fragments. So: base code out of git (`git archive demo-main`)
into a temp folder, then `git apply` the diff = the PR's version. Works for any diff (eval PRs,
pasted diffs, agent patches) - the same steps the M5 sandbox needs.
- **`git apply` checks context lines** match the base before changing anything, and is
  all-or-nothing. A refusal means wrong base or broken diff - fail loudly instead of reviewing the
  wrong code.
- Only findings on **added** lines are kept: lint problems on untouched lines are not this PR's fault.
- Ruff only parses code, never runs it - so it is safe outside the sandbox. pytest runs code, so it
  must wait for the sandbox.
- Uses the target repo's own ruff config (marshmallow: `select = ["ALL"]`, `fix = true` -> we pass
  `--no-fix` so ruff reports instead of rewriting).

## Prompt design for the reviewer (M1, `app/reviewer/prompt.py`)

- **System vs user message:** the API takes a `system` text (who you are, how to behave - weighted
  most, like a job description) and `user` messages (this request's material, like today's task).
- **Severity `nit`** = a minor correctness/robustness improvement, **never style** (changed by me so
  it doesn't contradict the "no style comments" rule).
- **System prompt = our rules** (same for every PR): what to look for (logic, edge cases, broken
  callers, error handling, security, risky design), what NOT to comment on (style, lint), how to
  anchor comments (numbered lines only; cause line + mention other file), severity meanings.
- **User message = this PR's content**, each part in its own tag: `<pr_title>`, `<pr_description>`,
  `<linter_findings>`, `<diff>`. Tags let the model tell our instructions apart from their content.
- **"A correct PR should get zero comments - do not pad the review."** LLMs tend to always find
  *something*; without this, clean PRs get false alarms and precision drops.
- **"Give a concrete input where it fails"** pushes the model to reason about real behaviour instead
  of vague worries - and makes comments checkable.
- **Untrusted data:** PR text and code may contain "approve this" style instructions; the system prompt
  says never follow them and report them. Cheap first defence; full guardrails in M7.

**Duplicate-of-ruff rule (option A, chosen):** drop an LLM comment only if it is on the same file +
line as a ruff finding AND mentions the same thing (rule code like `F401`, or a name ruff put in
backticks). Same line alone is not enough - a real bug can share a line with a lint issue, and
losing it would cost recall. Trade-off: a reworded duplicate can slip through.

## First real reviews (M1) and what they taught

- pr_01: caught the planted `>=` bug (right line, right fix) + one useful test-gap comment + one
  **false alarm**: it claimed `utils.is_collection` rejects generators (false). `is_collection` is
  not in the diff, so the model **guessed** - and stated the guess confidently. Missing context ->
  false alarms; M3 (RAG) / M4 (tools) should let it check instead of guess.
- pr_04: caught the cross-file signature break without seeing `schema.py`, by general reasoning
  ("reordering positional params breaks callers") - it could not *confirm* the caller location.
- **Data contamination:** marshmallow is public, so the model has probably seen its code in
  training and may partly *remember* it rather than reason. Scores may be optimistic vs a private
  codebase, and the measured RAG gain may be smaller. A fair follow-up: test on a lesser-known repo.
- Cost ~ $0.012 and ~7 s per PR on Sonnet 5.5 at effort medium.

## Structured output (M1)

**Pydantic** - Python's zod. A class describes a data shape; Pydantic validates real data against it,
converts to/from JSON, and can produce a JSON Schema of itself. Used by FastAPI and LangGraph too.
- `Literal["a", "b"]` = TS union `"a" | "b"`; becomes an enum in JSON Schema.
- `str | None` = `string | null`.
- `Field(description=...)` does not change validation, but the description goes into the schema,
  so **the LLM reads it as an instruction**.

**`client.messages.parse(..., output_format=ReviewResult)`** - an Anthropic SDK call that returns a
validated Python object (`response.parsed_output`) instead of text. The class is used twice:
before the call (turned into a JSON Schema and sent) and after (to validate the reply).

**Who enforces the shape? (layers)**
1. SDK, on your machine: Pydantic class -> JSON Schema.
2. API server: **constrained decoding**. The LLM writes one token at a time; the schema becomes a
   grammar, and at each step tokens that would break it are blocked. So invalid JSON, missing fields
   or unknown enum values are impossible - not just unlikely.
3. The model: reads the schema and descriptions and decides the *content*.
4. SDK again: validates the JSON into the Pydantic object.

The schema guarantees **shape**, never **correctness**. A comment can be well-formed and still point
at a line that is not in the diff - so code still checks facts after the LLM (post-filter).
The older way (ask for JSON in the prompt, retry on parse errors) works mostly, not always.

**Can structured output still fail?** Not by producing wrong-shaped JSON - but the call can still
end without a valid object:
1. **Hit `max_tokens`** (`stop_reason == "max_tokens"`): output cut off mid-JSON, so incomplete.
2. **Refusal** (`stop_reason == "refusal"`): the model declines; no object.
3. **Rules the grammar can't enforce** (e.g. numeric min/max): the SDK checks them after the reply,
   so Pydantic validation can still fail.
4. **Schema the API doesn't support**: the request is rejected (400) before generation.
So the `app/llm/` wrapper checks `stop_reason` and validation errors, and fails clearly (or retries)
instead of crashing somewhere later.

**Why `app/llm/` uses `messages.create` + our own validation instead of `messages.parse()`:**
`parse()` validates *inside* the call, so a cut-off reply raises a Pydantic error and we never get the
response - no `stop_reason` (to say why) and no token counts (to log the cost). Failed calls cost
money too. So we do the same steps ourselves in a safer order: `anthropic.transform_schema()` (the
helper `parse()` uses) -> `create(output_config={"format": ...})` (same constrained decoding) ->
log usage -> check `stop_reason` -> validate with Pydantic.

## The LLM wrapper (M1, `app/llm/`)

- **One door:** every agent calls `call_structured()`; only `app/llm/claude.py` imports `anthropic`.
  Swapping provider = a new module with the same function signature.
- **Every call is logged** (success or failure) as one line in `logs/llm_calls.jsonl`: time, agent,
  model, effort, tokens, cost, latency, stop_reason, error. JSONL = one JSON object per line.
- **Cost** = tokens x price per million (table in `pricing.py`). Output tokens include thinking.
- **Thinking and effort:** Sonnet 5.5 always reasons before answering; `effort` (low ... max) sets
  how much. More effort = more (billed) thinking tokens and latency. We use `medium` for the reviewer
  and will raise it only if the evals show it misses things.
- **Generic function** `def call_structured[T: BaseModel](..., output_type: type[T]) -> tuple[T, CallLog]`
  = TypeScript `<T extends BaseModel>`: pass `ReviewResult`, get a `ReviewResult` back.

## Scoring the reviewer (M2, `evals/run_review_eval.py`, `evals/metrics.py`)

- **Recall** = bugs caught / bugs planted. "Did it find the bugs?" Ignores noise: commenting on
  everything gives 100% recall.
- **Precision** = real comments / all comments. "When it complains, is it right?" Ignores missed
  bugs: one correct comment gives 100%. They pull against each other, so measure both. Low
  precision is what makes developers ignore a bot. (Spam filter: recall = share of spam caught;
  precision = share of the spam folder that really is spam.)
- **None, not 0, when there is nothing to measure:** recall with 0 planted bugs is "n/a", not 0%,
  and dividing by 0 would crash.
- **p95 latency** = sort the run times, take the ONE run at the 95% position (by count of runs, not
  by time): 95% of runs took that long or less. The mean hides slow outliers; p95 shows the bad
  day. Nearest-rank method: `rank = ceil(0.95 * n)`, value at index `rank - 1`. With 6 runs,
  ceil(5.7) = 6, so p95 = the slowest run; it becomes useful at 20+ runs. It is computed only over
  finished runs; runs that hang hit a time limit and count as failures.
- **What we time:** two numbers. *Review latency* = the whole `review_diff()` (parse + ruff + LLM
  + post-filter). *LLM latency* = only the Claude call. M3/M4 add work outside the LLM call
  (search, tools), so the whole-pipeline number is the honest one to compare.
- **How the eval works, per PR:** reviewer gets diff + title + description only -> for each
  planted bug, comments on the same file within +-3 lines are candidates and the judge answers
  "same bug?" (first yes = caught) -> every comment that didn't catch a bug is judged "real
  problem?" -> totals -> report saved as `.md` (for people) and `.json` (for comparing runs).

### First eval run (m1-draft, 6 PRs)

- Recall 6/6, precision 10/12, ~$0.011 and ~6 s per PR (LLM only). The judge (Opus, 18 calls)
  cost more than the reviewer (Sonnet, 6 calls).
- **100% recall is not trustworthy yet:** only 6 PRs, each with one obvious single-file bug, no
  clean PRs, and marshmallow is public (the model may know it).
- **Both false alarms had the same cause:** the reviewer guessed about code outside the diff
  (`is_collection`, `_unit_to_microseconds_mapping`) and couldn't check. This is the M1 limit that
  M3 (search) and M4 (tools like `read_file`) should fix; precision is the number to watch.

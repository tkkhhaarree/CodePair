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

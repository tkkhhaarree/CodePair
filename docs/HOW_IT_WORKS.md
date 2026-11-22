# How CodePair works

Kept up to date after every milestone. Concept explanations for learning live in `LEARNING_NOTES.md`.

**Status:** M0 done (setup + first 6 review PRs). M1 (single-pass reviewer) in progress.

---

## 30-second pitch

Two AI agents work on a real Python codebase like a developer and a senior reviewer. The developer
agent takes a task and opens a PR; the reviewer agent reviews it with knowledge of the whole codebase;
they go back and forth until the reviewer approves or a round limit is hit. The key idea: **the tests
decide, not the agents' opinions** - success is measured by hidden tests neither agent has seen.

## Architecture (so far)

```
CodePair (this repo)                       marshmallow demo repo (D:\marshmallow)
  app/schemas.py   data shapes      <-->     demo-main  = marshmallow 4.4.0, untouched
  evals/prs/       review test set           pr-NN-*    = one branch per planted-bug PR
  docker-compose   Postgres + Redis
```

- **Target codebase:** marshmallow 4.4.0 (MIT, ~5k lines of source, 1192 tests, no runtime
  dependencies). Forked to https://github.com/tkkhhaarree/marshmallow, branch `demo-main` from tag 4.4.0.
- **Infra:** Docker Compose runs Postgres 16 with pgvector (for M3 search) and Redis (for the M8 queue).

## Key design decisions and trade-offs

**1. Review test set = real branches with planted bugs.**
Each PR in `evals/prs/` is a real branch on the demo repo with a realistic change (docstrings,
changelog-style notes, the author's own passing tests) that hides one bug.
- Each PR has `pr_NN.diff` (what the reviewer sees) and `pr_NN.json` (title, description, and the
  bug labels: file, line, category, description).
- Trade-off: hand-made PRs are slow to build (6 so far, target 20-30), but the labels are exact.

**2. Proof rule: every planted bug is proven, not asserted.**
A proof test (in `evals/prs/proofs/`) must FAIL on the PR branch and PASS once the fix patch is
applied. This stops us from labelling "bugs" that are really just opinions.

**3. The reviewer never sees the answer key.**
The reviewer gets only the diff, title and description. The `bugs` field is never passed to it.
Proof tests are never shown to any agent.

**4. Eval matching = code first, LLM judge second.** (Built in M2.)
Code checks file and line (within ~3 lines); an LLM judge then decides "is this the same bug?" and
"is this comment a real problem?". The judge has no codebase access, so precision may be
underestimated - a known trade-off.

**5. Code comes from git, not from the Windows folder.**
On Windows, git converts line endings to CRLF on disk. The Linux sandbox (M5) must take code from
git (`git archive` / clone), and diff files are forced to LF via `.gitattributes`.

**6. Structured output for agent messages.** (M1)
The reviewer answers in a Pydantic shape (`ReviewResult` with `ReviewComment`s), enforced by the
API's constrained decoding. The shape is guaranteed; the content is still checked by code.

**7. Model is configurable.** `REVIEWER_MODEL` in `.env`; starting with Claude Sonnet 5.5 for cost.

## Failure modes and how they are handled

| Failure | Handling |
|---|---|
| Planted bug is not actually a bug | Proof rule: test must fail on branch, pass with fix |
| Answer key leaks to the reviewer | Loader passes only title + description, never `bugs` |
| Patches fail to apply in Linux | Diffs kept LF; sandbox code taken from git |
| LLM returns malformed output | Structured output (constrained decoding) + Pydantic validation |
| LLM comments on lines not in the diff | Post-filter in code drops them (M1) |

## Likely interview questions

**Q: Why build your own test set instead of using real PRs?**
A: Real PRs don't come with a reliable list of their bugs. With planted bugs I know exactly what
should be found, so I can measure recall. Each bug is proven by a failing test.

**Q: How do you know a planted bug is real?**
A: Proof rule - a test that fails on the PR branch and passes with the fix patch.

**Q: How do you stop the evaluation from leaking answers to the model?**
A: The reviewer only receives the diff, title and description; the loader never returns the bug
labels, and proof/hidden tests are never readable by agents.

**Q: Why marshmallow?**
A: MIT-licensed, medium-sized (~5k lines), several interacting modules (fields, schema, utils), a
large existing test suite, and no runtime dependencies - easy to run in a sandbox.

**Q: How do you get reliable JSON out of an LLM?**
A: Structured output: the SDK turns a Pydantic class into a JSON Schema and the API constrains
decoding to it, so the reply always matches the shape. Correctness is still checked in code.

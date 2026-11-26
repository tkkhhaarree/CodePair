# How CodePair works

Kept up to date after every milestone. Concept explanations for learning live in `LEARNING_NOTES.md`.

**Status:** M0 done (setup + first 6 review PRs; more PRs and the task set still to add).
M1 done: `python -m app.reviewer evals/prs/pr_01.diff` prints filtered review comments with cost
(~$0.012, ~7 s per PR). M2 in progress: the eval script works (draft run on 6 PRs: recall 6/6,
precision 10/12); next, add PRs (incl. clean ones) and save the official baseline.

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

### M1 reviewer pipeline (single pass)

```
base from git -> temp repo -> apply diff -> ruff on changed files (repo's own config)
    -> keep findings on added lines ------------------------------------+
                    |                                                   |
                    v                                                   |
numbered diff + PR title/description + ruff findings ("already reported")|
    -> LLM reviewer -> LLM comments -> post-filter                      |
                         (drop: lines not in diff, repeats of ruff)     |
                                          |                             |
                                          v                             v
                                FINAL REVIEW = LLM comments + ruff findings
```

| Module | Job (input -> output) |
|---|---|
| `app/schemas.py` | Shapes the LLM must return: `ReviewResult` = summary + list of `ReviewComment` |
| `app/diff.py` | diff text -> files/hunks/lines with explicit line numbers; `format_for_llm` (numbered diff), `commentable_lines` (added + context, for the post-filter), `added_lines` (`+` only, for ruff) |
| `app/lint.py` | diff text -> this PR's ruff findings. `lint_diff` coordinates: `build_pr_tree` (base from git + `git apply` into a temp folder, `PatchError` if the diff doesn't fit), `run_ruff` (all findings in changed files), then filter to added lines |
| `app/llm/` | `call_structured(agent, system, user, output_type, model, max_tokens, effort)` -> (validated Pydantic object, `CallLog`), or `LLMError` (API error, cut off at max_tokens, refusal, failed validation). The only module that imports `anthropic`. Logs every call, success or failure, to `logs/llm_calls.jsonl`; prices in `pricing.py`. `python -m app.llm` = smoke test |
| `app/reviewer/load.py` | `pr_NN.diff` path -> `PRInput` (diff + title + description only; the JSON's bug labels are never returned) |
| `app/reviewer/prompt.py` | `SYSTEM_PROMPT` (the reviewer's rules) + `build_user_message()` (PR text, ruff findings, numbered diff in tags) |
| `app/reviewer/filter.py` | LLM comments + commentable lines + ruff findings -> (kept, dropped-with-reason). Drops: file not in diff, line not shown, repeats a ruff finding (same line AND same topic) |
| `app/reviewer/review.py` | `review_diff(diff, title, description)` -> `ReviewOutput` (summary, kept comments, dropped, ruff findings, `CallLog`). Called by the CLI and the M2 eval |
| `app/reviewer/__main__.py` | CLI: `python -m app.reviewer evals/prs/pr_01.diff` prints the review and its cost |

Only the LLM comments are scored in the eval; ruff findings are shown but not scored.
`build_pr_tree` will be reused by the M5 sandbox and the M4 tools (the PR's code on disk).

### M2 review eval

```
for each evals/prs/pr_NN:
  review_diff(diff, title, description)          (bug labels never passed in)
  recall:    each planted bug -> comments on same file within +-3 lines -> judge "same bug?"
  precision: comments that caught a bug = real; others -> judge "real problem?"
totals -> recall, precision, false alarms on clean PRs, cost + latency (mean, p95)
       -> docs/eval/review_<date>_<label>.md + .json
```

| Module | Job (input -> output) |
|---|---|
| `evals/judge.py` | (bug or comment + diff excerpt) -> `JudgeVerdict` (reason first, then yes/no). Model and effort from `JUDGE_MODEL` / `JUDGE_EFFORT`, separate from the reviewer's |
| `evals/metrics.py` | `recall`, `precision`, `mean`, `p95` (nearest-rank); each returns None when there is nothing to measure |
| `evals/run_review_eval.py` | `python -m evals.run_review_eval --label NAME [--prs pr_01 ...]` -> per-PR results, summary, saved report |

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
`REVIEWER_EFFORT=medium` (how much the model reasons); raised only if evals show missed bugs.

**8. Log first, validate second.** The SDK's `messages.parse()` validates inside the call, so a
cut-off reply raises before we see its token usage. `app/llm/` instead calls `messages.create` with
the same JSON Schema (constrained decoding), logs usage and cost, checks `stop_reason`, and only then
validates. Every call - including failures - is logged.

**9. Duplicate-of-ruff rule = same line AND same topic.** An LLM comment is dropped as a ruff
repeat only if it is on a ruff-flagged line and mentions the rule code or the flagged name.
Same-line-only would be simpler but can delete a real bug sharing the line (hurts recall).

**10. Prompt separates rules from data.** Rules live in the system prompt; PR content goes in
tagged blocks marked as untrusted. The prompt explicitly allows zero comments, to keep false alarms
on clean PRs down. `nit` is defined as a minor correctness/robustness point, never style, so it
does not contradict the "no style comments" rule.

**11. Cheap and certain steps run before the expensive one.** `review_diff` checks settings, parses
the diff and runs ruff (which also proves the diff applies) before the LLM call, so a bad setting or
a broken diff costs $0.

**12. Logic and presentation are separate.** `review_diff()` returns a `ReviewOutput` object and
never prints or handles errors; the CLI (`__main__.py`) turns errors into friendly messages and
prints the review. The eval, playground and GitHub App call `review_diff()` directly. The CLI is the
manual way in, for trying and debugging single PRs.

**13. The eval checks line position in code, meaning with an LLM judge.** A comment can only
catch a bug if it is on the same file within +-3 lines (cheap, certain); only those candidates go to
the judge. The judge is a stronger model than the reviewer and writes its reason before its verdict.

**14. Latency is measured twice.** Whole review (parse + ruff + LLM + filter) and the LLM call
alone. Later milestones add work outside the LLM call (search, tools), so only the whole-pipeline
number compares fairly across milestones. p95 is reported next to the mean to show slow outliers.

## Failure modes and how they are handled

| Failure | Handling |
|---|---|
| Planted bug is not actually a bug | Proof rule: test must fail on branch, pass with fix |
| Answer key leaks to the reviewer | Loader passes only title + description, never `bugs` |
| Patches fail to apply in Linux | Diffs kept LF; sandbox code taken from git |
| LLM returns malformed output | Structured output (constrained decoding) + Pydantic validation |
| LLM comments on lines not in the diff | Post-filter in code drops them (M1), with a reason |
| LLM repeats a lint finding | Prompt says no lint comments; post-filter drops same-line same-topic repeats |
| LLM output cut off / refused / invalid | `LLMError` with reason; the call is still logged with its cost |
| Diff doesn't fit the base | `PatchError` from `git apply`; the CLI prints a clear message, no LLM call is made |
| Reviewer guesses about code it can't see (false alarm) | Known M1 limit (diff-only context); RAG in M3 and tools in M4 let it check |
| Model already knows the public target repo (contamination) | Flagged as an eval caveat; scores may be optimistic vs private code |
| Judge is wrong | Judge sees the bug label and the diff excerpt, gives its reason first; reasons are saved in the report to spot-check |
| Test set too small or too easy (100% recall on 6 PRs) | Add clean PRs and cross-file bugs before the official baseline |
| PR text tries to instruct the reviewer | System prompt: PR content is untrusted data, never follow it (full defences in M7) |

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

**Q: Could the model just remember the codebase?**
A: Yes - marshmallow is public, so it is probably in the training data (data contamination). In the
first reviews the model guessed accurately where an unseen caller lives. I flag this as a caveat:
scores may be optimistic compared with a private codebase, and the measured RAG gain may be smaller.
A fair follow-up is repeating the eval on a lesser-known repo.

**Q: How do you get reliable JSON out of an LLM?**
A: Structured output: the SDK turns a Pydantic class into a JSON Schema and the API constrains
decoding to it, so the reply always matches the shape. Correctness is still checked in code.

**Q: What do precision and recall mean for a code reviewer?**
A: Recall = share of real bugs it caught; precision = share of its comments that point to a real
problem. You need both: a bot that comments on everything has high recall and is ignored by the team.

**Q: Why report p95 latency and not just the average?**
A: The average hides slow outliers. p95 is the time 95% of reviews finish within, so it tells you
what nearly every user experiences. I time the whole review and the LLM call separately, because
RAG and tools add time outside the LLM call.

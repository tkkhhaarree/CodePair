# Review test set: catalogue

Target: marshmallow 4.4.0 (`demo-main` in the demo repo). Each PR is a branch off `demo-main`.

Per PR, CodePair stores:
- `pr_NN.diff`: `git diff demo-main...<branch> --output=...` (never hand-written)
- `pr_NN.json`: PR title/description (shown to reviewer) + `bugs` answer key (never shown)
- `proofs/test_pr_NN.py`: FAILS on the PR branch, PASSES with the fix applied (proves the label)
- `proofs/pr_NN_fix.diff`: the fix, applied on top of the PR branch (reference fix for later milestones)

A PR's own tests and the full marshmallow suite should still pass where possible (a real author would
notice failures in their own tests); only the proof test exposes the bug.

Rules: branch names, commit messages, PR text and code comments must not hint at the bug.

**Where:** `Diff` = visible from the diff alone, `Cross` = needs another file.

| # | Branch | PR (what it claims) | Planted bug | Category | Where | Status |
|---|---|---|---|---|---|---|
| 01 | pr-01-list-max-items | Add `max_items` to `fields.List` | `>=` rejects exactly max_items | off-by-one | Diff | **done** |
| 02 | pr-02-range-cleanup | Tidy `validate.Range` inclusive checks | max-inclusive flipped | logic | Diff | todo |
| 03 | pr-03-get-value-index | `utils.get_value`: list indexes in dotted keys | IndexError instead of default | error-handling | Diff | todo |
| 04 | pr-04-set-value-sep | `utils.set_value`: add `sep` | `sep` before `value`; `schema.py:689` not updated | signature-break | Cross | **done** |
| 05 | pr-05-nested-cache | `Nested`: cache resolved schema | class-level cache shared across `only=` | shared-state | Diff | todo |
| 06 | pr-06-merge-errors | `merge_errors`: simplify list merge | mutates caller's list | aliasing | Cross | todo |
| 07 | pr-07-store-error-args | `ErrorStore.store_error`: `index` 2nd | positional callers in `schema.py` swapped | signature-break | Cross | todo |
| 08 | pr-08-call-and-store | `_call_and_store`: more robust | `except Exception` hides user bugs | error-handling | Diff | todo |
| 09 | pr-09-decimal-places-int | `Decimal`: store `places` as int (introspection) | `if self.places:` skips rounding for places=0 | truthiness | Diff | **done** |
| 10 | pr-10-boolean-enabled-disabled | `Boolean`: accept enabled/disabled | lowercase "disabled" in truthy set | logic | Diff | **done** |
| 11 | pr-11-email-plus | `validate.Email`: plus-addressing | `$` vs `\Z` allows trailing newline | security | Diff | todo |
| 12 | pr-12-url-schemes | `validate.URL`: custom schemes | `javascript:` passes by default | security | Diff | todo |
| 13 | pr-13-timedelta-int-micros | `TimeDelta`: deserialize via integer microseconds | `int()` truncates instead of rounding | rounding | Diff | **done** |
| 14 | pr-14-mapping-key-order | `Mapping`: validate keys first | key errors overwrite value errors | error-handling | Diff | todo |
| 15 | pr-15-enum-case-insensitive | `Enum`: `case_insensitive` | `.lower()` on non-str input crashes (500 not 400) | type-check | Diff | **done** |
| 16 | pr-16-deserialize-partial | `Field.deserialize`: add `partial` | positional insert; `schema.py` caller shifts | signature-break | Cross | todo |
| 17 | pr-17-registry-first-match | `get_class`: first match on duplicates | `Nested` silently picks wrong schema | risky-change | Cross | todo |
| 18 | pr-18-hooks-dict | `set_hook`: dict storage | method with two hooks loses one | data-loss | Cross | todo |
| 19 | pr-19-is-collection-iterable | `is_collection`: any iterable | strings become collections (`fields.py:771`, `schema.py:420`) | behaviour-change | Cross | todo |
| 20 | pr-20-naive-dt-timezone | `NaiveDateTime`: `timezone` option | strips tzinfo without converting | logic | Diff | todo |

Clean PRs (`clean: true`, no bugs, measure false alarms):

| # | Branch | PR | Status |
|---|---|---|---|
| C1 | pr-c1-oneof-hints | Type hints + docstrings for `validate.OneOf` | todo |
| C2 | pr-c2-range-format-helper | Refactor `Range._format_error` (no behaviour change) | todo |
| C3 | pr-c3-string-strip | `fields.String(strip=True)`, correct + tested | todo |
| C4 | pr-c4-ensure-text-msg | Clearer error in `utils.ensure_text_type` | todo |
| C5 | pr-c5-ip-interface-exports | Export `IPv4Interface`/`IPv6Interface`, docs fix | todo |

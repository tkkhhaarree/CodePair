"""Review eval: run the reviewer on every PR in evals/prs/ and score it.

    python -m evals.run_review_eval --label m1-baseline
    python -m evals.run_review_eval --label try --prs pr_01 pr_04     (only some PRs)

Per PR:
  1. review_diff() -> comments (the reviewer sees only diff + title + description)
  2. recall:    for each planted bug, comments on the same file within +-LINE_TOLERANCE lines
                are candidates; the judge decides "same bug?". Caught if any says yes.
  3. precision: a comment that matched a bug is real; any other comment goes to the judge
                ("real problem?").
Then totals -> recall, precision, false alarms on clean PRs, cost and latency (mean, p95),
printed and saved to docs/eval/review_<date>_<label>.md and .json.
"""

import argparse
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from app.diff import format_for_llm, parse_diff
from app.lint import PatchError
from app.llm import LLMError
from app.reviewer.load import load_pr
from app.reviewer.review import review_diff
from evals.judge import _settings as judge_settings
from evals.judge import judge_real_problem, judge_same_bug
from evals.metrics import mean, p95, precision, recall

PRS_DIR = Path("evals/prs")
REPORT_DIR = Path("docs/eval")
LINE_TOLERANCE = 3


@dataclass
class CommentResult:
    file: str
    line: int
    severity: str
    message: str
    real: bool  # judged a real problem (or matched a planted bug)
    matched_bug: int | None  # index of the planted bug it caught, if any
    judge_reason: str


@dataclass
class PRResult:
    pr_id: str
    clean: bool
    bugs_total: int = 0
    bugs_caught: int = 0
    comments: list[CommentResult] = field(default_factory=list)
    dropped: int = 0  # comments removed by the reviewer's post-filter
    reviewer_cost: float = 0.0
    review_latency: float = 0.0  # whole review_diff(): parse + ruff + LLM + post-filter
    llm_latency: float = 0.0  # only the Claude call inside it
    judge_cost: float = 0.0
    model: str = ""
    effort: str = ""
    error: str | None = None


def evaluate_pr(meta_path: Path) -> PRResult:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    bugs = meta.get("bugs", [])
    result = PRResult(pr_id=meta["id"], clean=meta.get("clean", False), bugs_total=len(bugs))

    # 1. The reviewer. load_pr hands it only diff + title + description.
    pr = load_pr(meta_path.with_suffix(".diff"))
    start = time.perf_counter()  # a stopwatch: seconds, only differences are meaningful
    try:
        out = review_diff(pr.diff, pr.title, pr.description)
    except (PatchError, LLMError) as e:
        result.error = f"reviewer: {type(e).__name__}: {e}"
        if isinstance(e, LLMError):
            result.reviewer_cost = e.log.cost_usd or 0.0
        return result
    result.reviewer_cost = out.log.cost_usd or 0.0
    result.review_latency = time.perf_counter() - start
    result.llm_latency = out.log.latency_s
    result.model, result.effort = out.log.model, out.log.effort
    result.dropped = len(out.dropped)

    files = parse_diff(pr.diff)
    matched: dict[int, tuple[int, str]] = {}  # comment index -> (bug index, judge reason)

    try:
        # 2. Recall: does any nearby comment describe each planted bug?
        for bug_i, bug in enumerate(bugs):
            candidates = [
                i for i, c in enumerate(out.comments)
                if c.file == bug["file"] and abs(c.line - bug["line"]) <= LINE_TOLERANCE
                and i not in matched  # one comment can catch only one bug
            ]
            for i in candidates:
                verdict, log = judge_same_bug(bug, out.comments[i], files)
                result.judge_cost += log.cost_usd or 0.0
                if verdict.yes:
                    matched[i] = (bug_i, verdict.reason)
                    result.bugs_caught += 1
                    break  # this bug is caught; no need to judge more candidates

        # 3. Precision: is each comment a real problem?
        numbered = format_for_llm(files)
        for i, c in enumerate(out.comments):
            if i in matched:
                bug_i, reason = matched[i]
                real, matched_bug = True, bug_i
            else:
                verdict, log = judge_real_problem(c, pr.title, pr.description, numbered)
                result.judge_cost += log.cost_usd or 0.0
                real, matched_bug, reason = verdict.yes, None, verdict.reason
            result.comments.append(
                CommentResult(c.file, c.line, c.severity, c.message, real, matched_bug, reason)
            )
    except LLMError as e:
        result.error = f"judge: {e}"
    return result


def summarise(results: list[PRResult]) -> dict:
    ok = [r for r in results if r.error is None]
    bug_prs = [r for r in ok if not r.clean]
    clean_prs = [r for r in ok if r.clean]
    all_comments = [c for r in ok for c in r.comments]
    return {
        "prs_run": len(results),
        "prs_failed": len(results) - len(ok),
        "bugs_total": sum(r.bugs_total for r in bug_prs),
        "bugs_caught": sum(r.bugs_caught for r in bug_prs),
        "recall": recall(sum(r.bugs_caught for r in bug_prs), sum(r.bugs_total for r in bug_prs)),
        "comments_total": len(all_comments),
        "comments_real": sum(c.real for c in all_comments),  # True counts as 1
        "precision": precision(sum(c.real for c in all_comments), len(all_comments)),
        "clean_prs": len(clean_prs),
        "false_alarms_on_clean": sum(not c.real for r in clean_prs for c in r.comments),
        "comments_dropped_by_filter": sum(r.dropped for r in ok),
        "reviewer_cost_mean": mean([r.reviewer_cost for r in ok]),
        "reviewer_cost_p95": p95([r.reviewer_cost for r in ok]),
        "review_latency_mean": mean([r.review_latency for r in ok]),
        "review_latency_p95": p95([r.review_latency for r in ok]),
        "llm_latency_mean": mean([r.llm_latency for r in ok]),
        "llm_latency_p95": p95([r.llm_latency for r in ok]),
        "judge_cost_total": sum(r.judge_cost for r in results),
        "total_cost": sum(r.reviewer_cost + r.judge_cost for r in results),
    }


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.0%}"  # 0.75 -> "75%"


def _num(x: float | None, fmt: str) -> str:
    return "n/a" if x is None else format(x, fmt)


def render_markdown(label: str, results: list[PRResult], s: dict) -> str:
    first_ok = next((r for r in results if r.error is None), None)  # first match, or None
    judge_model, judge_effort = judge_settings()
    lines = [
        f"# Review eval: {label} ({date.today().isoformat()})",
        "",
        (  # two strings side by side inside ( ) are joined into one
            f"Reviewer: {first_ok.model if first_ok else '?'} "
            f"(effort {first_ok.effort if first_ok else '?'})  |  "
            f"Judge: {judge_model} (effort {judge_effort})  |  Line tolerance: +-{LINE_TOLERANCE}"
        ),
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| PRs run (failed) | {s['prs_run']} ({s['prs_failed']}) |",
        f"| Bug recall | {_pct(s['recall'])} ({s['bugs_caught']}/{s['bugs_total']}) |",
        f"| Precision | {_pct(s['precision'])} ({s['comments_real']}/{s['comments_total']} comments real) |",
        f"| False alarms on clean PRs | {s['false_alarms_on_clean']} across {s['clean_prs']} clean PRs |",
        f"| Comments dropped by post-filter | {s['comments_dropped_by_filter']} |",
        f"| Reviewer cost per PR (mean / p95) | ${_num(s['reviewer_cost_mean'], '.4f')} / ${_num(s['reviewer_cost_p95'], '.4f')} |",
        f"| Review latency per PR, whole pipeline (mean / p95) | {_num(s['review_latency_mean'], '.1f')}s / {_num(s['review_latency_p95'], '.1f')}s |",
        f"| ...of which the LLM call (mean / p95) | {_num(s['llm_latency_mean'], '.1f')}s / {_num(s['llm_latency_p95'], '.1f')}s |",
        f"| Judge cost (total) | ${s['judge_cost_total']:.4f} |",
        f"| Total cost of this run | ${s['total_cost']:.4f} |",
        "",
        "## Per PR",
        "",
        "| PR | Clean | Bugs caught | Comments (real) | Reviewer $ | Latency (LLM) | Error |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        real = sum(c.real for c in r.comments)
        lines.append(
            f"| {r.pr_id} | {'yes' if r.clean else 'no'} | {r.bugs_caught}/{r.bugs_total} | "
            f"{len(r.comments)} ({real}) | {r.reviewer_cost:.4f} | {r.review_latency:.1f}s ({r.llm_latency:.1f}s) | "
            f"{r.error or ''} |"
        )
    lines += ["", "## Comments", ""]
    for r in results:
        for c in r.comments:
            tag = f"caught bug {c.matched_bug}" if c.matched_bug is not None else (
                "real" if c.real else "NOT real"
            )
            lines.append(f"- **{r.pr_id}** `{c.file}:{c.line}` [{c.severity}] {tag}: {c.judge_reason}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Score the reviewer on evals/prs/.")
    parser.add_argument("--label", required=True, help="name of this run, e.g. m1-baseline")
    parser.add_argument("--prs", nargs="*", help="only these PR ids, e.g. pr_01 pr_04")
    args = parser.parse_args()

    meta_paths = sorted(PRS_DIR.glob("pr_*.json"))
    if args.prs:
        meta_paths = [p for p in meta_paths if p.stem in args.prs]  # .stem = name without .json

    results = []
    for path in meta_paths:
        print(f"{path.stem} ...", end=" ", flush=True)
        r = evaluate_pr(path)
        status = r.error or f"bugs {r.bugs_caught}/{r.bugs_total}, comments {len(r.comments)}"
        print(status)
        results.append(r)

    s = summarise(results)
    report = render_markdown(args.label, results, s)
    print("\n" + report)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    base = REPORT_DIR / f"review_{date.today().isoformat()}_{args.label}"
    base.with_suffix(".md").write_text(report, encoding="utf-8")
    raw = {"label": args.label, "summary": s, "prs": [asdict(r) for r in results]}
    base.with_suffix(".json").write_text(json.dumps(raw, indent=2), encoding="utf-8")
    print(f"saved {base}.md and .json")


if __name__ == "__main__":
    main()

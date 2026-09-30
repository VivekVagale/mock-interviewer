"""Check whether the grader can be trusted.

Run:  python -m src.evaluate --model qwen3:8b
      python -m src.evaluate --model llama3.2:3b --repeats 3

Uses eval/graded_answers.json: for 12 questions, one strong, one medium, one
weak, one "waffle" answer (long and confident, but missing the key points) and
one "paraphrase" answer (complete and correct, but avoiding the rubric's words).
Five checks:
  1. ordering: strong > medium > weak on each question
  2. Spearman correlation between intended quality (2/1/0) and score
  3. waffle: does fluent filler score like a weak answer, not a good one?
  4. paraphrase: does a correct answer in different words score near strong,
     or is the grader just matching keywords?
  5. consistency: re-grade at temperature 0.7 and measure the score spread
"""

import argparse
import json
import statistics
import time
from pathlib import Path

from .grader import grade
from .questions import by_id

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "eval" / "graded_answers.json"
RESULTS = ROOT / "results"
LEVEL = {"strong": 2, "medium": 1, "weak": 0}


def spearman(xs: list[float], ys: list[float]) -> float:
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2  # ties share the average rank
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    return cov / ((sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3:8b")
    ap.add_argument("--repeats", type=int, default=3, help="extra gradings at temperature 0.7 for consistency")
    args = ap.parse_args()

    items = json.loads(EVAL.read_text(encoding="utf-8"))["items"]
    rows, spreads, ordered, times, failures = [], [], 0, [], 0

    def safe_grade(q, answer, **kw) -> float:
        """A reply that is not valid JSON (e.g. cut off at the length cap) is what a user
        would see as an error, so it is counted as a failure and scores 0."""
        nonlocal failures
        try:
            return grade(q, answer, model=args.model, **kw)["score"]
        except (ValueError, KeyError):   # json.JSONDecodeError is a ValueError
            failures += 1
            return 0.0

    for item in items:
        q = by_id(item["id"])
        scores = {}
        for kind, answer in item["answers"].items():
            t = time.time()
            scores[kind] = safe_grade(q, answer)
            times.append(time.time() - t)
        for kind in ("strong", "medium"):
            reps = [safe_grade(q, item["answers"][kind], temperature=0.7) for _ in range(args.repeats)]
            spreads.append(statistics.pstdev(reps + [scores[kind]]))
        ok = scores["strong"] > scores["medium"] > scores["weak"]
        ordered += ok
        rows.append({"id": item["id"], **scores, "ordered": ok})
        print(f"{item['id']:22} strong {scores['strong']:4}  para {scores.get('paraphrase', '-'):4}  "
              f"medium {scores['medium']:4}  weak {scores['weak']:4}  waffle {scores['waffle']:4}  "
              f"{'ok' if ok else 'WRONG ORDER'}")

    levels = [LEVEL[k] for r in rows for k in LEVEL]
    graded = [r[k] for r in rows for k in LEVEL]
    kinds = [k for k in ("strong", "paraphrase", "medium", "weak", "waffle") if k in rows[0]]
    mean = {k: round(statistics.mean(r[k] for r in rows), 2) for k in kinds}
    waffle_below_medium = sum(r["waffle"] < r["medium"] for r in rows)
    out = {
        "model": args.model,
        "n_questions": len(rows),
        "ordering_accuracy": round(ordered / len(rows), 3),
        "spearman": round(spearman(levels, graded), 3),
        "mean_score": mean,
        "waffle_below_medium": f"{waffle_below_medium}/{len(rows)}",
        "paraphrase_within_2_of_strong": (f"{sum(r['strong'] - r['paraphrase'] <= 2 for r in rows)}/{len(rows)}"
                                          if "paraphrase" in rows[0] else None),
        "mean_score_std_on_regrade": round(statistics.mean(spreads), 2),
        "seconds_per_grade": round(statistics.mean(times), 1),
        "failed_replies": f"{failures}/{len(times) + len(spreads) * args.repeats}",
        "rows": rows,
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"grader_{args.model.replace(':', '_').replace('/', '_')}.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()

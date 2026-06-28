"""Eval harness - confusion matrix + per-class metrics + accuracy.

CI gates on 100% accuracy on the bundled fixtures. For your own
engagement, lower the threshold and gate on per-class F1 (e.g.,
"customer_complaint F1 must stay above 0.85") - the realistic ask
once your classes have noisier data.

Usage:
    python evals/run.py
    DOC_CLASSIFIER_BACKEND=llm python evals/run.py
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from doc_classifier.classifier import Classifier  # noqa: E402


FIXTURES = ROOT / "fixtures"


def load_cases() -> list[dict]:
    with open(Path(__file__).parent / "golden.json") as f:
        return json.load(f)["cases"]


def run_case(clf: Classifier, case: dict) -> dict:
    text = (FIXTURES / case["fixture"]).read_text(encoding="utf-8")
    r = clf.classify(text)
    return {
        "id": case["id"],
        "expected": case["expected"],
        "actual": r.label,
        "confidence": r.confidence,
        "passed": r.label == case["expected"],
    }


def compute_metrics(results: list[dict]) -> dict:
    """Per-class precision, recall, F1 + overall accuracy."""
    # Confusion structure: per expected class, count of correct + incorrect.
    classes: set[str] = set()
    for r in results:
        classes.add(r["expected"])
        classes.add(r["actual"])

    tp: dict[str, int] = defaultdict(int)
    fp: dict[str, int] = defaultdict(int)
    fn: dict[str, int] = defaultdict(int)
    for r in results:
        if r["expected"] == r["actual"]:
            tp[r["expected"]] += 1
        else:
            fn[r["expected"]] += 1
            fp[r["actual"]] += 1

    per_class = {}
    for c in sorted(classes):
        p = tp[c] / (tp[c] + fp[c]) if (tp[c] + fp[c]) > 0 else 0.0
        rec = tp[c] / (tp[c] + fn[c]) if (tp[c] + fn[c]) > 0 else 0.0
        f1 = 2 * p * rec / (p + rec) if (p + rec) > 0 else 0.0
        per_class[c] = {"precision": round(p, 3),
                        "recall": round(rec, 3),
                        "f1": round(f1, 3),
                        "support": tp[c] + fn[c]}

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    return {"accuracy": round(passed / total, 3) if total else 0.0,
            "passed": passed, "total": total,
            "per_class": per_class}


def main() -> int:
    cases = load_cases()
    clf = Classifier()
    print(f"Running {len(cases)} eval cases against backend={clf.backend}\n")

    results = [run_case(clf, c) for c in cases]
    metrics = compute_metrics(results)

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  {status}  {r['id']:25s}  expected={r['expected']:18s}  actual={r['actual']:18s}  conf={r['confidence']:.2f}")

    print(f"\nAccuracy: {metrics['accuracy']:.0%}  ({metrics['passed']}/{metrics['total']})\n")
    print("Per-class metrics:")
    print(f"  {'class':22s}  {'precision':>9s}  {'recall':>7s}  {'F1':>5s}  {'support':>7s}")
    for cls, m in metrics["per_class"].items():
        print(f"  {cls:22s}  {m['precision']:>9.2f}  {m['recall']:>7.2f}  {m['f1']:>5.2f}  {m['support']:>7d}")

    return 0 if metrics["accuracy"] == 1.0 else 1


if __name__ == "__main__":
    sys.exit(main())

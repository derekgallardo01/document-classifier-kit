"""Production inbox router: classify a directory of documents, route to queues.

The pattern: a SharePoint document library / Google Drive folder / email
attachment dump fills up with mixed documents. This script:

  1. Walks the input directory
  2. Reads each document as text (.txt files; for PDFs pair with pdf-extraction-kit)
  3. Classifies each via the kit's classifier
  4. Routes to a folder per queue (./output/<queue>/) - simulates how a real
     deployment would push to Azure Service Bus / a Postgres queue table
  5. Writes a per-document decision log (JSONL) with the rationale

Default runs against the bundled .txt fixtures so it shows behaviour with
no setup. Point --input at a real directory to route your own documents.

Usage:
    python examples/inbox_router.py
    python examples/inbox_router.py --input ./incoming --output ./routed --log decisions.jsonl
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from doc_classifier.classifier import Classifier, route  # noqa: E402
from doc_classifier.schema import default_catalog  # noqa: E402


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def route_directory(input_dir: Path, output_dir: Path,
                     review_threshold: float = 0.45) -> list[dict]:
    """Route every .txt file in input_dir to a per-queue subfolder in output_dir."""
    clf = Classifier(review_threshold=review_threshold)
    decisions: list[dict] = []

    # Clean output dir for the demo
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for doc_path in sorted(input_dir.glob("*.txt")):
        text = doc_path.read_text(encoding="utf-8")
        result = clf.classify(text)
        decision = route(result, clf.catalog)

        # "Push to queue" = copy into the per-queue subfolder
        queue_dir = output_dir / decision.queue
        queue_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(doc_path, queue_dir / doc_path.name)

        decisions.append({
            "file": doc_path.name,
            "label": result.label,
            "confidence": result.confidence,
            "candidates_top3": [(n, round(s, 2)) for n, s in result.candidates[:3]],
            "evidence": result.evidence[:5],  # cap at 5 keywords
            "queue": decision.queue,
            "sla_hours": decision.sla_hours,
            "review_required": decision.review_required,
            "handoff_reason": decision.handoff_reason,
        })

    return decisions


def write_decision_log(decisions: list[dict], path: Path) -> None:
    """Append one JSON line per decision to the audit log."""
    with open(path, "w", encoding="utf-8") as f:
        for d in decisions:
            f.write(json.dumps(d) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inbox router: classify + route documents.")
    parser.add_argument("--input", default=str(FIXTURES),
                        help="Directory of documents (.txt). Default: bundled fixtures.")
    parser.add_argument("--output", default="./routed",
                        help="Output directory; one subfolder per queue.")
    parser.add_argument("--log", default="./decisions.jsonl",
                        help="Where to write the decision log (JSONL).")
    parser.add_argument("--threshold", type=float, default=0.45,
                        help="Confidence below this routes to human_review.")
    parser.add_argument("--json", action="store_true",
                        help="Emit the decisions as JSON to stdout (skip filesystem routing).")
    args = parser.parse_args(argv)

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    log_path = Path(args.log)

    if not input_dir.exists():
        print(f"Input directory {input_dir} not found.", file=sys.stderr)
        return 1

    decisions = route_directory(input_dir, output_dir, review_threshold=args.threshold)
    write_decision_log(decisions, log_path)

    if args.json:
        print(json.dumps(decisions, indent=2))
        return 0

    # Human-readable summary
    print(f"\nRouted {len(decisions)} document(s) from {input_dir} -> {output_dir}\n")
    queue_counts: dict[str, int] = {}
    for d in decisions:
        mark = "[REVIEW]" if d["review_required"] else "[ROUTE] "
        print(f"  {mark} {d['file']:30s} -> {d['label']:22s}  "
              f"(conf={d['confidence']:.2f}) -> {d['queue']}")
        queue_counts[d["queue"]] = queue_counts.get(d["queue"], 0) + 1

    print(f"\n  Queue distribution:")
    for q, n in sorted(queue_counts.items(), key=lambda kv: -kv[1]):
        print(f"    {q:25s} {n}")
    print(f"\n  Audit log: {log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

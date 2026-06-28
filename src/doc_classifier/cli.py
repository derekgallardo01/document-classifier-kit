"""CLI - classify documents, route them, list the catalog.

Usage:
    doc-classifier classify <file>
    doc-classifier classify <file> --json
    doc-classifier demo                 # run all fixtures
    doc-classifier list-classes
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .classifier import Classifier, route
from .schema import default_catalog


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def cmd_list_classes(_args) -> int:
    cat = default_catalog()
    print(f"Catalog has {len(cat.classes)} classes:\n")
    for c in cat.classes:
        print(f"  {c.name:18s} -> queue '{c.queue}'  (SLA: {c.sla_hours}h)")
        print(f"    {c.description}")
        print(f"    keywords: {c.keywords}\n")
    return 0


def cmd_classify(args) -> int:
    path = Path(args.path)
    text = _read_text(path)
    clf = Classifier()
    result = clf.classify(text)
    decision = route(result, clf.catalog)

    out = {
        "doc": path.name,
        "classification": result.to_dict(),
        "routing": asdict(decision),
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0

    print(f"\n  {path.name}")
    print(f"    label:      {result.label}")
    print(f"    confidence: {result.confidence:.2f}")
    print(f"    backend:    {result.backend}")
    if result.evidence:
        print(f"    evidence:   {result.evidence}")
    print(f"    top 3:      {[(n, round(s,2)) for n, s in result.candidates]}")
    print(f"    -> queue:   {decision.queue}  (SLA {decision.sla_hours}h)")
    if decision.review_required:
        print(f"    review:     {decision.handoff_reason}")
    return 0


def cmd_demo(args) -> int:
    fixtures_dir = Path(__file__).resolve().parents[2] / "fixtures"
    clf = Classifier()
    results = []
    for fixture in sorted(fixtures_dir.glob("*.txt")):
        text = _read_text(fixture)
        r = clf.classify(text)
        d = route(r, clf.catalog)
        results.append({"doc": fixture.name,
                        "classification": r.to_dict(),
                        "routing": asdict(d)})
        if not args.json:
            mark = "📋" if d.review_required else "✓"
            mark = "[REVIEW]" if d.review_required else "[ROUTE]"
            print(f"  {mark} {fixture.name:30s} -> {r.label:18s} ({r.confidence:.2f}) -> {d.queue}")

    if args.json:
        print(json.dumps({"backend": clf.backend, "runs": results}, indent=2))
    else:
        review_count = sum(1 for x in results if x["routing"]["review_required"])
        print(f"\n  Backend: {clf.backend}.  "
              f"{len(results) - review_count}/{len(results)} routed confidently; "
              f"{review_count} sent to human_review.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Document classifier CLI.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list-classes")

    p_clf = sub.add_parser("classify")
    p_clf.add_argument("path")
    p_clf.add_argument("--json", action="store_true")

    p_demo = sub.add_parser("demo")
    p_demo.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    handlers = {"list-classes": cmd_list_classes,
                "classify": cmd_classify,
                "demo": cmd_demo}
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())

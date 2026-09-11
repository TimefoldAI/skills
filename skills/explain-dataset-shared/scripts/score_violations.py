#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Shows violated constraints with sample justifications.
Works for any model defined in model_config.py, selected via --model.

Reads the API key from the TIMEFOLD_API_KEY environment variable. It accepts no --api-key
argument, so the key stays out of the command line.

Usage:
    python score_violations.py --model employee-shift-scheduling --dataset-id ID [--type hard|medium|soft]
    python score_violations.py --model field-service-routing --dataset-id ID --constraint "unassigned"
    python score_violations.py --model pickup-delivery-routing --dataset-id ID --type hard
"""
import argparse
import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

from timefold_api import model_api_get, parse_score, score_sort_key, constraint_type, add_common_args, resolve_args, run
from model_config import get_config


def format_justification(j):
    if isinstance(j, str):
        return j
    if "description" in j:
        return j["description"]
    parts = []
    for k, v in j.items():
        if isinstance(v, (str, int, float, bool)):
            parts.append(f"{k}={v}")
        elif isinstance(v, list) and all(isinstance(x, (str, int)) for x in v):
            parts.append(f"{k}=[{', '.join(str(x) for x in v)}]")
    return ", ".join(parts) if parts else str(j)


def main():
    p = argparse.ArgumentParser(description="Show violated constraints with sample justifications")
    add_common_args(p)
    p.add_argument("--samples", type=int, default=10,
                   help="Sample justifications per constraint (default: 10)")
    p.add_argument("--type", choices=["hard", "medium", "soft", "all"], default="all")
    p.add_argument("--constraint", metavar="NAME",
                   help="Show all justifications for a constraint (substring match)")
    args = p.parse_args()
    base, key, did, _ = resolve_args(args)
    cfg = get_config(args.model)
    cp = cfg["collection_path"]

    print(f"Fetching score analysis for {did}...")
    score_data = model_api_get(base, f"{cp}/{did}/score-analysis", key,
                         params={"includeJustifications": "true"})

    constraints = score_data.get("constraints", [])
    if args.constraint:
        constraints = [c for c in constraints if args.constraint.lower() in c["name"].lower()]
        if not constraints:
            print(f"No constraint found matching '{args.constraint}'")
            return
    else:
        constraints = [c for c in constraints if c["matchCount"] > 0]

    if args.type != "all":
        constraints = [c for c in constraints if constraint_type(c["weight"]) == args.type]

    constraints = sorted(constraints, key=lambda c: score_sort_key(c["score"]))

    print(f"Score: {score_data.get('score', '?')}")
    filter_note = f" of type '{args.type}'" if args.type != "all" else ""
    print(f"Showing {len(constraints)} violated constraint(s){filter_note}.")
    print()

    if not constraints:
        print("✓  No violations found for the given filter.")
        return

    for c in constraints:
        ctype = constraint_type(c["weight"]).upper()
        s = parse_score(c["score"])
        total = s["hard"] or s["medium"] or s["soft"]
        print(f"[{ctype}] {c['name']}")
        print(f"  Score impact : {total:+,}  |  Violations: {c['matchCount']}")

        matches = c.get("matches", [])
        n = len(matches) if args.constraint else min(args.samples, len(matches))
        omitted = len(matches) - n

        if n > 0:
            print(f"  Examples ({n} of {len(matches)}):")
            for match in matches[:n]:
                line = format_justification(match.get("justification", {}))
                if len(line) > 140:
                    line = line[:137] + "..."
                print(f"    • {line}")
        if omitted > 0:
            print(f"    ... and {omitted} more. Use --constraint \"{c['name']}\" to see all.")
        print()


if __name__ == "__main__":
    run(main)

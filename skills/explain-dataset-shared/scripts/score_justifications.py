#!/usr/bin/env python3
"""
Shows score analysis justifications with sampling or resource-focused filtering.
Works for any model defined in model_config.py, selected via --model.

Two modes:
  --samples N        Sample N justifications per constraint (default: 3). Good for a broad overview.
  --resource NAME    Show every justification that mentions a specific resource — a vehicle shift ID
                     for FSR, an employee name for ESS, a driver shift ID for PDR. Substring match,
                     case-insensitive.

Additional filters (combinable):
  --type hard|medium|soft|all    Restrict to one constraint tier (default: all violated)
  --constraint NAME              Restrict to one constraint by name (substring match)

Usage:
    python score_justifications.py --model field-service-routing --api-key KEY --dataset-id ID
    python score_justifications.py --model field-service-routing --api-key KEY --dataset-id ID --samples 5 --type hard
    python score_justifications.py --model field-service-routing --api-key KEY --dataset-id ID --resource "VAN-12"
    python score_justifications.py --model field-service-routing --api-key KEY --dataset-id ID --resource "TRK-07" --type hard
    python score_justifications.py --model employee-shift-scheduling --api-key KEY --dataset-id ID --resource "EMP-001"
    TIMEFOLD_API_KEY=KEY python score_justifications.py --model field-service-routing --dataset-id ID --resource "VAN-12"
"""

import argparse
import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

from model_config import get_config
from timefold_api import (
    add_common_args,
    constraint_type,
    model_api_get,
    parse_score,
    resolve_args,
    score_sort_key,
)


def _contains_resource(value, resource_lower):
    """Recursively search all string values in a justification for the resource substring."""
    if isinstance(value, str):
        return resource_lower in value.lower()
    if isinstance(value, dict):
        return any(_contains_resource(v, resource_lower) for v in value.values())
    if isinstance(value, list):
        return any(_contains_resource(item, resource_lower) for item in value)
    return False


def format_justification(j):
    if isinstance(j, str):
        return j
    if isinstance(j, dict):
        if "description" in j:
            return j["description"]
        parts = []
        for k, v in j.items():
            if isinstance(v, (str, int, float, bool)):
                parts.append(f"{k}={v}")
            elif isinstance(v, list) and all(isinstance(x, (str, int)) for x in v):
                parts.append(f"{k}=[{', '.join(str(x) for x in v)}]")
        return ", ".join(parts) if parts else str(j)
    return str(j)


def main():
    p = argparse.ArgumentParser(
        description="Show score analysis justifications with sampling or resource-focused filtering"
    )
    add_common_args(p)
    p.add_argument(
        "--samples",
        type=int,
        default=3,
        help="Max justifications to show per constraint in sample mode (default: 3; ignored when --resource is set)",
    )
    p.add_argument(
        "--resource",
        metavar="NAME",
        help="Show all justifications that mention this resource. Substring match, case-insensitive. "
        "FSR: vehicle shift ID. ESS: employee name. PDR: driver shift ID.",
    )
    p.add_argument(
        "--type",
        choices=["hard", "medium", "soft", "all"],
        default="all",
        help="Filter by constraint tier (default: all violated constraints)",
    )
    p.add_argument(
        "--constraint",
        metavar="NAME",
        help="Restrict to one constraint by name (substring match)",
    )
    args = p.parse_args()
    base, key, did, _ = resolve_args(args)
    cfg = get_config(args.model)
    cp = cfg["collection_path"]
    # singular resource label for display (strip trailing 's')
    resource_label = cfg["resource_plural"].rstrip("s")

    print(f"Fetching score analysis with justifications for {did}...")
    score_data = model_api_get(
        base,
        f"{cp}/{did}/score-analysis",
        key,
        params={"includeJustifications": "true"},
    )

    constraints = [c for c in score_data.get("constraints", []) if c["matchCount"] > 0]

    if args.type != "all":
        constraints = [c for c in constraints if constraint_type(c["weight"]) == args.type]

    if args.constraint:
        constraints = [c for c in constraints if args.constraint.lower() in c["name"].lower()]
        if not constraints:
            print(f"No violated constraint matching '{args.constraint}' found.")
            return

    constraints = sorted(constraints, key=lambda c: score_sort_key(c["score"]))

    print(f"Score      : {score_data.get('score', '?')}")
    type_note = f" [{args.type}]" if args.type != "all" else ""
    if args.resource:
        print(f"Filter     : {resource_label} containing '{args.resource}'")
        mode = "resource"
    else:
        print(f"Mode       : {args.samples} sample(s) per constraint")
        mode = "sample"
    print(f"Constraints: {len(constraints)} violated{type_note}")
    print()

    if not constraints:
        print("✓  No violations found for the given filters.")
        return

    resource_lower = args.resource.lower() if args.resource else None
    total_shown = 0

    for c in constraints:
        all_matches = c.get("matches", [])
        if not all_matches:
            continue

        if mode == "resource":
            display = [
                m
                for m in all_matches
                if _contains_resource(m.get("justification", {}), resource_lower)
            ]
            if not display:
                continue
            omitted = 0
            count_note = f"{len(display)} match(es) for this {resource_label}"
        else:
            display = all_matches[: args.samples]
            omitted = len(all_matches) - len(display)
            count_note = f"showing {len(display)} of {len(all_matches)}"

        ctype = constraint_type(c["weight"]).upper()
        s = parse_score(c["score"])
        impact = s["hard"] or s["medium"] or s["soft"]

        print(f"[{ctype}] {c['name']}")
        print(f"  Impact: {impact:+,}  |  Total violations: {c['matchCount']}  |  {count_note}")

        for match in display:
            line = format_justification(match.get("justification", {}))
            if len(line) > 160:
                line = line[:157] + "..."
            print(f"    • {line}")

        if omitted > 0:
            print(f'    … {omitted} more — use --constraint "{c["name"]}" to see all.')
        print()
        total_shown += len(display)

    if mode == "resource" and total_shown == 0:
        print(f"No justifications mention '{args.resource}'.")
        print(
            f"Tip: use a shorter substring of the {resource_label} ID (e.g. just the surname or shift date)."
        )


if __name__ == "__main__":
    main()

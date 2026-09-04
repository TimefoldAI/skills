#!/usr/bin/env python3
"""
Looks up one or more work items by ID, showing their input requirements and
current assignment. Also supports looking up all work items for a given resource.

For employee-shift-scheduling: looks up shifts — shows time, skills, location; reports which employee is assigned.
For field-service-routing: looks up visits — shows service duration, time windows, skills; reports which vehicle/shift.
For pickup-delivery-routing: looks up jobs — shows stops and priority; assignment lookup not available (use platform Visualization).

Usage:
    python work_details.py --model employee-shift-scheduling --api-key KEY --dataset-id ID --work-ids ID1 ID2
    python work_details.py --model employee-shift-scheduling --api-key KEY --dataset-id ID --resource "EMP-001"
    python work_details.py --model field-service-routing --api-key KEY --dataset-id ID --work-ids "visit-001"
    python work_details.py --model pickup-delivery-routing --api-key KEY --dataset-id ID --work-ids "job-001"
    TIMEFOLD_API_KEY=KEY python work_details.py --model employee-shift-scheduling --dataset-id ID --work-ids "shift-001"
"""
import argparse
import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

from timefold_api import model_api_get, fmt, fmt_datetime, duration_between, add_common_args, resolve_args
from model_config import get_config, get_unassigned_ids, fmt_work_skills, fmt_work_location, fmt_time_windows, nested_get


def get_assignments(solution, cfg, input_work=None):
    """Return {work_id: assigned_resource_label} for all assigned work items."""
    if cfg["solution_work_path"]:
        # Work items carry their assigned resource directly (e.g. ESS: shift.employee)
        work_list = nested_get(solution, cfg["solution_work_path"]) or []
        return {w["id"]: w.get(cfg["solution_assigned_field"]) for w in work_list}
    # Resources carry itineraries that reference work items (e.g. FSR: vehicle → shifts → itinerary)
    ic = cfg.get("solution_itinerary_config")
    if not ic:
        return {}

    # Some models' itinerary entries reference a work item's sub-unit rather than the work
    # item itself (e.g. PDR: itinerary entries are stop IDs, and a job's "stops" list is what
    # maps each stop ID back to its owning job). Build that reverse map first when needed.
    subunit_field = ic.get("work_subunit_field")
    subunit_to_work = {}
    if subunit_field and input_work:
        for wid, item in input_work.items():
            for subunit in item.get(subunit_field, []):
                subunit_id = subunit.get("id") if isinstance(subunit, dict) else subunit
                if subunit_id:
                    subunit_to_work[subunit_id] = wid

    assignments = {}
    for resource in nested_get(solution, ic["resource_list_path"]) or []:
        for shift in resource.get(ic["shifts_field"], []):
            for item in shift.get(ic["itinerary_field"], []):
                if item.get("kind") == ic["kind_filter"] and item.get("id"):
                    label = ic["label_template"].format(
                        resource_id=resource["id"], shift_id=shift["id"]
                    )
                    work_id = subunit_to_work.get(item["id"], item["id"]) if subunit_field else item["id"]
                    assignments[work_id] = label
    return assignments


def main():
    p = argparse.ArgumentParser(description="Look up work item details by ID or by resource")
    add_common_args(p)
    p.add_argument("--work-ids", nargs="+", metavar="ID",
                   help="One or more work item IDs to look up")
    p.add_argument("--resource", metavar="NAME",
                   help="Show all work items assigned to this resource (substring match)")
    args = p.parse_args()
    base, key, did, _ = resolve_args(args)
    cfg = get_config(args.model)
    cp = cfg["collection_path"]
    wu = cfg["work_unit"]

    if not args.work_ids and not args.resource:
        sys.exit(f"Error: provide --work-ids or --resource")

    print(f"Fetching input and solution for {did}...")
    inp = model_api_get(base, f"{cp}/{did}/input", key)
    sol = model_api_get(base, f"{cp}/{did}", key)

    input_work = {w["id"]: w for w in inp.get(cfg["input_work_list"], [])}

    assignments = get_assignments(sol, cfg, input_work)
    unassigned_ids = set(get_unassigned_ids(sol, cfg))

    # Resolve which IDs to show
    if args.resource:
        name_filter = args.resource.lower()
        work_ids = [wid for wid, assigned in assignments.items()
                    if assigned and name_filter in str(assigned).lower()]
        if not work_ids:
            print(f"No {wu}s assigned to a resource matching '{args.resource}'.")
            return
        print(f"Found {len(work_ids)} {wu}(s) for '{args.resource}'.")
    else:
        work_ids = args.work_ids

    meta = sol.get("metadata", {})
    print(f"\n=== {wu.capitalize()} details — {meta.get('name', did)} ===\n")

    for wid in work_ids:
        print(f"{wu.capitalize()} ID : {wid}")

        # Assignment status
        if wid in unassigned_ids:
            print(f"Assigned   : (unassigned)")
        else:
            assigned_to = assignments.get(wid)
            print(f"Assigned   : {assigned_to or '(not found in solution)'}")

        # Input details
        item = input_work.get(wid)
        if item:
            _print_work_details(item, cfg)
        else:
            print("  (not found in input — may be a generated or template item)")
        print()

    if not args.work_ids:
        return
    missing = [wid for wid in args.work_ids if wid not in input_work]
    if missing:
        print(f"Note: {len(missing)} ID(s) not found in input: {', '.join(missing)}")


def _print_work_details(item, cfg):
    """Print all available fields for a work item."""
    # Time (ESS: fixed start/end)
    start_val = None
    for f in cfg["work_start_fields"]:
        start_val = item.get(f)
        if start_val:
            break
    if start_val:
        end_val = None
        for f in cfg["work_end_fields"]:
            end_val = item.get(f)
            if end_val:
                break
        dur = duration_between(start_val, end_val) if end_val else "?"
        print(f"  Time     : {fmt_datetime(start_val)} → {fmt_datetime(end_val)} ({dur})")

    # Location
    loc = fmt_work_location(item, cfg["work_location_fields"])
    if loc:
        print(f"  Location : {loc}")

    # Skills
    skills_raw = item.get(cfg["work_skills_field"], [])
    if skills_raw:
        print(f"  Skills   : {fmt_work_skills(skills_raw, cfg['work_skills_name_key'])}")

    # Tags
    tags_field = cfg.get("work_tags_field")
    tags_raw = item.get(tags_field, []) if tags_field else []
    if tags_raw:
        print(f"  Tags     : {', '.join(str(t) for t in tags_raw)}")

    # Model-specific extras (includes Priority, for models that declare it in work_extra_fields)
    for label, field in cfg.get("work_extra_fields", []):
        val = item.get(field)
        if val is None:
            continue
        if label == "Time windows":
            formatted = fmt_time_windows(val)
        elif label == "Service duration":
            formatted = fmt(val)
        else:
            formatted = str(val)
        if formatted:
            print(f"  {label:<18}: {formatted}")


if __name__ == "__main__":
    main()

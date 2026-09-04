#!/usr/bin/env python3
"""
Lists unassigned work items with their details from the input.
Works for any model defined in model_config.py, selected via --model.

For employee-shift-scheduling: shows unassigned shifts with required skills, time, location.
For field-service-routing: shows unassigned visits with service duration, time windows, required skills.
For pickup-delivery-routing: shows unassigned jobs with their stops and priority.

Usage:
    python list_unassigned.py --model employee-shift-scheduling --api-key KEY --dataset-id ID [--recommendations]
    python list_unassigned.py --model field-service-routing --api-key KEY --dataset-id ID
    python list_unassigned.py --model pickup-delivery-routing --api-key KEY --dataset-id ID
    TIMEFOLD_API_KEY=KEY python list_unassigned.py --model employee-shift-scheduling --dataset-id ID
"""
import argparse
import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

from timefold_api import model_api_get, model_api_post, fmt, fmt_datetime, duration_between, add_common_args, resolve_args
from model_config import get_config, get_unassigned_ids, get_unassigned_entries, fmt_work_skills, fmt_work_location, fmt_time_windows, nested_get


def main():
    p = argparse.ArgumentParser(description="List unassigned work items in a Timefold dataset")
    add_common_args(p)
    p.add_argument("--recommendations", action="store_true",
                   help="Call the recommendation API for each unassigned work item (not supported by every model — a note is printed if unsupported)")
    p.add_argument("--limit", type=int, default=None,
                   help="Max items to display (default: all; default with --recommendations: 50)")
    args = p.parse_args()
    base, key, did, _ = resolve_args(args)
    cfg = get_config(args.model)
    cp = cfg["collection_path"]
    wu = cfg["work_unit"]
    wu_plural = cfg["work_unit_plural"]

    print(f"Fetching solution for {did}...")
    sol = model_api_get(base, f"{cp}/{did}", key)
    unassigned_entries = get_unassigned_entries(sol, cfg)
    unassigned_ids = get_unassigned_ids(sol, cfg)
    # Some models (e.g. pickup-delivery-routing) report richer objects instead of bare IDs,
    # e.g. {"id": ..., "unassignedStops": [...]} when only some of a work item's sub-units
    # are unassigned. The key name mirrors work_subunit_field (see solution_itinerary_config).
    subunit_field = (cfg.get("solution_itinerary_config") or {}).get("work_subunit_field")
    unassigned_subunit_key = f"unassigned{subunit_field.capitalize()}" if subunit_field else None
    partial_subunits = {
        e["id"]: e[unassigned_subunit_key]
        for e in unassigned_entries
        if isinstance(e, dict) and unassigned_subunit_key and e.get(unassigned_subunit_key)
    }

    if not unassigned_ids:
        print(f"✓  No unassigned mandatory {wu_plural} found.")
        return

    print(f"Found {len(unassigned_ids)} unassigned {wu_plural}. Fetching input for details...")
    inp = model_api_get(base, f"{cp}/{did}/input", key)
    work_index = {w["id"]: w for w in inp.get(cfg["input_work_list"], [])}

    # Only cap by default when --recommendations is active
    default_limit = 50 if args.recommendations else len(unassigned_ids)
    limit = args.limit if args.limit is not None else default_limit
    if limit <= 0:
        limit = len(unassigned_ids)
    display_ids = unassigned_ids[:limit]
    omitted = len(unassigned_ids) - len(display_ids)

    print()
    print(f"=== Unassigned {wu_plural} ({len(unassigned_ids)} total) ===")
    if omitted:
        print(f"    Showing first {limit}. Use --limit 0 to see all.")
    print()

    for wid in display_ids:
        item = work_index.get(wid)
        print(f"{wu.capitalize()} ID : {wid}")
        if item:
            _print_work_item(item, cfg)
            unassigned_subunits = partial_subunits.get(wid)
            total_subunits = item.get(subunit_field) if subunit_field else None
            if unassigned_subunits and isinstance(total_subunits, list) and len(unassigned_subunits) < len(total_subunits):
                print(f"  Unassigned {subunit_field}: {len(unassigned_subunits)} of {len(total_subunits)} — {', '.join(unassigned_subunits)}")
        else:
            print(f"  (not found in input)")

        # Prefer the bulk/global endpoint (called once, below) over one per-item call per shift.
        if args.recommendations and cfg.get("recommend_endpoint") and not cfg.get("bulk_recommend_endpoint"):
            _print_recommendations(base, key, did, wid, cfg, cp)
        print()

    if omitted:
        print(f"... {omitted} more unassigned {wu_plural} not shown. Use --limit 0 to see all.")

    if args.recommendations and cfg.get("bulk_recommend_endpoint"):
        _print_bulk_recommendations(base, key, did, cp, display_ids, inp, cfg)

    if args.recommendations and not cfg.get("recommend_endpoint") and not cfg.get("bulk_recommend_endpoint"):
        print(f"Note: recommendations are not supported for {args.model}.")

    print(f"Tip: use work_details.py --model {args.model} to inspect a specific {wu} in more detail.")


def _print_work_item(item, cfg):
    """Print key fields of a work item based on model config."""
    # Time (ESS: fixed start/end; FSR/PDR: time windows per stop)
    start_val = None
    for f in cfg["work_start_fields"]:
        start_val = item.get(f)
        if start_val:
            break
    end_val = None
    for f in cfg["work_end_fields"]:
        end_val = item.get(f)
        if end_val:
            break
    if start_val:
        dur = duration_between(start_val, end_val) if end_val else "?"
        print(f"  Time     : {fmt_datetime(start_val)} → {fmt_datetime(end_val)} ({dur})")

    # Location
    loc = fmt_work_location(item, cfg["work_location_fields"])
    if loc:
        print(f"  Location : {loc}")

    # Required skills
    skills_raw = item.get(cfg["work_skills_field"], [])
    if skills_raw:
        print(f"  Skills   : {fmt_work_skills(skills_raw, cfg['work_skills_name_key'])}")

    # Tags
    tags_field = cfg.get("work_tags_field")
    tags_raw = item.get(tags_field, []) if tags_field else []
    if tags_raw:
        print(f"  Tags     : {', '.join(str(t) for t in tags_raw)}")

    # Model-specific extra fields
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
            print(f"  {label:<10}: {formatted}")


def _print_recommendations(base, key, did, wid, cfg, cp):
    """Call and display the recommendation API for a single unassigned work item.
    Only reached for models with a per-item recommend_endpoint (currently employee-shift-scheduling only),
    whose response identifies the candidate resource via an "employee" field.
    """
    endpoint = cfg["recommend_endpoint"]
    try:
        rec_data = model_api_get(base, f"{cp}/{did}{endpoint}", key)
        recs = rec_data.get("recommendations", [])
        if not recs:
            print(f"  Recommendations: none — no feasible option under current constraints")
        else:
            print("  Recommendations (top 3):")
            for rec in recs[:3]:
                resource = rec.get("employee", "?")
                score_diff = rec.get("scoreDiff", "?")
                diffs = [d.get("constraintName") for d in rec.get("constraintDiffs", [])
                         if d.get("matchCountDiff", 0) > 0]
                diff_note = f" (would violate: {', '.join(diffs)})" if diffs else " (no new violations)"
                print(f"    → {resource}: score change {score_diff}{diff_note}")
    except Exception as e:
        print(f"  Recommendations: failed ({e})")


def _print_fsr_time_window_recs(recs):
    """Print field-service-routing's bulk response: a flat list of suggested time windows,
    each naming which vehicle shifts could serve it (not tied to a specific visit ID)."""
    for rec in recs:
        tw = rec.get("timeWindow") or {}
        tw_str = ""
        if tw.get("minStartTime") or tw.get("maxEndTime"):
            tw_str = f"  window: {tw.get('minStartTime', '?')} → {tw.get('maxEndTime', '?')}"
        score_diff = rec.get("scoreDiff", "")
        score_str = f"  score: {score_diff}" if score_diff else ""
        diffs = [d.get("constraintName") for d in rec.get("constraintDiffs", [])
                 if d.get("matchCountDiff", 0) > 0]
        diff_note = f"  violations: {', '.join(diffs)}" if diffs else "  no new violations"
        shifts = rec.get("vehicleShifts", [])
        shift_ids = [s.get("id", "?") for s in shifts]
        shift_str = f"  shifts: {', '.join(shift_ids)}" if shift_ids else "  no shifts recommended"
        parts = [p for p in [tw_str, shift_str, score_str, diff_note] if p]
        print(f"  →{'  |'.join(parts)}")


def _print_ess_global_recs(recs):
    """Print employee-shift-scheduling's global batch response: one ranked list of
    (shift, employee) candidates across all requested shifts."""
    for entry in recs:
        shift_id = entry.get("shiftId", "?")
        rec = entry.get("recommendation") or {}
        employee = rec.get("employeeId", "?")
        score_diff = rec.get("scoreDiff", "?")
        diffs = [d.get("constraintName") for d in rec.get("constraintDiffs", [])
                 if d.get("matchCountDiff", 0) > 0]
        diff_note = f"would violate: {', '.join(diffs)}" if diffs else "no new violations"
        print(f"  → shift {shift_id}: {employee}  (score change {score_diff}, {diff_note})")


_BULK_SHAPE_PRINTERS = {
    "fsr_time_window": _print_fsr_time_window_recs,
    "ess_global":      _print_ess_global_recs,
}


def _print_bulk_recommendations(base, key, did, cp, work_ids, inp, cfg):
    """Call the model's bulk/global recommendation endpoint in batches and display results.
    Request field names, batch size, and response shape all vary by model — see the
    bulk_recommend_* keys in model_config.py.
    """
    endpoint = cfg["bulk_recommend_endpoint"]
    id_field = cfg["bulk_recommend_id_field"]
    max_field = cfg["bulk_recommend_max_field"]
    max_value = cfg["bulk_recommend_max_value"]
    batch_size = cfg["bulk_recommend_batch_size"]
    print_recs = _BULK_SHAPE_PRINTERS[cfg["bulk_recommend_shape"]]
    wu_plural = cfg["work_unit_plural"]

    total = len(work_ids)
    batches = [work_ids[i:i + batch_size] for i in range(0, total, batch_size)]

    print(f"\n=== Bulk recommendations for {total} unassigned {wu_plural} ===")

    for batch_num, batch in enumerate(batches, 1):
        if len(batches) > 1:
            print(f"\n  Batch {batch_num}/{len(batches)} ({len(batch)} {wu_plural}): {', '.join(batch)}")

        body = {
            max_field: max_value,
            id_field: batch,
            "modelInput": inp,
        }
        try:
            data = model_api_post(base, f"{cp}/{did}{endpoint}", key, body)
            recs = data.get("recommendations", [])
            if not recs:
                print("  No feasible recommendation found for this group.")
                continue
            print_recs(recs)
        except Exception as e:
            print(f"  Bulk recommendations failed: {e}")


if __name__ == "__main__":
    main()

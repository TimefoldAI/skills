#!/usr/bin/env python3
"""
Shows per-resource metrics in a compact table with configurable sort order.
Flags overtime, unpreference violations, and underutilized resources automatically.

For employee-shift-scheduling: shows per-employee metrics (hours, overtime, preferences).
For field-service-routing: shows per-vehicle metrics (visits, travel time, distance, overtime).
For pickup-delivery-routing: shows per-driver metrics (travel time, distance, overtime).

Sort keys vary by model — the full list of valid --sort values for the given --model is
printed at the end of every run ("Available --sort values: ...").

Reads the API key from the TIMEFOLD_API_KEY environment variable. It accepts no --api-key
argument, so the key stays out of the command line.

Usage:
    python resource_metrics.py --model employee-shift-scheduling --dataset-id ID --sort overtime
    python resource_metrics.py --model employee-shift-scheduling --dataset-id ID --filter "EMP-001"
"""
import argparse
import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

from timefold_api import model_api_get, fmt, seconds, iso_duration, parse_score, add_common_args, resolve_args
from model_config import get_config, nested_get


def resource_metrics(resource):
    """Return a resource's metrics dict. Most models put an aggregate on the resource
    itself; pickup-delivery-routing only nests metrics per shift (resource['shifts'][i]['metrics']),
    so aggregate those by summing durations/numbers and taking the max for point-in-time fields."""
    if resource.get("metrics"):
        return resource["metrics"]
    shifts = resource.get("shifts") or []
    shift_metrics = [s["metrics"] for s in shifts if s.get("metrics")]
    if not shift_metrics:
        return {}
    agg = {}
    for m in shift_metrics:
        for field, value in m.items():
            if isinstance(value, bool) or value is None:
                continue
            if isinstance(value, (int, float)):
                agg[field] = agg.get(field, 0) + value
            elif isinstance(value, str) and value.startswith("PT"):
                agg[field] = agg.get(field, 0) + seconds(value)
    for field, value in list(agg.items()):
        if isinstance(value, (int, float)) and any(
            field in m and isinstance(m[field], str) and m[field].startswith("PT") for m in shift_metrics
        ):
            agg[field] = iso_duration(value)
    return agg


def fmt_cell(value, col_type):
    if value is None:
        return "—"
    if col_type == "duration":
        s = seconds(value)
        return fmt(value) if s > 0 else "—"
    if col_type == "percent":
        return f"{value:.1f}%"
    if col_type == "meters":
        return f"{value/1000:.1f}km" if value >= 1000 else f"{value}m"
    if col_type == "number":
        return f"{value:,.1f}" if isinstance(value, float) else str(value)
    return str(value)


def build_sort_keys(cfg):
    """Build the sort key functions available for this model."""
    keys = {"name": lambda r: r["id"].lower()}
    ot = cfg.get("resource_overtime_field")
    if ot:
        keys["overtime"] = lambda r: -seconds(resource_metrics(r).get(ot, "PT0S"))
    worked = cfg.get("resource_worked_field")
    if worked:
        keys["hours"] = lambda r: -seconds(resource_metrics(r).get(worked, "PT0S"))
    unprefs = cfg.get("resource_unprefs_field")
    if unprefs:
        keys["unprefs"] = lambda r: -seconds(resource_metrics(r).get(unprefs, "PT0S"))
    assigned = cfg.get("resource_assigned_field")
    if assigned:
        keys["visits"] = lambda r: -resource_metrics(r).get(assigned, 0)
    travel = cfg.get("resource_travel_field")
    if travel:
        keys["travel"] = lambda r: -seconds(resource_metrics(r).get(travel, "PT0S"))
    return keys


def get_flags(metrics, cfg):
    flags = []
    ot_field = cfg.get("resource_overtime_field")
    if ot_field and seconds(metrics.get(ot_field, "PT0S")) > 0:
        flags.append("overtime")
    unprefs = cfg.get("resource_unprefs_field")
    if unprefs and seconds(metrics.get(unprefs, "PT0S")) > 0:
        flags.append("unprefs")
    worked_field = cfg.get("resource_worked_field")
    worked = seconds(metrics.get(worked_field, "PT0S")) if worked_field else 0
    for tf in cfg.get("resource_threshold_fields", []):
        threshold = seconds(metrics.get(tf, "PT0S"))
        if threshold > 0:
            if worked < threshold * 0.85:
                flags.append("underutilized")
            break
    return flags


def main():
    p = argparse.ArgumentParser(description="Show per-resource metrics for a Timefold dataset")
    add_common_args(p)
    p.add_argument("--sort", default=None, metavar="KEY",
                   help="Sort key; valid values depend on --model (printed at the end of output as 'Available --sort values')")
    p.add_argument("--filter", metavar="TEXT", help="Only show resources whose ID contains this text")
    args = p.parse_args()
    base, key, did, _ = resolve_args(args)
    cfg = get_config(args.model)
    cp = cfg["collection_path"]

    sol = model_api_get(base, f"{cp}/{did}", key)
    meta = sol.get("metadata", {})
    resources = list(nested_get(sol, cfg["resource_list_path"]) or [])

    if args.filter:
        resources = [r for r in resources if args.filter.lower() in r["id"].lower()]
    if not resources:
        msg = f" matching '{args.filter}'" if args.filter else ""
        print(f"No {cfg['resource_plural']} found{msg}.")
        return

    sort_keys = build_sort_keys(cfg)
    default_sort = "unprefs" if "unprefs" in sort_keys else "overtime"
    if args.sort and args.sort not in sort_keys:
        print(f"Unknown --sort '{args.sort}' for {args.model} — falling back to '{default_sort}'. "
              f"Valid values: {', '.join(sort_keys)}\n")
    sort_by = args.sort if args.sort in sort_keys else default_sort
    resources.sort(key=sort_keys[sort_by])

    print(f"=== {meta.get('name', did)} — {cfg['resource_plural'].capitalize()} (sorted by {sort_by}) ===")
    print(f"Score: {meta.get('score', '?')}  |  {len(resources)} {cfg['resource_plural']}")
    print()

    # Determine which columns have any data worth showing
    active_cols = []
    for field, header, col_type in cfg["resource_metric_columns"]:
        has_data = any(
            resource_metrics(r).get(field) is not None
            for r in resources
        )
        if has_data:
            active_cols.append((field, header, col_type))

    id_w = 28
    col_w = 10
    sep = "  "
    header_str = f"{'ID':<{id_w}}" + sep + sep.join(f"{h:>{col_w}}" for _, h, _ in active_cols)
    print(header_str)
    print("-" * len(header_str))

    observations = {"overtime": [], "unprefs": [], "underutilized": []}

    for r in resources:
        m = resource_metrics(r)
        flags = get_flags(m, cfg)
        for f in flags:
            if f in observations:
                observations[f].append(r["id"])

        row = f"{r['id'][:id_w-1]:<{id_w}}"
        for field, _, col_type in active_cols:
            cell = fmt_cell(m.get(field), col_type)
            row += sep + f"{cell:>{col_w}}"
        if flags:
            row += f"  ◄ {', '.join(flags)}"
        print(row)

    print()
    obs_lines = []
    if observations["overtime"]:
        obs_lines.append(
            f"{len(observations['overtime'])} {cfg['resource_plural']} with overtime: "
            + ", ".join(observations["overtime"][:5])
            + (f" +{len(observations['overtime'])-5} more" if len(observations["overtime"]) > 5 else "")
        )
    if observations["unprefs"]:
        unprefs_field = cfg.get("resource_unprefs_field")
        worst = max(
            [r for r in resources if seconds(resource_metrics(r).get(unprefs_field, "PT0S")) > 0],
            key=lambda r: seconds(resource_metrics(r).get(unprefs_field, "PT0S")),
        )
        obs_lines.append(
            f"{len(observations['unprefs'])} {cfg['resource_plural']} with unpreferred {cfg['work_unit_plural']} — "
            f"worst: {worst['id']} ({fmt(worst['metrics'].get(unprefs_field))})"
        )
    if observations["underutilized"]:
        obs_lines.append(
            f"{len(observations['underutilized'])} {cfg['resource_plural']} underutilized (<85% of threshold): "
            + ", ".join(observations["underutilized"][:5])
        )

    if obs_lines:
        print("Observations:")
        for line in obs_lines:
            print(f"  • {line}")
    else:
        print(f"No notable workload issues detected.")

    available_sorts = ", ".join(sort_keys)
    print(f"\nAvailable --sort values: {available_sorts}")


if __name__ == "__main__":
    main()

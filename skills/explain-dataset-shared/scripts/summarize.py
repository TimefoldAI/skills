#!/usr/bin/env python3
"""
Fetches a Timefold dataset and prints a compact, readable summary of results.
Works for any model defined in model_config.py, selected via --model.

Reads the API key from the TIMEFOLD_API_KEY environment variable. It accepts no --api-key
argument, so the key stays out of the command line.

Usage:
    python summarize.py --model employee-shift-scheduling --dataset-id ID [--tenant ID]
    python summarize.py --model field-service-routing --dataset-id ID
"""
import argparse
import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

from timefold_api import model_api_get, fmt, seconds, parse_score, score_sort_key, constraint_type, add_common_args, resolve_args, platform_links, fmt_solver_status, get_tenant_name
from model_config import get_config, nested_get


def fmt_kpi(value, kpi_type):
    """Format a KPI value based on its declared type."""
    if value is None:
        return None
    if kpi_type == "duration":
        return fmt(value)
    if kpi_type == "percent":
        return f"{value:.1f}%"
    if kpi_type == "meters":
        km = value / 1000
        return f"{km:.1f} km" if km >= 1 else f"{value} m"
    if kpi_type == "number":
        return f"{value:,.2f}" if isinstance(value, float) else str(value)
    return str(value)  # int


def get_resource_flags(metrics, cfg):
    """Return a list of flag labels for a resource with notable issues."""
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
    p = argparse.ArgumentParser(description="Summarize a Timefold dataset")
    add_common_args(p)
    args = p.parse_args()
    base, key, did, platform_base = resolve_args(args)
    cfg = get_config(args.model)
    cp = cfg["collection_path"]

    sol = model_api_get(base, f"{cp}/{did}", key)
    score_data = model_api_get(base, f"{cp}/{did}/score-analysis", key)

    meta = sol.get("metadata", {})
    kpis = sol.get("kpis", {})
    im = sol.get("inputMetrics", {})

    # Header
    print(f"=== {meta.get('name', did)} ===")
    if args.tenant:
        tenant_name = get_tenant_name(args.tenant, key, platform_base)
        if tenant_name:
            print(f"Tenant     : {tenant_name} ({args.tenant})")
        else:
            print(f"Tenant ID  : {args.tenant}")
    print(f"Dataset ID : {did}")
    tags = meta.get("tags", [])
    if tags:
        print(f"Tags       : {', '.join(tags)}")
    if args.tenant:
        links = platform_links(args.tenant, cfg["platform_model_slug"], did, platform_base=platform_base)
        pad = max(len(k) for k in links)
        print("Platform links:")
        for label, url in links.items():
            print(f"  {label:<{pad}} : {url}")
    status = meta.get("solverStatus", "UNKNOWN")
    print(f"Status     : {status} ({fmt_solver_status(status)})")
    print()

    # Coverage banner
    score_str = meta.get("score", "?")
    score = parse_score(score_str)
    assigned   = kpis.get(cfg["kpi_assigned_field"])
    unassigned = kpis.get(cfg["kpi_unassigned_field"], 0)
    mandatory  = im.get(cfg["input_mandatory"])
    wu_plural  = cfg["work_unit_plural"]

    if score["hard"] != 0:
        print(f"⚠️  INFEASIBLE: {score['hard']} hard constraint violation(s) — run score_violations.py --type hard")
    if unassigned > 0:
        pct = f" ({unassigned / mandatory * 100:.1f}% of mandatory)" if mandatory else ""
        print(f"⚠️  {unassigned} mandatory {wu_plural} unassigned{pct}")
    elif score["medium"] < 0:
        print(f"⚠️  Medium constraint violations present (score impact {score['medium']:+,}) — see constraint summary below")
    if score["hard"] == 0 and score["medium"] == 0:
        print(f"✓  All mandatory {wu_plural} assigned, no hard violations")
    print()

    # KPIs
    print("--- Schedule results ---")
    total    = im.get(cfg["input_total"], "?")
    optional = im.get(cfg["input_optional"], 0)
    res_total = im.get(cfg["input_resources"], "?")
    shift_note = f"  ({mandatory} mandatory, {optional} optional)" if optional else ""
    if assigned is not None:
        print(f"  {cfg['work_unit_plural'].capitalize()} assigned : {assigned}/{total}{shift_note}")
    active_res = kpis.get(cfg["kpi_active_resources"])
    if active_res is not None:
        print(f"  {cfg['resource_plural'].capitalize()} active   : {active_res} of {res_total}")

    for field, label, kpi_type in cfg["kpis"]:
        if field in (cfg["kpi_assigned_field"], cfg["kpi_unassigned_field"], cfg["kpi_active_resources"]):
            continue  # already shown above
        value = kpis.get(field)
        if value is None:
            continue
        formatted = fmt_kpi(value, kpi_type)
        if formatted:
            # Add contextual note for fairness
            note = ""
            if field == "workingTimeFairnessPercentage":
                note = "  ← good balance" if value >= 90 else ("  ← uneven" if value < 70 else "")
            print(f"  {label:<30} {formatted}{note}")
    print()

    # Validation warnings
    vr = meta.get("validationResult", {})
    errors   = vr.get("errors", [])
    warnings = vr.get("warnings", [])
    if errors:
        print(f"--- Input validation errors ({len(errors)}) ---")
        for e in errors[:5]:
            print(f"  ✗ {e}")
        if len(errors) > 5:
            print(f"  ... and {len(errors) - 5} more")
        print()
    if warnings:
        print(f"--- Input validation warnings ({len(warnings)}) ---")
        for w in warnings[:5]:
            print(f"  ⚠ {w}")
        if len(warnings) > 5:
            print(f"  ... and {len(warnings) - 5} more (these may explain why some {wu_plural} can't be assigned)")
        print()

    # Constraint summary (pointer only — detail in score_violations.py)
    violations = sorted(
        [c for c in score_data.get("constraints", []) if c["matchCount"] > 0],
        key=lambda c: score_sort_key(c["score"]),
    )
    hard_med = [c for c in violations if constraint_type(c["weight"]) in ("hard", "medium")]
    soft_only = [c for c in violations if c not in hard_med]
    if hard_med:
        print("--- Constraint summary (hard/medium issues) ---")
        for c in hard_med[:5]:
            ctype = constraint_type(c["weight"]).upper()
            print(f"  [{ctype}] {c['name']}: {c['matchCount']} violation{'s' if c['matchCount'] != 1 else ''}")
        if soft_only:
            print(f"  + {len(soft_only)} soft constraint(s) with violations (preferences, cost, fairness)")
        print("  Run score_violations.py for the full breakdown.")
    else:
        print("--- No hard or medium constraint violations ---")
    print()

    # Resource table
    resources = nested_get(sol, cfg["resource_list_path"]) or []
    if not resources:
        print(f"(No {cfg['resource_plural']} in solution output)")
        return

    # Sort by most-flagged first
    unprefs_field = cfg.get("resource_unprefs_field")
    overtime_field = cfg.get("resource_overtime_field")

    def sort_key(r):
        m = r.get("metrics", {})
        return (
            -seconds(m.get(unprefs_field, "PT0S")) if unprefs_field else 0,
            -seconds(m.get(overtime_field, "PT0S")) if overtime_field else 0,
            r["id"],
        )

    sorted_res = sorted(resources, key=sort_key)
    flagged = [r for r in sorted_res if get_resource_flags(r.get("metrics", {}), cfg)]
    large = len(resources) > 20

    # Determine which metric columns have any non-zero/non-null values
    active_cols = []
    for field, header, col_type in cfg["resource_metric_columns"]:
        has_data = any(
            r.get("metrics", {}).get(field) is not None
            and (col_type != "duration" or seconds(r.get("metrics", {}).get(field, "PT0S")) > 0
                 or field in (cfg.get("resource_worked_field"), cfg.get("resource_overtime_field") or ""))
            for r in resources
        )
        if has_data:
            active_cols.append((field, header, col_type))

    if large and flagged:
        display = flagged
        print(f"--- {cfg['resource_plural'].capitalize()} — {len(flagged)} with notable issues (of {len(resources)} total) ---")
        print(f"    Run resource_metrics.py to see all.")
    elif large:
        display = sorted_res[:5]
        print(f"--- {cfg['resource_plural'].capitalize()} — no notable issues across {len(resources)} total ---")
        print(f"    Sample (first 5, run resource_metrics.py for full table):")
    else:
        display = sorted_res
        print(f"--- {cfg['resource_plural'].capitalize()} metrics ---")

    col_id_w = 28
    col_w = 9
    sep = "  "
    header = f"{'ID':<{col_id_w}}" + sep + sep.join(f"{h:>{col_w}}" for _, h, _ in active_cols)
    print(header)
    print("-" * len(header))

    for r in display:
        m = r.get("metrics", {})
        flags = get_resource_flags(m, cfg)
        row = f"{r['id'][:col_id_w-1]:<{col_id_w}}"
        for field, _, col_type in active_cols:
            val = m.get(field)
            if val is None or (col_type == "duration" and seconds(val) == 0):
                cell = "—"
            else:
                cell = fmt_kpi(val, col_type) or "—"
            row += sep + f"{cell:>{col_w}}"
        if flags:
            row += f"  ◄ {', '.join(flags)}"
        print(row)

    print()
    wu = cfg["work_unit_plural"]
    if not args.tenant:
        print(f"Tip: add --tenant YOUR_TENANT_ID to generate platform links (overview, visualization, input, output, configuration).")
    print(f"     run list_unassigned.py --model {args.model} to see why {wu} are unassigned.")
    print(f"     run score_violations.py --model {args.model} for the full constraint breakdown.")
    print(f"     run resource_metrics.py --model {args.model} for the full {cfg['resource_plural']} table.")


if __name__ == "__main__":
    main()

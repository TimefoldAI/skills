"""
Per-model configuration for the explain-dataset skill.
Covers terminology, API paths, KPI field names, resource metric columns,
and how to detect unassigned work items — the parts that differ between models.
"""


# ---------------------------------------------------------------------------
# Config registry
# ---------------------------------------------------------------------------

MODEL_CONFIGS = {
    "employee-shift-scheduling": {
        "name": "Employee Shift Scheduling",
        # The skill that drives this model. It goes into the usage parameter on every request.
        "skill": "explain-dataset-ess",
        "collection_path": "/schedules",
        # The platform's URL routing (and the Model API path) use "employee-scheduling" —
        # an older, shorter slug that predates this plugin's "employee-shift-scheduling" key.
        "platform_model_slug": "employee-scheduling",

        # Human-readable terminology
        "work_unit": "shift",
        "work_unit_plural": "shifts",
        "resource_plural": "employees",

        # KPI display: list of (api_field, label, type)
        # type: "int" | "duration" | "percent" | "number" | "meters"
        "kpis": [
            ("assignedShifts",                                    "Shifts assigned",          "int"),
            ("unassignedShifts",                                  "Shifts unassigned",        "int"),
            ("activatedEmployees",                                "Employees active",         "int"),
            ("workingTimeFairnessPercentage",                     "Working time fairness",    "percent"),
            ("averageDurationOfEmployeesPreferencesMet",          "Avg preferences met",      "duration"),
            ("minimumDurationOfPreferencesMetAcrossEmployees",    "Min preferences met",      "duration"),
            ("averageDurationOfEmployeesUnpreferencesViolated",   "Avg unprefs violated",     "duration"),
            ("maximumDurationOfUnpreferencesViolatedAcrossEmployees", "Max unprefs violated", "duration"),
            ("disruptionPercentage",                              "Disruption",               "percent"),
        ],
        "kpi_assigned_field":   "assignedShifts",
        "kpi_unassigned_field": "unassignedShifts",
        "kpi_active_resources": "activatedEmployees",

        # inputMetrics field names
        "input_total":     "shifts",
        "input_mandatory": "mandatoryShifts",
        "input_optional":  "optionalShifts",
        "input_resources": "employees",

        # Where to find resources in the solution
        "resource_list_path": ["modelOutput", "employees"],

        # Per-resource metrics table columns: (api_field, header, type)
        "resource_metric_columns": [
            ("assignedShifts",                    "Shifts",      "int"),
            ("durationWorked",                    "Worked",      "duration"),
            ("overtimeThresholdDuration",         "Threshold",   "duration"),
            ("overtimeWorked",                    "Overtime",    "duration"),
            ("durationOfTimePreferencesMet",      "Prefs met",   "duration"),
            ("durationOfTimeUnpreferencesViolated", "Unprefs",   "duration"),
            ("costDefinitionTotalCost",           "Cost",        "number"),
            ("durationOfDisruptedShifts",         "Disruption",  "duration"),
        ],
        # Fields used for flagging notable resources
        "resource_overtime_field":    "overtimeWorked",
        "resource_worked_field":      "durationWorked",
        "resource_threshold_fields":  ["overtimeThresholdDuration", "maximumAvailabilityDuration"],
        "resource_unprefs_field":     "durationOfTimeUnpreferencesViolated",
        "resource_assigned_field":    "assignedShifts",
        "resource_travel_field":      None,  # ESS has no travel metric — shifts aren't routed

        # Unassignment detection
        # ESS: scan modelOutput.shifts[] for absent/null employee field
        "unassigned_explicit_path": None,
        "solution_work_path":       ["modelOutput", "shifts"],
        "solution_assigned_field":  "employee",   # absent or null → unassigned
        # Input work item field names (for list_unassigned + work_details)
        "input_work_list":       "shifts",
        "work_start_fields":     ["start", "startDateTime"],
        "work_end_fields":       ["end", "endDateTime"],
        "work_location_fields":  ["location", "locationName", "department", "area"],
        "work_skills_field":     "requiredSkills",
        "work_skills_name_key":  "name",   # how to extract skill name from each item (string key, or None if plain string)
        "work_tags_field":       "tags",
        "work_extra_fields":     [("Priority", "priority")],

        # ESS assignment is a direct employee field on each shift — no itinerary to traverse.
        "solution_itinerary_config": None,

        # Recommendation endpoints: recommend_endpoint suggests an employee for a single
        # unassigned shift. bulk_recommend_endpoint (the "global" batch variant) ranks
        # (shift, employee) candidates across many shifts in one call — preferred over
        # the per-item endpoint whenever --recommendations is used for several shifts.
        "recommend_endpoint": "/recommendations/recommend-employees",
        "bulk_recommend_endpoint": "/recommendations/recommend-employees-batch-global",
        "bulk_recommend_id_field":  "fitShiftIds",
        "bulk_recommend_max_field": "maxNumberOfRecommendations",
        "bulk_recommend_max_value": 10,
        "bulk_recommend_batch_size": 100,  # API-enforced max fitShiftIds per call
        "bulk_recommend_shape":     "ess_global",
    },

    "field-service-routing": {
        "name": "Field Service Routing",
        "skill": "explain-dataset-fsr",
        "collection_path": "/route-plans",
        "platform_model_slug": "field-service-routing",

        "work_unit": "visit",
        "work_unit_plural": "visits",
        "resource_plural": "vehicles",

        # KPI display: list of (api_field, label, type)
        "kpis": [
            ("totalAssignedVisits",            "Visits assigned",          "int"),
            ("unassignedMandatoryVisits",       "Visits unassigned",        "int"),
            ("totalActivatedVehicles",          "Vehicles active",          "int"),
            ("workingTimeFairnessPercentage",   "Working time fairness",    "percent"),
            ("totalTravelTime",                 "Total travel time",        "duration"),
            ("averageTravelTimePerVisit",       "Avg travel time / visit",  "duration"),
            ("totalTravelDistanceMeters",       "Total distance",           "meters"),
            ("totalOvertime",                   "Total overtime",           "duration"),
            ("totalTechnicianCosts",            "Total cost",               "number"),
            ("percentageVisitsInSla",           "Visits within SLA",        "percent"),
            ("absoluteVisitsInSla",             "Visits within SLA (count)","int"),
            ("totalProfit",                     "Total profit",             "number"),
        ],
        "kpi_assigned_field":   "totalAssignedVisits",
        "kpi_unassigned_field": "unassignedMandatoryVisits",
        "kpi_active_resources": "totalActivatedVehicles",

        "input_total":     "visits",
        "input_mandatory": "mandatoryVisits",
        "input_optional":  "optionalVisits",
        "input_resources": "vehicles",

        "resource_list_path": ["modelOutput", "vehicles"],

        "resource_metric_columns": [
            ("assignedVisits",             "Visits",    "int"),
            ("totalShiftDuration",         "Shift",     "duration"),
            ("totalServiceDuration",       "Service",   "duration"),
            ("totalTravelTime",            "Travel",    "duration"),
            ("totalTravelDistanceMeters",  "Distance",  "meters"),
            ("totalOvertime",              "Overtime",  "duration"),
            ("totalWaitingTime",           "Waiting",   "duration"),
        ],
        "resource_overtime_field":   "totalOvertime",
        "resource_worked_field":     "totalShiftDuration",
        "resource_threshold_fields": ["availableOvertime"],
        "resource_unprefs_field":    None,
        "resource_assigned_field":   "assignedVisits",
        "resource_travel_field":     "totalTravelTime",

        # Unassignment detection
        # FSR: explicit list of unassigned visit IDs in modelOutput
        "unassigned_explicit_path": ["modelOutput", "unassignedVisits"],
        "solution_work_path":       None,
        "solution_assigned_field":  None,
        # Assignment lookup: traverse vehicles → shifts → itinerary
        "solution_itinerary_config": {
            "resource_list_path": ["modelOutput", "vehicles"],
            "shifts_field":       "shifts",
            "itinerary_field":    "itinerary",
            "kind_filter":        "VISIT",
            "label_template":     "{resource_id} / shift {shift_id}",
            # FSR itinerary entries already use the visit's own ID — no sub-unit indirection.
            "work_subunit_field": None,
        },
        "input_work_list":      "visits",
        "work_start_fields":    [],    # visits have time windows, not a fixed start
        "work_end_fields":      [],
        "work_location_fields": ["location"],   # [lat, lon] array
        "work_skills_field":    "requiredSkills",
        "work_skills_name_key": "name",
        "work_tags_field":      "requiredTags",
        "work_extra_fields": [
            ("Service duration", "serviceDuration"),
            ("Time windows",     "timeWindows"),
            ("Priority",         "priority"),
        ],

        # Recommendation endpoints: FSR recommends time windows in bulk for a batch of
        # unassigned visits; there is no single-item/per-employee variant for this model.
        "recommend_endpoint": None,
        "bulk_recommend_endpoint": "/recommendations/bulk-recommend-time-windows",
        "bulk_recommend_id_field":  "fitVisitIds",
        "bulk_recommend_max_field": "maxNumberOfRecommendationsPerTimeWindow",
        "bulk_recommend_max_value": 3,
        "bulk_recommend_batch_size": 20,
        "bulk_recommend_shape":     "fsr_time_window",
    },

    "pickup-delivery-routing": {
        "name": "Pick-up and Delivery Routing",
        "skill": "explain-dataset-pdr",
        "collection_path": "/route-plans",
        "platform_model_slug": "pickup-delivery-routing",

        "work_unit": "job",
        "work_unit_plural": "jobs",
        "resource_plural": "drivers",

        # KPI display: list of (api_field, label, type)
        "kpis": [
            ("totalAssignedJobs",         "Jobs assigned",          "int"),
            ("totalUnassignedJobs",        "Jobs unassigned",        "int"),
            ("totalActivatedDrivers",      "Drivers active",         "int"),
            ("totalTravelTime",            "Total travel time",      "duration"),
            ("totalTravelDistanceMeters",  "Total distance",         "meters"),
            ("travelTimeBetweenStops",     "Travel between stops",   "duration"),
        ],
        "kpi_assigned_field":   "totalAssignedJobs",
        "kpi_unassigned_field": "totalUnassignedJobs",
        "kpi_active_resources": "totalActivatedDrivers",

        # inputMetrics field names
        "input_total":     "jobs",
        "input_mandatory": None,  # not broken out in inputMetrics
        "input_optional":  None,
        "input_resources": "drivers",

        # Where to find resources in the solution
        "resource_list_path": ["modelOutput", "drivers"],

        # Per-resource metrics table columns: (api_field, header, type)
        "resource_metric_columns": [
            ("totalTravelTime",           "Travel",    "duration"),
            ("totalTravelDistanceMeters", "Distance",  "meters"),
            ("totalOvertime",             "Overtime",  "duration"),
        ],
        "resource_overtime_field":   "totalOvertime",
        "resource_worked_field":     None,
        "resource_threshold_fields": [],
        "resource_unprefs_field":    None,
        "resource_assigned_field":   None,
        "resource_travel_field":     "totalTravelTime",

        # Unassignment detection: explicit list (same pattern as FSR)
        "unassigned_explicit_path": ["modelOutput", "unassignedJobs"],
        "solution_work_path":       None,
        "solution_assigned_field":  None,
        # Assignment lookup: traverse drivers → shifts → itinerary. Itinerary entries carry
        # stop IDs, not job IDs directly, so work_subunit_field tells get_assignments() to
        # resolve each stop ID back to its owning job via the job's own "stops" list first.
        "solution_itinerary_config": {
            "resource_list_path": ["modelOutput", "drivers"],
            "shifts_field":       "shifts",
            "itinerary_field":    "itinerary",
            "kind_filter":        "STOP",
            "label_template":     "{resource_id} / shift {shift_id}",
            "work_subunit_field": "stops",
        },

        "input_work_list":      "jobs",
        "work_start_fields":    [],
        "work_end_fields":      [],
        "work_location_fields": [],
        "work_skills_field":    "requiredSkills",
        "work_skills_name_key": "name",
        "work_tags_field":      None,
        "work_extra_fields": [
            ("Stops",    "stops"),
            ("Priority", "priority"),
        ],

        # PDR's recommendation API suggests time windows for new jobs (customer scheduling),
        # not which resource to assign to an existing unassigned job — so neither the
        # per-item nor the bulk recommendation endpoint applies here.
        "recommend_endpoint": None,
        "bulk_recommend_endpoint": None,
        "bulk_recommend_id_field":  None,
        "bulk_recommend_max_field": None,
        "bulk_recommend_max_value": None,
        "bulk_recommend_batch_size": None,
        "bulk_recommend_shape":     None,
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_config(model_key):
    if model_key not in MODEL_CONFIGS:
        raise SystemExit(f"Unknown model '{model_key}'. Choose from: {', '.join(MODEL_CONFIGS)}")
    return MODEL_CONFIGS[model_key]


def nested_get(obj, path):
    """Walk a nested dict using a list of string keys. Returns None if any key is missing."""
    for key in path:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def get_unassigned_entries(solution, cfg):
    """Return the raw list of unassigned work items for the given model.
    Entries are usually plain ID strings, but some models (e.g. pickup-delivery-routing)
    report objects instead, such as {"id": ..., "unassignedStops": [...]} for a job that's
    only partially unassigned. Use get_unassigned_ids() when only the ID is needed.
    """
    if cfg.get("unassigned_explicit_path"):
        return list(nested_get(solution, cfg["unassigned_explicit_path"]) or [])
    # Scan solution work list for items where assigned field is absent/null
    work_list = nested_get(solution, cfg.get("solution_work_path")) or []
    field = cfg.get("solution_assigned_field")
    return [w.get("id") for w in work_list if not w.get(field) and w.get("id") is not None]


def get_unassigned_ids(solution, cfg):
    """Return list of unassigned work item IDs for the given model, normalized to plain
    ID strings even when the API reports richer objects (see get_unassigned_entries)."""
    return [e["id"] if isinstance(e, dict) else e for e in get_unassigned_entries(solution, cfg)]


def fmt_work_skills(skills_raw, name_key):
    """Format a list of skill entries (dicts with name_key, or plain strings) into a comma string."""
    if not skills_raw:
        return "none"
    parts = []
    for s in skills_raw:
        if isinstance(s, dict):
            parts.append(s.get(name_key) or str(s))
        else:
            parts.append(str(s))
    return ", ".join(parts)


def fmt_work_location(item, fields):
    """Extract a location string from a work item using a priority list of field names."""
    for f in fields:
        val = item.get(f)
        if val:
            if isinstance(val, list) and len(val) == 2:
                return f"{val[0]:.5f}, {val[1]:.5f}"
            return str(val)
    return None


def fmt_time_windows(windows):
    """Format a list of time windows into a readable string."""
    if not windows:
        return None
    parts = []
    for w in windows[:3]:
        start = w.get("start") or w.get("startTime") or ""
        end = w.get("end") or w.get("endTime") or ""
        parts.append(f"{start[:16]} – {end[:16]}" if start else str(w))
    suffix = f" (+{len(windows)-3} more)" if len(windows) > 3 else ""
    return ", ".join(parts) + suffix

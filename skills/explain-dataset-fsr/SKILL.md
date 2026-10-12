---
name: explain-dataset-fsr
description: >
  Helps users of the Timefold Field Service Routing (FSR) model understand an optimized route
  plan by fetching and interpreting the dataset via the API. Use this skill whenever someone
  asks why visits are unassigned, why a specific vehicle is assigned to a visit, what the travel
  efficiency or SLA compliance looks like, where the coverage gaps are, or what they should do
  to improve their plan. Also invoke when the user says things like "explain my route plan",
  "what's wrong with my routing", "help me understand this dataset", "why can't this visit be
  scheduled", "interpret my FSR results", or when they share a dataset ID and want help making
  sense of it.
---

# Model context: Field Service Routing (FSR)

## Terminology

| Generic term | FSR term |
|---|---|
| Work item / work unit | visit |
| Resource | vehicle |
| Resource sub-unit | vehicle shift (a vehicle can have multiple shifts) |
| Mandatory work | mandatory visit |
| Optional work | optional visit |
| Required capability | skill (`requiredSkills`) |
| Capacity constraint | shift time window (`maxEndTime`), max visits, max travel time |

## Model-specific configuration

Always set these before running any script.

```bash
MODEL=field-service-routing
MODEL_API_URL=https://app.timefold.ai/api/models/field-service-routing/v1
COLLECTION=/route-plans
OPENAPI_URL=https://app.timefold.ai/openapis/field-service-routing/v1
```

## Scripts

Scripts live in the sibling skill `explain-dataset-shared`, in its `scripts/` directory.
Anchor every path on this skill's own directory, not on the working directory. The working
directory is the user's project, and these skills are installed somewhere else.

In Claude Code, `${CLAUDE_SKILL_DIR}` is substituted with this skill's directory. If your agent
leaves the placeholder unresolved, replace it with the absolute directory that holds this
`SKILL.md`.

`$PY` is the Python runner that the shared skill's runtime check selects (`uv run`,
`python3`, or `python`). Run that check before the first script call.

```bash
SKILL_DIR=${CLAUDE_SKILL_DIR}
SHARED=$SKILL_DIR/../explain-dataset-shared
SCRIPTS=$SHARED/scripts
PLUGIN_ROOT=${CLAUDE_PLUGIN_ROOT:-$SKILL_DIR/../..}

$PY $SCRIPTS/summarize.py             --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID [--tenant ID]
$PY $SCRIPTS/list_unassigned.py       --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID [--recommendations]
$PY $SCRIPTS/resource_metrics.py      --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID [--sort overtime|travel|visits|name]
$PY $SCRIPTS/work_details.py          --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID --work-ids "visit-001"
$PY $SCRIPTS/work_details.py          --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID --resource "VAN-12"
$PY $SCRIPTS/score_violations.py      --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID [--type hard|medium|soft]
$PY $SCRIPTS/score_justifications.py  --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID [--samples 3]
$PY $SCRIPTS/score_justifications.py  --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID --resource "VAN-12"
```

`$SHARED` also carries the version stamp and, in a plugin install, `$PLUGIN_ROOT` carries the
plugin manifest. The report metadata needs both. Keep the two variables set.

## API

```
Base URL : https://app.timefold.ai/api/models/field-service-routing/v1
Auth     : X-API-KEY: {token}
Collection path: /route-plans
OpenAPI spec: https://app.timefold.ai/openapis/field-service-routing/v1
```

## Documentation

- User guide: https://docs.timefold.ai/field-service-routing/latest/
- Metrics and KPIs: https://docs.timefold.ai/field-service-routing/latest/metrics-and-optimization-goals

## FSR-specific notes

- **Unassigned visits** are in `modelOutput.unassignedVisits` (an explicit list of visit IDs),
  not inferred from a null field like in ESS.
- **Vehicles have shifts**: a vehicle wraps one or more `vehicleShift` objects that each have
  their own itinerary, time window, and metrics. Per-vehicle aggregate metrics are in
  `vehicle.metrics`; per-shift detail is in `vehicle.shifts[].metrics`.
- **Travel metrics** are a core KPI: total travel time, distance, average per visit, and time
  breakdowns (depot-to-first, between visits, last-to-depot).
- **SLA**: if `percentageVisitsInSla` / `absoluteVisitsInSla` are present, call them out.
  They directly measure service quality.
- **Mandatory vs optional is not a fixed tag or priority range.** By default, this is automatic
  and implicit: a visit is mandatory if its time window falls within the current planning
  window, and optional if its time window ends outside it. The `priority` field can override
  this default: built-in priorities `1`-`10` use the automatic `AUTO` behavior above
  (overridable dataset-wide via `defaultAssignmentType: MANDATORY`), `opt-1`-`opt-10` are
  always optional, and custom priority names can set an explicit `assignment` of `AUTO`,
  `MANDATORY`, or `OPTIONAL`. Read the dataset's own priority configuration rather than
  assuming a fixed threshold. See
  [Priority visits and optional visits](https://docs.timefold.ai/field-service-routing/latest/visit-service-constraints/priority-visits-and-optional-visits).
- **`SOLVING_COMPLETED` is not a feasibility verdict.** It means the solver stopped. A completed
  plan with a negative hard score is infeasible.

## Hard constraints: the settings behind them

The shared skill tells you to trace every hard violation to the settings that cause it, and to
link each one. This table maps the FSR hard constraints that are hardest to trace to the input
field or configuration setting that switches them on.

| Constraint | Switched on by | Docs |
|---|---|---|
| Require visit dependency prerequisite assigned | `visits[].visitDependencies[].precedingVisit` on B. Penalizes B being assigned while A, its preceding visit, is unassigned | [Single visit dependency](https://docs.timefold.ai/field-service-routing/latest/visit-service-constraints/visit-dependencies#_single_visit_dependency) |
| Require visit dependency dependent assigned | A dependency whose assignment type is `DISALLOW_TO_BLOCK_FOLLOWING` (the default, also set dataset-wide by `defaultDependencyAssignmentType`) | [Assignment type](https://docs.timefold.ai/field-service-routing/latest/visit-service-constraints/visit-dependencies#_visit_dependency_assignment_type) |
| Require visit dependency delay | `minDelayTo` / `maxDelayTo` on the dependency | [Dependency with delay](https://docs.timefold.ai/field-service-routing/latest/visit-service-constraints/visit-dependencies#_visit_dependency_with_delay) |
| Require the same vehicle for dependent visit | `coordination: SAME_VEHICLE` on the dependency | [Coordination](https://docs.timefold.ai/field-service-routing/latest/visit-service-constraints/visit-dependencies#_visit_dependency_with_coordination) |
| Require the same vehicle shift for dependent visit | `coordination: SAME_SHIFT`, **or any pooling type other than `ALLOW_POOLING_ALL`**, set on the dependency or inherited from `config.model.overrides.defaultDependencyPoolingType` | [Coordination](https://docs.timefold.ai/field-service-routing/latest/visit-service-constraints/visit-dependencies#_visit_dependency_with_coordination), [Pooling type](https://docs.timefold.ai/field-service-routing/latest/visit-service-constraints/visit-dependencies#_visit_dependency_pooling_type) |
| Require visit dependency pooling type | `poolingType` other than `ALLOW_POOLING_ALL`, on the dependency or from `defaultDependencyPoolingType` | [Pooling type](https://docs.timefold.ai/field-service-routing/latest/visit-service-constraints/visit-dependencies#_visit_dependency_pooling_type) |
| Keep a pinned visit's vehicle shift | `pinningRequested: true` on the visit, or `pin: true` on an itinerary item | [Pinning individual visits](https://docs.timefold.ai/field-service-routing/latest/real-time-planning/real-time-planning-pinning-visits#_pinning_individual_visits) |
| Keep a pinned visit's start service time | `pin: true` with `startServiceTime` on `vehicles[].shifts[].itinerary[]` | [Pinning individual visits](https://docs.timefold.ai/field-service-routing/latest/real-time-planning/real-time-planning-pinning-visits#_pinning_individual_visits) |

For a hard constraint that is not in this table, find its page in the
[FSR user guide](https://docs.timefold.ai/field-service-routing/latest/) before you explain it.
Don't link a URL that you did not open.

### Visit dependencies: what each part means

- **A plain dependency only orders the visits.** With only `precedingVisit` (and optionally a
  delay), B starts no sooner than A ends, and B is not assigned unless A is. A and B can be on
  different vehicles and on different days. A plain dependency does not mean "same vehicle" or
  "same shift".
- **A pooling type other than `ALLOW_POOLING_ALL` implicitly adds `SAME_SHIFT`.** Pooling controls
  whether other visits can sit between A and B. When the pooling type is `ALLOW_POOLING_VISITS`,
  `ALLOW_POOLING_DEPENDENCIES`, or `DISALLOW_POOLING`, the model sets the dependency's coordination
  to `SAME_SHIFT` (unless it is already `SAME_SHIFT_ENFORCE`). The input record then shows no
  `coordination` field, yet the "same vehicle shift" constraint still applies.
- **The pooling type often comes from the dataset default.** A dependency without its own
  `poolingType` takes `config.model.overrides.defaultDependencyPoolingType`. `summarize.py` prints
  it under "Configuration overrides". At level 3 or 4, read it from `GET {collection}/{id}/config`.

### Known conflict: recurring visits chained with dependencies

Recurring work (a weekly visit for four weeks) is often modeled as a dependency chain, so that week 2
is not planned without week 1. That is a valid use of a plain dependency. It breaks when the
dependencies get `SAME_SHIFT`, because visits on different dates can never share one vehicle shift.
If the visits are also pinned to their dated shifts, the solver cannot move them, and every link
in the chain stays a hard violation of "Require the same vehicle shift for dependent visit".

Explain it as three settings that combine, each with its docs link: the dependency chain, the
pooling type that implies `SAME_SHIFT`, and the pinning. The fix that keeps the user's intent is
`poolingType: ALLOW_POOLING_ALL` on those dependencies, or as the dataset default if no other
dependency needs a stricter pooling type. Do not propose to remove the dependencies: that drops the
"week 2 only after week 1" rule.

## Full instructions

Read and follow: `$SHARED/SKILL.md`

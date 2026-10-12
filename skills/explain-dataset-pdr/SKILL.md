---
name: explain-dataset-pdr
description: >
  Helps users of the Timefold Pick-up and Delivery Routing (PDR) model understand an optimized
  route plan by fetching and interpreting the dataset via the API. Use this skill whenever someone
  asks why jobs are unassigned, why a specific driver is assigned to a job, what the travel
  efficiency looks like, where the coverage gaps are, or what they should do to improve their
  plan. Also invoke when the user says things like "explain my route plan", "what's wrong with
  my routing", "help me understand this dataset", "why can't this job be scheduled", "interpret
  my PDR results", or when they share a dataset ID and want help making sense of it.
---

# Model context: Pick-up and Delivery Routing (PDR)

## Terminology

| Generic term | PDR term |
|---|---|
| Work item / work unit | job |
| Resource | driver |
| Resource sub-unit | driver shift (a driver can have multiple shifts) |
| Work item sub-unit | stop (each job consists of one or more pickup/delivery stops) |
| Mandatory work | mandatory job (priority 1–10) |
| Optional work | optional job (priority opt-1–opt-10) |
| Required capability | skill (`requiredSkills`) |
| Capacity constraint | shift time window (`maxEndTime`), max stops, max travel time |

## Model-specific configuration

Always set these before running any script.

```bash
MODEL=pickup-delivery-routing
MODEL_API_URL=https://app.timefold.ai/api/models/pickup-delivery-routing/v1
COLLECTION=/route-plans
OPENAPI_URL=https://app.timefold.ai/openapis/pickup-delivery-routing/v1
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
$PY $SCRIPTS/list_unassigned.py       --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID
$PY $SCRIPTS/resource_metrics.py      --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID [--sort overtime|travel|name]
$PY $SCRIPTS/work_details.py          --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID --work-ids "job-001"
$PY $SCRIPTS/score_violations.py      --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID [--type hard]
$PY $SCRIPTS/score_justifications.py  --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID [--samples 3]
$PY $SCRIPTS/score_justifications.py  --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID --resource "driver-001"
```

`$SHARED` also carries the version stamp and, in a plugin install, `$PLUGIN_ROOT` carries the
plugin manifest. The report metadata needs both. Keep the two variables set.

## API

```
Base URL : https://app.timefold.ai/api/models/pickup-delivery-routing/v1
Auth     : X-API-KEY: {token}
Collection path: /route-plans
OpenAPI spec: https://app.timefold.ai/openapis/pickup-delivery-routing/v1
```

## Documentation

- User guide: https://docs.timefold.ai/pickup-delivery-routing/latest/
- Metrics and KPIs: https://docs.timefold.ai/pickup-delivery-routing/latest/metrics-and-optimization-goals

## PDR-specific notes

- **Unassigned jobs** are in `modelOutput.unassignedJobs` (an explicit list of job IDs).
- **Jobs contain stops**: a job groups one or more pickup/delivery stops that must all be served
  together by the same driver shift. Stops appear in the driver's itinerary with `kind: "STOP"`.
- **Drivers have shifts**: a driver can have multiple shifts; each shift has its own itinerary
  and metrics. Per-shift metrics are in `driver.shifts[].metrics`.
- **Assignment lookup**: the itinerary contains stop IDs, not job IDs, so `work_details.py`
  resolves each stop back to its owning job via the job's input `stops` list before matching
  `--resource` or reporting which driver a job is assigned to.
- **Travel metrics** are a core KPI: total travel time, distance, and per-segment breakdowns
  (depot-to-first, between stops, last-to-depot).
- **Mandatory vs optional comes from the `priority` field, by prefix, not a fixed tag.**
  Priorities `1`-`10` are mandatory by default (`6` is the default value), and `opt-1`-`opt-10`
  are always optional. This default mapping is itself configurable per dataset via a
  `priorityWeights` override, which can define custom priority names with an explicit
  `assignment` of `MANDATORY` or `OPTIONAL`. Read the dataset's own priority configuration
  rather than assuming every job's priority follows the default prefix convention. See
  [Priority jobs and optional jobs](https://docs.timefold.ai/pickup-delivery-routing/latest/job-service-constraints/priority-jobs-and-optional-jobs).
- **`SOLVING_COMPLETED` is not a feasibility verdict.** It means the solver stopped. A completed
  plan with a negative hard score is infeasible.

## Hard constraints: the settings behind them

The shared skill tells you to trace every hard violation to the settings that cause it, and to
link each one. This table maps the PDR hard constraints that are hardest to trace to what switches
them on.

| Constraint | Switched on by | Docs |
|---|---|---|
| Do not assign stops if previous stop is unassigned | The order of `jobs[].stops[]`. Each stop depends on the stop before it in the list | [Dependencies between stops](https://docs.timefold.ai/pickup-delivery-routing/latest/job-service-constraints/dependencies-between-stops#_defining_stop_dependencies) |
| Assign stops in sequence | The order of `jobs[].stops[]` | [Dependencies between stops](https://docs.timefold.ai/pickup-delivery-routing/latest/job-service-constraints/dependencies-between-stops#_defining_stop_dependencies) |
| Assign the same driver shift for dependent stops | Always on for the stops of one job. No setting turns it off | [Dependencies between stops](https://docs.timefold.ai/pickup-delivery-routing/latest/job-service-constraints/dependencies-between-stops#_defining_stop_dependencies) |
| No semi-assigned jobs | A job with some stops assigned and others not | [Dependencies between stops](https://docs.timefold.ai/pickup-delivery-routing/latest/job-service-constraints/dependencies-between-stops#_defining_stop_dependencies) |
| Prohibit job pooling | `jobs[].prohibitJobPooling: true` | [Job pooling](https://docs.timefold.ai/pickup-delivery-routing/latest/job-service-constraints/job-requirements-and-tags/job-pooling) |
| Keep a pinned stop's driver shift | `pin: true` with `startServiceTime` on `drivers[].shifts[].itinerary[]`, `drivers[].shifts[].pinned`, or `freezeTime` | [Pinning stops](https://docs.timefold.ai/pickup-delivery-routing/latest/real-time-planning/real-time-planning-pinning-stops) |
| Keep a pinned stop's start service time | `pin: true` with `startServiceTime` on `drivers[].shifts[].itinerary[]` | [Pinning stops](https://docs.timefold.ai/pickup-delivery-routing/latest/real-time-planning/real-time-planning-pinning-stops) |

For a hard constraint that is not in this table, find its page in the
[PDR user guide](https://docs.timefold.ai/pickup-delivery-routing/latest/) before you explain it.
Don't link a URL that you did not open.

### Stop dependencies: what you can and cannot change

- **The dependencies are not an input field.** The model makes them from the order of the stops
  in a job: each stop depends on the stop before it. The input record shows no
  `dependencies` field, but the dependency rules still apply.
- **A job always finishes in one driver shift.** The model requires every dependent pair of
  stops to share one driver shift. Unlike Field Service Routing, no pooling or coordination
  setting relaxes this. `prohibitJobPooling` only controls whether other jobs can interleave with
  this job.
- **So a job that cannot fit in one shift is infeasible by itself.** Examples: its stops have
  time windows on different days, or its stops are pinned to different shifts. Explain it as a
  model rule, not as a setting the user turned on. Proposals that the user can act on are to align
  the stops' time windows to one shift, or to change the pinning. Splitting the job into separate
  jobs removes the order between its stops, so ask the user whether that order matters before
  you propose it. If the user needs a job to span shifts, say that this needs a model change
  and is a discussion for their Timefold contact.
- **Pinning fields in PDR:** `freezeTime`, `pinNextStopDuringFreeze`, `drivers[].shifts[].pinned`,
  and `pin` with `startServiceTime` on itinerary items. PDR has no `pinningRequested` field.

## Full instructions

Read and follow: `$SHARED/SKILL.md`

# Deep dives

Full workflow for investigating specific questions about a dataset. Read this file when the
user asks "why is X unassigned?", "why is Y assigned to Z?", or requests any per-item or
per-resource investigation.

## Why is a work item unassigned?

```bash
python $SCRIPTS/list_unassigned.py --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID
python $SCRIPTS/list_unassigned.py --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID --recommendations
```

`list_unassigned.py` shows each unassigned item with its requirements (skills, time, location).
`--recommendations` calls the recommendation API, which returns the top candidate resources
along with exactly which constraints would be violated by each assignment. It is the best tool for
explaining *why* no one can take a specific item.

**Recommendation call volume**: without `--recommendations`, all unassigned items are listed
(no API calls beyond the initial fetch). With `--recommendations`, the script makes one API
call per item and defaults to a cap of 50 items. Use `--limit N` to raise or lower that cap,
or `--limit 0` for all. Before calling with `--recommendations`, tell the user how many
unassigned items there are and ask whether they want recommendations for all of them or just
the first N, especially if there are more than 50.

If recommendations are empty or all carry hard violations: the item cannot be feasibly assigned
under current constraints. Explain which constraints block every candidate, e.g.:
- "No resource has the required skill"
- "All eligible resources are already at capacity for that time slot"
- "Assigning any candidate would exceed their weekly hour limit"

## Why does a hard violation remain after solving?

Follow "Explain every hard violation" in the shared `SKILL.md`: involved items, their raw input
records, the dataset configuration, pinning, and a docs link for each setting. Two points matter
most in a deep dive:

- **The constraint name is not the cause.** "Require the same vehicle shift" does not mean the
  input asked for the same shift. Find the field or the dataset default that switched the rule on.
- **Pinned items explain why the solver did not repair it.** The solver cannot move them, so a
  pinned placement that conflicts with another rule stays a hard violation. Check the pinning
  fields of every involved item before you explain why the solver "chose" the placement.

To test a fix before the user resubmits, change the suspect setting in the input or the
configuration and use the comparison technique below. The score analysis shows whether the hard
violations go away.

## Comparing two scenarios: the most powerful explanation technique

To understand why a specific assignment was or wasn't made, the most effective approach is:
**fetch the current score analysis → modify the assignment → re-POST → compare the diff**.

Steps:
1. Fetch current score analysis (baseline)
2. Fetch full input: `GET {collection_path}/{id}/input`
3. Modify the input JSON to force the assignment you want to test
4. POST to `{collection_path}/score-analysis?includeJustifications=true`
5. Compare: which constraints got worse (those are the reasons the solver avoided it)?

Use `score_violations.py` on the baseline to identify the constraints most likely to change.

## Why is resource X assigned to item Y?

1. Use `work_details.py` to see the item's requirements and who is assigned:
   ```bash
   python $SCRIPTS/work_details.py --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID --work-ids ID
   ```
2. Use `score_violations.py --constraint "..."` to see if any violated constraint
   specifically mentions this resource–item pair.
3. Use the comparison technique above to understand why the solver chose this resource
   over alternatives.

Be honest when the assignment is simply "the solver chose this from several equivalent options"; sometimes the score is the same for multiple candidates.

## Structural bottlenecks

Frame bottlenecks in two ways:

**By constraint**: run `score_violations.py` and sort by impact:
- Hard violations first, since they indicate infeasibility
- High-impact soft violations: systemic imbalance (fairness, cost, coverage)
- For each top violator: explain what business rule it represents

**By resource pool / time slot**: group unassigned items from `list_unassigned.py` by skill,
time window, or location. Clusters of unassigned items in the same window + skill = structural gap.
This is directly actionable: "You need more resources with [skill] available on [days/times]."

**Capacity math**: if many items are unassigned, check whether total demand exceeds theoretical
capacity. For Employee Shift Scheduling: employees × max shifts/week vs. weekly mandatory shift count.
For Field Service Routing: vehicles × max visits per shift vs. visit volume.
For Pick-up and Delivery Routing: drivers × max stops per shift vs. total stop volume.
A margin < 5% almost guarantees unassignment once scheduling constraints (rest rules, time windows, skill requirements) kick in.

## Adjusting soft constraint weights

Soft constraints have configurable weights that control how strongly the solver prioritizes
one objective over another. When a user wants to change the balance (e.g., "I want more
optional visits scheduled even if it means more travel"), the answer is to adjust the weight
of the relevant constraint in the **Configuration**, not to change the data or add new rules.

Key principle: **increasing a soft constraint's weight makes the solver work harder to satisfy
it**, at the cost of relaxing other soft constraints. The tradeoff is always between competing
soft objectives.

**Discovering available weights from the OpenAPI spec:**

Fetch `$OPENAPI_URL` and look for the schema of the configuration override object
(`config.model.overrides` in the request body). Any property whose name ends in `Weight`
is a constraint weight the user can adjust. The rest of the name identifies which constraint
it controls (e.g. `overtimeWeight`, `unscheduledVisitWeight`). Use these actual field names
when advising the user. Do not guess or use names from memory.

For each relevant weight, explain:
1. What constraint it controls (translate the field name to plain language)
2. What increasing it prioritizes, and what it trades off against

Weight changes are made in the dataset Configuration (visible in the platform Configuration
page linked at the top of the report). After changing weights, re-submit the dataset to see
the new result.

**Always frame weight adjustments as a tradeoff**: "Increasing the optional visit penalty
will schedule more optional work, but may increase total travel time and reduce fairness scores."

## Recommendations: what users can act on

Only suggest actions the user can take through input data or configuration. The two levers are:

**Input data changes** (add/modify data in the next submission):
- Add more resources (vehicles, employees) to increase overall capacity
- Extend or shift time windows for work items that are too restrictive to schedule
- Change required skills on work items (e.g., if a lower skill level is acceptable)
- Increase visit priority so optional items compete more strongly for slots
- Split or shorten work items that are too long to fit available slots

**Configuration changes** (adjust solver settings without changing data):
- Increase/decrease soft constraint weights to shift the balance between objectives
- Adjust overtime thresholds or cost parameters

Do **not** suggest:
- Implementing new constraints or changing how existing constraints work
- Writing code or modifying the model logic
- Any change that requires a developer or model change, since these are outside the user's control

If a finding can only be addressed by a model change, say so clearly and stop there:
"This pattern would require a change to the model configuration. That's a discussion for your
Timefold contact rather than something you can adjust in the input."

## Resource workload and fairness

```bash
python $SCRIPTS/resource_metrics.py --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID
python $SCRIPTS/resource_metrics.py --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID --sort overtime
python $SCRIPTS/resource_metrics.py --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID --filter "Name"
```

The script auto-flags resources with overtime, unpreference violations (Employee Shift Scheduling),
or significant underutilization (<85% of their threshold). Key metrics vary by model. Refer to
the model's metrics documentation URL (shown at the top of the `resource_metrics.py` output).

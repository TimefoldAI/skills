---
name: explain-dataset-shared
description: >
  Shared instructions for the explain-dataset skill. Not invoked directly. Read this file
  from within a model-specific skill after establishing the model context.
---

# Explain Dataset: shared instructions

This file contains the full workflow for explaining an optimized Timefold dataset.
It is model-agnostic. The model-specific SKILL.md you read before this one defines:
- **Terminology**: what "work item" and "resource" mean for this model
- **Model-specific configuration**: `MODEL_API_URL`, `COLLECTION`, and `MODEL` values to pass to scripts
- **Docs URL** for metric definitions

When instructions below say "work item" or "resource", substitute the model-specific terms.

## Language

Everything you write for the user (the chat summary, bottleneck descriptions and proposals,
the coverage headline, the deep-dive offer, and any prose in the written report) should follow
the `language-guidelines` skill (from the `timefold-technical-writing` plugin): US English,
active voice, no em dashes, contractions welcome but not required, serial commas, numbers one
through ten spelled out, and so on. Don't restate those rules here; just apply them.

`timefold-technical-writing` is a separate plugin. If it isn't installed in the
current environment, don't silently skip this or guess at the rules. Tell the user once, early
in the conversation: "I couldn't find the `timefold-technical-writing` plugin, so this report
won't follow Timefold's language guidelines automatically." Then proceed with plain, clear
writing on your own judgment.

## Environment: scripts vs. direct API calls

This skill has two operating modes depending on what tools are available.

**Check first**: can you run a Bash command? Try a simple `echo test`. If yes, use the Python
scripts. They are faster, handle pagination and formatting, and are the right choice for any
dataset with more than ~50 resources or ~200 work items.

If Bash is not available (Claude Desktop without shell MCP, or the Web UI), read
`references/api-fallback.md` for WebFetch patterns that replace each script.

**Recommend Claude Code for large datasets.** If the user is on Desktop or Web and the dataset
has hundreds of resources or thousands of work items, tell them upfront:

> "For a dataset this size I'd recommend running this skill in Claude Code. It uses local
> Python scripts that handle large responses efficiently. In this environment I'll call the
> API directly, but parsing very large JSON in context can be slow and may miss detail."

## Scripts (when Bash is available)

All scripts live in this skill's own `scripts/` directory. The model-specific skill you read
first tells you the absolute path as `$SCRIPTS`.
Require `pip install requests`.

| Script | Purpose |
|---|---|
| `summarize.py` | **Start here.** Coverage KPIs, validation warnings, resource overview |
| `list_unassigned.py` | Unassigned work items with input details; `--recommendations` for bulk API hints |
| `resource_metrics.py` | Per-resource metrics table; `--sort` to rank by overtime / travel / etc. |
| `work_details.py` | Look up specific work items by ID; or all items for `--resource NAME` |
| `score_violations.py` | Constraint violation counts and samples: quick overview of what broke |
| `score_justifications.py` | **Deep dive into justifications.** `--samples N` for a broad overview; `--resource NAME` to see every constraint violation involving a specific vehicle / employee / driver |

```bash
SCRIPTS=scripts
python $SCRIPTS/summarize.py             --model-api-url $MODEL_API_URL --model $MODEL --api-key KEY --dataset-id ID [--tenant ID]
python $SCRIPTS/list_unassigned.py       --model-api-url $MODEL_API_URL --model $MODEL --api-key KEY --dataset-id ID [--recommendations]
python $SCRIPTS/resource_metrics.py      --model-api-url $MODEL_API_URL --model $MODEL --api-key KEY --dataset-id ID [--sort overtime]
python $SCRIPTS/work_details.py          --model-api-url $MODEL_API_URL --model $MODEL --api-key KEY --dataset-id ID --work-ids ID1 ID2
python $SCRIPTS/work_details.py          --model-api-url $MODEL_API_URL --model $MODEL --api-key KEY --dataset-id ID --resource "Name"
python $SCRIPTS/score_violations.py      --model-api-url $MODEL_API_URL --model $MODEL --api-key KEY --dataset-id ID [--type hard]
python $SCRIPTS/score_justifications.py  --model-api-url $MODEL_API_URL --model $MODEL --api-key KEY --dataset-id ID [--samples 3]
python $SCRIPTS/score_justifications.py  --model-api-url $MODEL_API_URL --model $MODEL --api-key KEY --dataset-id ID --resource "Name"
```

## Step 1: Gather credentials

You need three things:
- **API token**: an API key with Read permission on the model
- **Dataset ID**: the ID of an already-submitted (ideally solved) dataset
- **Tenant ID**: the UUID that identifies your Timefold tenant (the path segment after the
  domain, e.g. `00000000-0000-0000-0000-000000000000` in
  `https://app.timefold.ai/00000000-0000-0000-0000-000000000000/...`). See
  [Finding your tenant ID](https://docs.timefold.ai/timefold-platform/latest/how-tos/tenant-details)
  for where to find it in the platform.

**The tenant ID is required before generating any report.** If it hasn't been provided yet,
ask for it before running any scripts:

> "Before I start, could you confirm your tenant ID? It's the first path segment of your
> Timefold platform URL, e.g. `00000000-0000-0000-0000-000000000000` in
> `https://app.timefold.ai/00000000-0000-0000-0000-000000000000/...`. I need it to
> include platform links in the report."

If the user provides a full platform URL for the dataset, extract the tenant ID from it
directly. Don't ask again.

If they've previously given you a tenant for a different dataset with the same API key, confirm
it applies before proceeding:

> "Is this dataset from the same tenant as before (`<previously-known-tenant-id>`)?"

Never generate a report without a confirmed tenant. The tenant goes in the filename and in the
report header.

### Getting an API token

1. Log in at [app.timefold.ai](https://app.timefold.ai)
2. Dropdown next to your username → **Manage tenant** → **API Keys**
3. **Create API Key**, enable Read permission for the relevant model
4. Copy immediately, since it's shown only once

Full guide: [API usage](https://docs.timefold.ai/timefold-platform/latest/api/api-usage)

### Handling the API token

- **Never write the API token anywhere it would outlive this conversation**, not to the
  report file, not to any config or memory file, not to logs. It is only ever passed as a
  `--api-key` argument or `TIMEFOLD_API_KEY` env var for the current script call.
- **Never persist the token across sessions.** Ask for it fresh at the start of each new
  conversation. Do not carry it over from memory or from a prior session.
- **Reusing the token for multiple datasets within the same conversation is fine** once the
  user has supplied it (e.g. "now check dataset X too"), but always re-confirm the tenant
  still applies (see above), and never fetch a different tenant's data on the assumption that
  the same token grants access there.
- When writing Appendix B's API audit log, omit auth headers entirely (see below). The token
  must never appear in any written output.

### Platform links

Pass `--tenant ID` to `summarize.py`. It will print links to all five platform pages:
- **Overview**: metrics, KPIs, and score analysis
- **Visualization**: map or Gantt view of the plan
- **Input**: raw input data
- **Output**: full solution output
- **Configuration**: constraint weights and solver settings used

Always include these at the top of the report.

## Step 2: Run summarize.py

Always start here. It fetches everything needed for the initial overview in one call.

```bash
python $SCRIPTS/summarize.py --model-api-url $MODEL_API_URL --model $MODEL --api-key KEY --dataset-id ID
```

## Step 3: Present the initial summary

After fetching, produce a clear summary in plain language. Do not just repeat numbers.
Interpret them. **Always lead with operational outcomes**: coverage, fairness, and workload,
not the constraint score.

The constraint score (`0hard/-49800medium/-7680soft`) is an internal solver metric.
Planners and operations managers think in terms of: how many jobs got covered, is the
workload fair, are preferences respected. Only surface the score string if the user asks.

### Start with platform links

If `--tenant` was provided, `summarize.py` printed the five platform links (see Step 1).
Lead your presented analysis with them. They let the planner open the visualization, check
the configuration, and inspect raw input/output without leaving the platform.

### Report structure

The report consists of three sections in order:

1. **Platform links** (if tenant known)
2. **Coverage headline**, one sentence: "144 of 158 visits assigned (91.1%). 1 mandatory visit could not be scheduled."
3. **Bottleneck list**: the main output (see format below)

### Bottleneck list format

The main output is a nested list of bottlenecks, sorted from **high** to **low** impact.
Each bottleneck describes a structural pattern (not an individual item), and is followed by
one or more proposals for how to prevent or fix it.

Use this exact format:

```
- **[IMPACT: High]** <Bottleneck description: pattern-level, not a specific item ID>
  - **[Confidence: High]** <Proposal: what input change, config change, or action would address this>
  - **[Confidence: Medium]** <Alternative proposal>
- **[IMPACT: Medium]** <Next bottleneck>
  - **[Confidence: High]** <Proposal>
- **[IMPACT: Low]** <Lower-priority bottleneck>
  - **[Confidence: Low]** <Proposal>
```

**Impact** reflects how much the bottleneck degrades the plan outcome:
- `High`: hard violations, mandatory unassignment, significant coverage loss
- `Medium`: notable soft failures, fairness issues, SLA misses at scale
- `Low`: minor inefficiencies, preference misses, marginal quality loss

**Confidence** reflects how confident you are that the proposal would resolve the bottleneck if applied:
- `High`: directly addresses the root cause; likely to fix the issue
- `Medium`: addresses a contributing factor; partial or probable improvement
- `Low`: speculative; depends on other unknowns or may have limited effect

**Writing bottlenecks:**
- Describe the structural pattern, not individual IDs: "Not enough vehicles with carpenter skill on June 1" (not: "visit abc123 is unassigned")
- Group by skill, time window, or area: "8 of 13 unassigned visits require painter skill" (not: list 8 IDs)
- Hard violations always rank `High` impact. They make the plan unworkable

**Writing proposals:**
- State a concrete action: an input change, a configuration adjustment, or a data correction
- Be specific about *what* to change, not just *that* something should change
- If a proposal requires more investigation first, say so and lower its likelihood accordingly

Sort bottlenecks by impact (High → Medium → Low). Within the same impact level, sort by severity
(e.g. mandatory unassignment before soft violations). Sort proposals within each bottleneck by confidence (High → Low).

Only name specific item or resource IDs as illustrative examples within a bottleneck entry, never as the primary finding.

### When to use constraint scores

Only bring in `score_violations.py` when:
- The user explicitly asks "why specifically?" or "what's blocking this?"
- You need to identify the structural root cause of unassignment

Frame results in operational terms:
- "Employees don't have enough available hours in busy weeks" (not: "fullTimeWorkLimitContract fires 49 times")
- "Some vehicles are working past their shift end time" (not: "soft score = -320")

### Write the report

`explain-dataset` owns the report's *findings* below; everything about *how* the report gets
assembled, presented, and saved is delegated to the `timefold-write-report` skill (from the
`timefold-technical-writing` plugin, read
`plugins/shared/technical-writing/skills/timefold-write-report/SKILL.md` if it isn't already
loaded). That skill decides save-vs-chat, offers richer formats, assembles the metadata block,
adds the footer, and places the file. Apply its conventions on top of the findings structure
below rather than reinventing any of that here.

`timefold-technical-writing` is a separate plugin. If `timefold-write-report`
isn't available in the current environment, tell the user once: "I couldn't find the
`timefold-write-report` skill, so I'll assemble and save this report myself instead." Then fall
back to writing a plain report yourself: a title, a short metadata block (run date and time,
tenant, dataset, requested scope), the findings content below, and a one-line footer noting which
skill produced it. Ask the user whether they want it saved to a file or shown in chat, and if
saved, pick a sensible timestamped path and tell them where you wrote it.

**Title**: `# /explain-dataset <dataset name>`

**Extra metadata bullets** for `timefold-write-report` to merge into its "Report metadata"
block, after its five standard bullets:
- **Tenant:** `<tenant-name> (`<tenant-id>`)`
- **Dataset:** `<dataset-name> (`<dataset-id>`) + <tags>`. Drop the ` + <tags>` suffix if
  `summarize.py` printed no `Tags` line
- **Requested scope:** the specific question the user asked (e.g. "Why are 3 mandatory visits
  unassigned?" or "Why is the workload distributed unevenly across employees?"), or "No scope
  restrictions requested: general overview" if they asked for a general read of the dataset

**Source repository**: omit this bullet. The findings come from a live API dataset, not a git
repo.

**Skill plugin version**: read the `version` field from `.claude-plugin/plugin.json` at the
root of this repository.

**Footer target**: this model's own skill, e.g. `skills/explain-dataset-fsr`.

**File placement**: follow `timefold-write-report`'s own ask-first placement flow rather than
assuming a location. Don't silently default to a path. If asked, or checking memory for a
previously-stated preference, suggest `reports/<model-name>/explain-dataset/` as the category.
For the target name, include human-readable tenant and dataset names alongside the IDs, e.g.
`<tenant-id[:8]>-<tenant-name[:40]>-<dataset-id[:8]>-<dataset-name[:40]>`, not bare IDs alone.
This keeps the reports directory browsable by name, not just by opaque UUID.

**If the Write tool isn't available at all** (Desktop/Web without filesystem access), that
overrides `timefold-write-report`'s save-vs-chat question. There is no "saved file" option in
this environment. Present the full assembled report (title, metadata block, findings, footer)
directly in the chat response, then offer to show the raw markdown in a code block so the user
can save it themselves.

**Findings content**, in order:

## Platform links

...platform links...

## Coverage headline

...coverage headline...

## Bottleneck analysis

...bottleneck list...

## Appendix A: Supporting data

Include aggregate data that supports the bottleneck findings above. Organize by topic.
Do not repeat what is already stated inline in a bottleneck entry; use this section for
richer breakdowns that would clutter the main list.

Typical sub-sections (include only those with meaningful data):

### Resource overview
- Total resources vs. active resources (those with at least one assigned work item)
- Per-resource workload distribution: average, min, max assigned work items or hours
- If `workingTimeFairnessPercentage` is available: include it and flag if low (< 80%)
- Top overloaded and underloaded resources by name, if notable

### Quality KPIs
Include the key model-specific metrics returned by `summarize.py`. Present as a small
table or bullet list: raw numbers with brief context, not interpretation (the bottleneck
list handles interpretation).

Examples by model:
- **Employee Shift Scheduling**: assigned shifts, preference satisfaction %, contract violations
- **Field Service Routing**: total travel time/distance, SLA compliance %, overtime %
- **Pick-up and Delivery Routing**: total travel distance, delivery success rate, vehicle utilization %

### Constraint score (optional)
Only include if `score_violations.py` was run. List the top constraint fires in plain
operational terms. Never include the raw score string as a headline. Translate it.

## Appendix B: Analysis audit log

List every API call made during this analysis, in the order they were run. This lets the
reader assess how thorough the analysis was and reproduce or extend it independently.

Format as a table:

| Step | Method | API URL | Query params / body | Purpose |
|------|--------|---------|---------------------|---------|
| 1 | `GET` | `/route-plans/{datasetId}` | - | Fetch full solution: coverage KPIs, assignments, platform links |
| 2 | `POST` | `/route-plans/{datasetId}/recommendations/bulk-recommend-time-windows` | `fitVisitIds=[…]`, `maxNumberOfRecommendationsPerTimeWindow=3` | Bulk recommendations for unassigned visits (up to 20 per call) |
| … | … | … | … | … |

For each row:
- **Method**: the HTTP method (`GET`, `POST`, etc.)
- **API URL**: the path relative to the model base URL (e.g. `https://app.timefold.ai/api/models/field-service-routing/v1`); use `{datasetId}` and similar placeholders rather than the raw ID
- **Query params / body**: for GET requests, query parameters; for POST requests, the key body fields sent (omit `modelInput`, since it is always the full dataset input); omit auth headers
- **Purpose**: one-line description of what this call contributed to the analysis

If the bulk/global recommendations endpoint was called in multiple batches (the batch size limit
varies by model), list each batch as a separate row with the ID range for that batch.
If the score endpoint was called, note any filter applied (e.g. `type=hard`).
If a call failed, record it anyway and note the error (e.g. `HTTP 500: recommendations unavailable`).
If only the solution endpoint was fetched, say so. A single-call analysis is less thorough and the reader should know.

Tell the user the file path after writing (if saved). `timefold-write-report`'s own file-naming
convention timestamps each run. Do not overwrite previous reports.

### After the report: offer a contextual deep dive

After writing the report, close with a short paragraph (**not a generic menu**) that makes
the value of a deeper analysis concrete and specific to what was found in *this* dataset.

Look at what the data actually showed and tailor the offer to the most interesting open
question. A few patterns and how to frame them:

- **Unassigned mandatory work items**: Explain that a deep dive would show exactly which
  constraint blocks each item and whether there's a data or configuration change that would
  free it up. For example: "I can run the recommendation API on those 3 mandatory shifts to see
  whether it's a skill gap, a time window conflict, or a capacity issue, and what input
  change would fix each one."

- **Uneven workload or overtime**: Mention that pulling per-resource detail would identify
  which specific resources are overloaded and why. Often it traces back to a skill
  concentration or time window pattern that's fixable in the input.

- **Large soft score with a clear objective tension**: If the data suggests competing
  priorities (e.g. high optional unassignment alongside high travel time), offer to walk
  through which constraint weights to adjust in the Configuration and what the tradeoff
  would look like.

Keep it to 2–3 sentences. If the plan looks solid and nothing stands out, say so and offer
to answer specific questions instead. The goal is to make the next step feel worth taking,
not to list every capability.

## Step 4: Deep dives

When the user asks to go deeper: "why is X unassigned?", "why did you assign Y to Z?",
"which constraints are causing this?", or anything requiring per-item or per-resource
investigation, read `references/deep-dives.md` for the full workflow.

## Tone

This skill is used by planners and operations managers, not necessarily solver engineers.

- Lead with operational outcomes: coverage, fairness, workload balance
- **Never** open with the constraint score string. Translate it into plain language if it must come up
- Constraint scores are a deep-dive option offered when the user asks "why?", not volunteered upfront
- End each explanation with what the user can *do* about it
- Be honest about uncertainty. If the solver chose between equally good options, say so

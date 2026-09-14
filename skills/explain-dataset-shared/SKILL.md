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
the `language-guidelines` skill: US English, active voice, no em dashes, contractions welcome but
not required, serial commas, numbers one through ten spelled out, and so on. Don't restate those
rules here; just apply them.

`language-guidelines` ships in this plugin, next to this skill. Read
`../language-guidelines/SKILL.md` if it isn't already loaded. If you genuinely cannot reach it,
don't silently skip this or guess at the rules. Tell the user once, early in the conversation:
"I couldn't find the `language-guidelines` skill, so this report won't follow Timefold's language
guidelines automatically." Then proceed with plain, clear writing on your own judgment.

## Environment: find a runtime first

The scripts need nothing more than Python 3.9 or later. They use the standard library only, so
there is no package to install and no virtual environment to create.

**Run this check once, before Step 1.** It sets `$PY`. Use `$PY` for every script command in
this skill:

```bash
PY=""
uv --version >/dev/null 2>&1 && PY="uv run"
if [ -z "$PY" ]; then
  for c in python3 python; do
    "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null \
      && PY="$c" && break
  done
fi
echo "runner: ${PY:-none}"
```

The loop runs the candidate, and it does not only look for the name. This matters on Windows,
where `python` can be a Microsoft Store stub that is on the PATH but does not work.

If a runner is found, use the scripts. They are faster, they handle pagination and formatting,
and they are the correct choice for any dataset with more than ~50 resources or ~200 work items.

**If no runner is found, do not stop and do not ask the user to install Python.** Drop to the
next level of this ladder:

| Level | Condition | What to do |
|---|---|---|
| 1 | `uv` is on the PATH | `PY="uv run"`, and uv downloads a Python if necessary |
| 2 | Python 3.9+ is on the PATH | `PY=python3` or `PY=python` |
| 3 | Bash works, but no Python | Call the API with `curl`; see `references/api-fallback.md` |
| 4 | No shell at all | Call the API with WebFetch; see `references/api-fallback.md` |

`curl` is present on macOS, on Linux, and on Windows 10 and later, so level 3 works almost
everywhere. Level 4 covers Claude Desktop without a shell MCP, and the Web UI.

**uv is not a prerequisite.** It is only the best level. Level 2 needs no installation on almost
every macOS and Linux machine, and levels 3 and 4 answer the same questions without Python. Never
tell the user that something is missing before you have tried all four levels.

**Tell the user which level you use, once, at the start.** At level 3 or 4 add this:

> "I don't see Python here, so I'll call the Timefold API directly. That works, but on a large
> dataset it is slower and I can miss detail."

**At level 3, offer to install uv. Do not install it without a yes.** The installer downloads and
runs a script from the internet, so the user decides. Show the command that applies to their
system, and continue at level 3 if they decline or do not answer:

> "Optional: if you install uv, I can use the local scripts instead, which is faster and keeps
> large payloads out of this conversation. It is one binary, it needs no administrator rights,
> and it changes nothing about your system Python. Shall I run this?
>   macOS and Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
>   Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
> Otherwise I'll carry on calling the API directly, which works fine."

The installer puts `uv` in `~/.local/bin`, which the current shell may not have on its PATH. After
an install, set `PY="$HOME/.local/bin/uv run"` for this session rather than starting a new shell.

**Recommend Claude Code for large datasets.** If the user is on Desktop or Web and the dataset
has hundreds of resources or thousands of work items, tell them upfront:

> "For a dataset this size I'd recommend running this skill in Claude Code. It uses local
> Python scripts that handle large responses efficiently. In this environment I'll call the
> API directly, but parsing very large JSON in context can be slow and may miss detail."

## Scripts (levels 1 and 2)

All scripts live in this skill's own `scripts/` directory. The model-specific skill you read
first tells you the absolute path as `$SCRIPTS`.

| Script | Purpose |
|---|---|
| `summarize.py` | **Start here.** Coverage KPIs, validation warnings, resource overview |
| `list_unassigned.py` | Unassigned work items with input details; `--recommendations` for bulk API hints |
| `resource_metrics.py` | Per-resource metrics table; `--sort` to rank by overtime / travel / etc. |
| `work_details.py` | Look up specific work items by ID; or all items for `--resource NAME` |
| `score_violations.py` | Constraint violation counts and samples: quick overview of what broke |
| `score_justifications.py` | **Deep dive into justifications.** `--samples N` for a broad overview; `--resource NAME` to see every constraint violation involving a specific vehicle / employee / driver |

```bash
SCRIPTS=scripts     # $PY comes from the runtime check above
$PY $SCRIPTS/summarize.py             --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID [--tenant ID]
$PY $SCRIPTS/list_unassigned.py       --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID [--recommendations]
$PY $SCRIPTS/resource_metrics.py      --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID [--sort overtime]
$PY $SCRIPTS/work_details.py          --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID --work-ids ID1 ID2
$PY $SCRIPTS/work_details.py          --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID --resource "Name"
$PY $SCRIPTS/score_violations.py      --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID [--type hard]
$PY $SCRIPTS/score_justifications.py  --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID [--samples 3]
$PY $SCRIPTS/score_justifications.py  --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID --resource "Name"
```

## What every request carries

Every call to a Timefold installation carries one extra query parameter, `tfSource`. It tells
Timefold that the call came from these skills, and which skill and script made it:

```
tfSource=timefold-skills.explain-dataset-ess.summarize~0.3.0
         ^ product        ^ skill              ^ script   ^ skill version
```

The scripts add it by themselves. You add nothing. At level 3 and level 4 you add it yourself to
each request, because there is no script to do it for you. See `references/api-fallback.md`.

Every call also carries a `User-Agent` header that names the skills and their version:

```
User-Agent: timefold-skills/0.5.0 (+https://github.com/TimefoldAI/skills)
```

This one is not optional. Python sends `Python-urllib/3.x` when a script sets no user agent, and an
installation behind a web application firewall rejects that signature before the request reaches
the API. US production does exactly this, and answers `HTTP 403` with Cloudflare error 1010,
`browser_signature_banned`, whatever the API key says. The scripts set the header themselves. At
level 3 and level 4 you set it yourself. See `references/api-fallback.md`.

Both values identify the skill, not the user. They carry no tenant ID, no dataset ID, no API key,
and nothing the URL does not already carry. If a user asks what the skill sends to Timefold, tell
them exactly this, and point at `scripts/timefold_api.py` where they can read the code.

**A 403 is not always the key.** If a script or a `curl` call returns `HTTP 403` and the body names
Cloudflare, a browser signature, or a firewall, the request never reached the API. Do not send the
user off to check their key permissions. Check the user agent first.

## Step 1: Gather credentials

You need three things:
- **API key**: an API key with Read permission on the model, exported as `TIMEFOLD_API_KEY` in the
  environment the scripts run in. You never handle the key yourself. See
  "The API key stays out of the conversation" below.
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

### Getting an API key

Tell the user to do this themselves. Don't offer to do it for them.

1. Log in at [app.timefold.ai](https://app.timefold.ai)
2. Dropdown next to your username → **Manage tenant** → **API Keys**
3. **Create API Key**, enable Read permission for the relevant model
4. Copy immediately, since it's shown only once

Full guide: [API usage](https://docs.timefold.ai/timefold-platform/latest/api/api-usage)

### The API key stays out of the conversation

The scripts read the key from the `TIMEFOLD_API_KEY` environment variable, and they accept no
`--api-key` argument. That is deliberate. A key on a command line lands in your context, in the
transcript, and in the shell history, and a key that reaches your context can leak from there into
a report, a log, or a later summary. The safest key is the one you never see.

So:

- **Never ask the user to paste the key into the chat**, and never put it in a command you run.
  If the user pastes it anyway, tell them once that you cannot remove it from the transcript, and
  recommend they revoke that key under **Manage tenant** → **API Keys** and issue a new one.
- **Check whether the key is set** before you run anything, and check it without printing it:
  ```bash
  [ -n "${TIMEFOLD_API_KEY:-}" ] && echo "TIMEFOLD_API_KEY is set" || echo "TIMEFOLD_API_KEY is missing"
  ```
- **If it's missing, ask the user to export it in their own shell**, then start the agent session
  again from that same shell so the scripts inherit it:
  ```bash
  export TIMEFOLD_API_KEY=<your-api-key>
  ```
  Exporting it from inside the session does not help. Each command you run gets a fresh shell, so
  the value would not survive to the next call, and it would sit in the transcript besides. A shell
  profile or a secret manager is the right home for it. A checked-in config file is not.
- **Never write the key anywhere it would outlive the run**, not to the report file, not to a
  config or memory file, not to logs, and not to a memory you keep between sessions.
- **The same key covers more datasets in the same conversation**, but always re-confirm the tenant
  still applies (see above). Never fetch another tenant's data on the assumption that the same key
  grants access there.
- When writing Appendix B's API audit log, omit auth headers entirely (see below). The key must
  never appear in any written output.

`TIMEFOLD_TENANT` and `TIMEFOLD_PLATFORM_URL` work the same way, and the scripts read them from the
environment too. Neither is a secret, so passing `--tenant` or `--platform-url` on the command line
is fine when the user gives you those values in the conversation.

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
$PY $SCRIPTS/summarize.py --model-api-url $MODEL_API_URL --model $MODEL --dataset-id ID
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
assembled, presented, and saved is delegated to the `timefold-write-report` skill (read
`../timefold-write-report/SKILL.md` if it isn't already loaded). That skill decides
save-vs-chat, assembles the metadata block, adds the footer, and places the file. Apply its
conventions on top of the findings structure below rather than reinventing any of that here.

The report is Markdown, and it serves two readers. A planner reads it to understand the plan. An
agent reads it later, in a fresh session, to answer a follow-up question about the same dataset.
The second reader is why the metadata block and the audit log below matter as much as the
findings: together they say which dataset the findings describe and which calls produced them, so
the next session can pick the file up cold and keep going instead of starting over.

`timefold-write-report` ships in this plugin, next to this skill. If you genuinely cannot reach
it, tell the user once: "I couldn't find the
`timefold-write-report` skill, so I'll assemble and save this report myself instead." Then fall
back to writing a plain report yourself: a title, a short metadata block (run date and time,
tenant, dataset, requested scope), the findings content below, and a one-line footer noting which
skill produced it. Ask the user whether they want it saved to a file or shown in chat, and if
saved, pick a sensible timestamped path and tell them where you wrote it.

**Title**: `# /explain-dataset <dataset name>`

**Extra metadata bullets** for `timefold-write-report` to merge into its "Report metadata"
block, after its standard bullets:
- **Tenant:** `<tenant-name> (`<tenant-id>`)`
- **Dataset:** `<dataset-name> (`<dataset-id>`) + <tags>`. Drop the ` + <tags>` suffix if
  `summarize.py` printed no `Tags` line
- **Requested scope:** the specific question the user asked (e.g. "Why are 3 mandatory visits
  unassigned?" or "Why is the workload distributed unevenly across employees?"), or "No scope
  restrictions requested: general overview" if they asked for a general read of the dataset

**Source**: the findings come from a live API dataset, not a git repo, so replace
`timefold-write-report`'s "Source repository" bullet with these two:
- **Model:** `<model display name> (`<model-key>`)`, e.g. `Field Service Routing
  (`field-service-routing`)`
- **Model API URL:** the `$MODEL_API_URL` you ran the scripts against

Those two, plus the tenant and dataset bullets above, are what let a later session re-fetch this
same dataset. The model key alone is not enough, because the same key runs on more than one
platform installation. Never write the API key into the report. The reader supplies their own.

**Skill plugin version**: resolve it from the directory these skills are installed in, never
from the user's working directory. The working directory is the user's own project, which is not
this plugin, so a lookup there finds nothing. Try these in order and stop at the first that
works:

1. `cat $SHARED/VERSION`. This stamp ships inside the skill folder, so it survives every
   install shape, including the ones that copy the skill folders and leave the plugin manifest
   behind.
2. The `version` field of `$PLUGIN_ROOT/.claude-plugin/plugin.json`, for an install that keeps
   the manifest.
3. Only if both are missing, report the version as not available, and name the two paths you
   looked in.

`$SHARED` and `$PLUGIN_ROOT` are the variables the model-specific skill set before it sent you
here.

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
reader assess how thorough the analysis was, and it tells the next session which ground the
analysis already covered and which endpoints are still open. A follow-up question usually starts
from a call listed here, either by repeating it with a narrower filter or by calling something
this run never touched.

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

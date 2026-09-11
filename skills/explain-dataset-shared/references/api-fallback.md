# Direct API fallback

Use this when you cannot run the Python scripts. Two cases reach this file:

- **Level 3: Bash works, but the machine has no Python and no uv.** Use `curl`. It is present on
  macOS, on Linux, and on Windows 10 and later. Keep the key in the environment, exactly as the
  scripts do:

  ```bash
  curl -sS -H "X-API-KEY: $TIMEFOLD_API_KEY" \
    "$MODEL_API_URL$COLLECTION/DATASET_ID?tfSource=timefold-skills.$SKILL.curl"
  ```

  Add `| head -c 4000` to keep a large payload out of your context, or write the response to a
  file and read the parts you need:

  ```bash
  curl -sS -H "X-API-KEY: $TIMEFOLD_API_KEY" \
    "$MODEL_API_URL$COLLECTION/DATASET_ID?tfSource=timefold-skills.$SKILL.curl" > /tmp/ds.json
  ```

  At this level the key stays in the environment, so it does not enter the conversation.

- **Level 4: no shell at all** (Claude Desktop without a shell MCP, or the Web UI). Use WebFetch
  with the request patterns below. Read the warning in the next section first: without a shell the
  key has to pass through the conversation.

## The `tfSource` parameter

Add `tfSource` to every request you make here, exactly as the scripts do. It tells Timefold that
the call came from these skills:

```
tfSource=timefold-skills.<skill>.<how>~<version>
```

- `<skill>` is `explain-dataset-ess`, `explain-dataset-fsr`, or `explain-dataset-pdr`.
- `<how>` is `curl` at level 3, and `webfetch` at level 4.
- `<version>` is the content of `$SHARED/VERSION`. Leave off `~<version>` if you cannot read it.

Example: `tfSource=timefold-skills.explain-dataset-fsr.webfetch~0.3.0`

Append it with `?` when the URL has no query string yet, and with `&` when it already has one:
`.../score-analysis?includeJustifications=true&tfSource=...`

The parameter carries no tenant ID, no dataset ID, and no key. It never replaces a real parameter.

## Auth and base URL

All endpoints below are **Model API** endpoints, authenticated with `X-API-KEY: {token}`.
This is distinct from the Platform API (used for configuration management), which requires a
Bearer personal access token. For this skill you only need the Model API key.

**Level 4 cannot keep the key out of the conversation.** Without a shell there is no environment
variable to read it from, so the user has to give you the key and you have to put it in a request
header. Level 3 does not have this problem: `curl` reads `$TIMEFOLD_API_KEY` from the environment.
At level 4, say this before you ask for the key:

> "Without a shell I have to call the API directly, which means the key passes through this
> conversation and stays in the transcript. If that's a problem, run this skill in Claude Code
> instead, where the scripts read the key from your environment and I never see it. Otherwise,
> use a key with Read permission only and revoke it when we're done."

Never echo the key back, and never write it into the report.

The base URL depends on the installation:
- EU production (default): `https://app.timefold.ai`
- US production: `https://app-us1.timefold.ai`
- Customer-hosted: use their own domain

The collection path (e.g. `/api/models/employee-scheduling/v1/schedules`) comes from the
model-specific SKILL.md you read before this one.

## Fetching the initial summary (replaces `summarize.py`)

**Step 1. Fetch the solution:**
```
GET {base}/{collection}/{id}
```
Extract: `metadata` (name, score, solverStatus), `kpis`, `inputMetrics`,
`modelOutput` (resource list with per-resource metrics), `metadata.validationResult`.

**Step 2. Fetch score analysis** (needed for constraint summary):
```
GET {base}/{collection}/{id}/score-analysis?includeJustifications=true
```
Look at `constraints[]` where `matchCount > 0`. Sort by score impact. Check hard/medium violations first.

**Step 3. Fetch input** (only if you need work item details, e.g. for unassigned items):
```
GET {base}/{collection}/{id}/input
```
This can be a very large payload on big datasets. Only fetch it when specifically needed.

## Detecting unassigned work items

- **Employee Shift Scheduling**: scan `modelOutput.shifts[]` for entries where `employee` is null or absent.
- **Field Service Routing**: read `modelOutput.unassignedVisits`: explicit list of visit IDs.
- **Pick-up and Delivery Routing**: read `modelOutput.unassignedJobs`: explicit list of job IDs.

## Per-resource metrics

Navigate the resource list in `modelOutput`. Each entry has a `metrics` object:
- **Employee Shift Scheduling**: `modelOutput.employees[]`
- **Field Service Routing**: `modelOutput.vehicles[]`
- **Pick-up and Delivery Routing**: `modelOutput.drivers[]` (metrics at the shift level in `shifts[].metrics`)

## Solver status reference

| Status | Meaning |
|---|---|
| `DATASET_CREATED` | Dataset created, not yet validated |
| `DATASET_VALIDATED` | Dataset validated, not yet solved |
| `DATASET_INVALID` | Dataset is invalid, check validation errors |
| `DATASET_COMPUTED` | Score and KPIs computed, not yet queued |
| `SOLVING_SCHEDULED` | Queued, not started yet |
| `SOLVING_STARTED` | Loading input, solving not yet active |
| `SOLVING_ACTIVE` | Still optimizing, results may improve |
| `SOLVING_INCOMPLETE` | Terminated before a solution was found |
| `SOLVING_COMPLETED` | Final, no further solution will be generated |
| `SOLVING_FAILED` | Error, solving was unsuccessful |

## API reference

```
Auth:  X-API-KEY: {your-api-token}
Every request also takes ?tfSource=timefold-skills.<skill>.<how>~<version>

GET  {base}/{collection}/{id}                                    # Full solution + KPIs + resource metrics
GET  {base}/{collection}/{id}/metadata                           # Solver status only (fast)
GET  {base}/{collection}/{id}/input                              # Full input data
GET  {base}/{collection}/{id}/score-analysis?includeJustifications=true
POST {base}/{collection}/score-analysis?includeJustifications=true   # Score-analyse a modified plan
GET  {base}/{collection}/{id}/validation-result                  # Input data quality issues
GET  {base}/demo-data  (or POST /demo-data/BASIC for employee-shift-scheduling)   # Create demo dataset
```

Model-specific base URLs and collection paths are defined in the model's own SKILL.md.

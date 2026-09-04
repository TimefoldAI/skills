# Direct API fallback

Use this when Bash is not available and you cannot run the Python scripts.

## Auth and base URL

All endpoints below are **Model API** endpoints, authenticated with `X-API-KEY: {token}`.
This is distinct from the Platform API (used for configuration management), which requires a
Bearer personal access token. For this skill you only need the Model API key.

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
Auth: X-API-KEY: {your-api-token}

GET  {base}/{collection}/{id}                                    # Full solution + KPIs + resource metrics
GET  {base}/{collection}/{id}/metadata                           # Solver status only (fast)
GET  {base}/{collection}/{id}/input                              # Full input data
GET  {base}/{collection}/{id}/score-analysis?includeJustifications=true
POST {base}/{collection}/score-analysis?includeJustifications=true   # Score-analyse a modified plan
GET  {base}/{collection}/{id}/validation-result                  # Input data quality issues
GET  {base}/demo-data  (or POST /demo-data/BASIC for employee-shift-scheduling)   # Create demo dataset
```

Model-specific base URLs and collection paths are defined in the model's own SKILL.md.

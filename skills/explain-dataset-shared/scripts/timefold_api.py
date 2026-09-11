"""
Shared utilities for Timefold API scripts.

Model-specific configuration (base URLs, collection paths, field names) lives in each model's own plugin directory — not here.

Two distinct APIs, two distinct auth schemes:

  Model API — base URL passed via --model-api-url; authenticated with X-API-KEY.
                Covers /api/models/<model>/<version>/..., /api/aboutme

  Platform API — base URL derived from --platform-url; authenticated with Bearer PAT
                 + X-TF-TENANT-ID header. Covers /api/platform/v1/...

Known production platform installations (pass to --platform-url or set TIMEFOLD_PLATFORM_URL):
  https://app.timefold.ai        EU production (default)
  https://app-us1.timefold.ai   US production

Usage in model skill scripts:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from timefold_api import model_api_get, fmt, add_common_args, resolve_args

Requirements: Python 3.9 or later. The standard library only — no packages to install.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT_SECONDS = 30


class TimefoldApiError(RuntimeError):
    """A call to a Timefold installation failed.

    Its own class, so run() can report it as one clear line and still let a real bug
    in a script raise a traceback.
    """

# ---------------------------------------------------------------------------
# Usage tracking
#
# Every request to a Timefold installation carries one extra query parameter, so
# Timefold can tell which traffic came from these skills. It identifies the skill,
# not the user: no tenant, no dataset, no key, and nothing the URL does not already
# carry. To rename the parameter, change SOURCE_PARAM here and in
# references/api-fallback.md, which documents the same parameter for the curl and
# WebFetch fallbacks.
#
# Value format:  timefold-skills.<skill>.<script>~<version>
#   e.g.         timefold-skills.explain-dataset-ess.summarize~0.3.0
# Split on "~" for the version, then on "." for the parts. Unknown parts are left
# out, so the value is never shorter than "timefold-skills".
# ---------------------------------------------------------------------------

SOURCE_PARAM = "tfSource"
SOURCE_PREFIX = "timefold-skills"

_source = SOURCE_PREFIX


def skill_version():
    """Return the skill version stamp, or None if neither version file is readable."""
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    version_file = os.path.join(scripts_dir, os.pardir, "VERSION")
    try:
        with open(version_file, encoding="utf-8") as handle:
            stamp = handle.read().strip()
        if stamp:
            return stamp
    except OSError:
        pass
    manifest = os.path.join(scripts_dir, os.pardir, os.pardir, os.pardir,
                            ".claude-plugin", "plugin.json")
    try:
        with open(manifest, encoding="utf-8") as handle:
            return json.load(handle).get("version") or None
    except (OSError, ValueError):
        return None


def set_source(skill=None, script=None, version=None):
    """Build the value of the usage parameter that every later request carries.

    resolve_args() calls this, so the entry-point scripts need no change.
    """
    global _source
    parts = [SOURCE_PREFIX]
    for part in (skill, script):
        if part:
            parts.append(str(part))
    value = ".".join(parts)
    if version:
        value += "~" + str(version)
    _source = value
    return _source


def get_source():
    """Return the current value of the usage parameter."""
    return _source


# ---------------------------------------------------------------------------
# HTTP layer — standard library only, so the scripts run on any Python 3
# ---------------------------------------------------------------------------

def _request(method, url, headers, params=None, body=None):
    """Send one JSON request and return the decoded response body.

    Raises RuntimeError with the status, the URL and the start of the error body.
    """
    pairs = [(k, v) for k, v in (params or {}).items() if v is not None]
    if not any(k == SOURCE_PARAM for k, _ in pairs):
        pairs.append((SOURCE_PARAM, _source))
    separator = "&" if "?" in url else "?"
    url = url + separator + urllib.parse.urlencode(pairs, doseq=True)

    headers = dict(headers)
    headers.setdefault("Accept", "application/json")
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        detail = ""
        try:
            detail = error.read().decode("utf-8", "replace").strip()
        except Exception:
            pass
        if len(detail) > 500:
            detail = detail[:500] + " ..."
        message = f"HTTP {error.code} {error.reason} for {method} {url}"
        raise TimefoldApiError(f"{message}\n{detail}" if detail else message) from None
    except urllib.error.URLError as error:
        raise TimefoldApiError(f"Cannot reach {url}: {error.reason}") from None

    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError as error:
        raise TimefoldApiError(f"{url} did not return JSON: {error}") from None


# ---------------------------------------------------------------------------
# Platform base URL — configurable per installation
# ---------------------------------------------------------------------------

KNOWN_PLATFORM_URLS = {
    "eu":      "https://app.timefold.ai",
    "us":      "https://app-us1.timefold.ai",
}

DEFAULT_PLATFORM_BASE = KNOWN_PLATFORM_URLS["eu"]

# Module-level default: can be overridden by env var; individual calls can override further.
PLATFORM_BASE = os.environ.get("TIMEFOLD_PLATFORM_URL", DEFAULT_PLATFORM_BASE).rstrip("/")


def _pb(platform_base=None):
    """Return the effective platform base URL, stripped of trailing slash."""
    return (platform_base or PLATFORM_BASE).rstrip("/")


# ---------------------------------------------------------------------------
# Model API helpers — authenticated with X-API-KEY
# ---------------------------------------------------------------------------

def model_api_get(base_url, path, api_key, params=None):
    """GET {base_url}{path} with X-API-KEY auth. Raises on HTTP errors."""
    return _request("GET", base_url + path, {"X-API-KEY": api_key}, params=params)


def model_api_post(base_url, path, api_key, body, params=None):
    """POST {base_url}{path} with X-API-KEY auth. Raises on HTTP errors."""
    return _request("POST", base_url + path, {"X-API-KEY": api_key}, params=params, body=body)


def _aboutme_tenants(api_key, platform_base=None):
    """Call /api/aboutme and return the tenants list."""
    payload = _request("GET", _pb(platform_base) + "/api/aboutme", {"X-API-KEY": api_key})
    return (payload or {}).get("tenants", [])


def get_tenant_name(tenant_id, api_key, platform_base=None):
    """Return the display name for a tenant UUID, or None if not found."""
    try:
        tenants = _aboutme_tenants(api_key, platform_base)
        for t in tenants:
            if t.get("id") == tenant_id:
                return t.get("name")
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Platform API helpers — authenticated with Bearer PAT + X-TF-TENANT-ID
# Base path: {platform_base}/api/platform/v1
# ---------------------------------------------------------------------------

def platform_api_get(path, pat, tenant_id, platform_base=None):
    """GET from the Platform API with Bearer PAT + X-TF-TENANT-ID header."""
    return _request(
        "GET",
        _pb(platform_base) + "/api/platform/v1" + path,
        {"Authorization": f"Bearer {pat}", "X-TF-TENANT-ID": tenant_id},
    )


def platform_api_post(path, pat, tenant_id, body, platform_base=None):
    """POST to the Platform API with Bearer PAT + X-TF-TENANT-ID header."""
    return _request(
        "POST",
        _pb(platform_base) + "/api/platform/v1" + path,
        {"Authorization": f"Bearer {pat}", "X-TF-TENANT-ID": tenant_id},
        body=body,
    )


# ---------------------------------------------------------------------------
# Solver status helpers
# ---------------------------------------------------------------------------

# Full lifecycle: https://docs.timefold.ai/timefold-platform/latest/how-tos/run-lifecycle
_SOLVER_STATUS_NOTES = {
    "DATASET_CREATED":    "dataset created, not yet validated",
    "DATASET_VALIDATED":  "dataset validated, not yet solved",
    "DATASET_INVALID":    "dataset is invalid — check validation errors",
    "DATASET_COMPUTED":   "score and KPIs computed, not yet queued",
    "SOLVING_SCHEDULED":  "queued, not started yet",
    "SOLVING_STARTED":    "loading input, solving not yet active",
    "SOLVING_ACTIVE":     "still optimizing — results may improve",
    "SOLVING_INCOMPLETE": "terminated before a solution was found",
    "SOLVING_COMPLETED":  "final — no further solution will be generated",
    "SOLVING_FAILED":     "error — solving was unsuccessful",
}

TERMINAL_STATUSES = {"DATASET_INVALID", "SOLVING_INCOMPLETE", "SOLVING_COMPLETED", "SOLVING_FAILED"}
ACTIVE_STATUSES   = {"SOLVING_SCHEDULED", "SOLVING_STARTED", "SOLVING_ACTIVE"}


def fmt_solver_status(status):
    """Return a human-readable note for a solver status string."""
    return _SOLVER_STATUS_NOTES.get(status, "unknown status")


def is_terminal(status):
    """Return True if the run has reached a final state (no further changes expected)."""
    return status in TERMINAL_STATUSES


def is_active(status):
    """Return True if the run is still in progress."""
    return status in ACTIVE_STATUSES


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def fmt(iso):
    """Convert ISO 8601 duration to a compact human-readable string.
    Examples: 'PT40H' → '40h', 'PT1H30M' → '1h30m', 'PT0S' → '0h', None → '—'
    """
    if not iso or iso in ("PT0S", "P0D"):
        return "0h"
    h_match = re.search(r"(\d+)H", iso)
    m_match = re.search(r"(\d+)M", iso)
    hours = int(h_match.group(1)) if h_match else 0
    mins = int(m_match.group(1)) if m_match else 0
    if hours and mins:
        return f"{hours}h{mins}m"
    return f"{hours}h" if hours else f"{mins}m"


def seconds(iso):
    """Convert ISO 8601 duration to total seconds. Returns 0 for None or zero durations."""
    if not iso:
        return 0
    h = re.search(r"(\d+)H", iso)
    m = re.search(r"(\d+)M", iso)
    s = re.search(r"(\d+)S", iso)
    return (
        (int(h.group(1)) if h else 0) * 3600
        + (int(m.group(1)) if m else 0) * 60
        + (int(s.group(1)) if s else 0)
    )


def iso_duration(total_seconds):
    """Convert a total-seconds count back into an ISO 8601 duration string.
    Examples: 3600 -> 'PT1H', 5400 -> 'PT1H30M', 0 -> 'PT0S'
    """
    h, rem = divmod(int(total_seconds), 3600)
    m, s = divmod(rem, 60)
    out = "PT"
    if h:
        out += f"{h}H"
    if m:
        out += f"{m}M"
    if s or out == "PT":
        out += f"{s}S"
    return out


def parse_score(score_str):
    """Parse a Timefold score string into a dict with 'hard', 'medium', 'soft' keys.
    Example: '0hard/-2medium/-150soft' → {'hard': 0, 'medium': -2, 'soft': -150}
    """
    result = {"hard": 0, "medium": 0, "soft": 0}
    for part in (score_str or "").split("/"):
        for label in ("hard", "medium", "soft"):
            if label in part:
                try:
                    result[label] = int(part.replace(label, ""))
                except ValueError:
                    pass
    return result


def score_sort_key(score_str):
    """Sortable key: hard violations first, then medium, then soft (most negative first)."""
    s = parse_score(score_str)
    if s["hard"] != 0:
        return (0, s["hard"])
    if s["medium"] != 0:
        return (1, s["medium"])
    return (2, s["soft"])


def constraint_type(weight_str):
    """Classify a constraint's weight string as 'hard', 'medium', or 'soft'."""
    s = parse_score(weight_str)
    if s["hard"] != 0:
        return "hard"
    if s["medium"] != 0:
        return "medium"
    return "soft"


def fmt_datetime(iso):
    """Shorten an ISO datetime to a readable label. Example: '2026-06-02T06:00-04:00' → 'Mon 02 Jun 06:00'."""
    if not iso:
        return "?"
    try:
        from datetime import datetime
        return datetime.fromisoformat(iso).strftime("%a %d %b %Y  %H:%M")
    except Exception:
        return iso[:16]


def duration_between(start_iso, end_iso):
    """Compute human-readable duration between two ISO datetimes. Returns '?' on parse failure."""
    try:
        from datetime import datetime
        delta = datetime.fromisoformat(end_iso) - datetime.fromisoformat(start_iso)
        total_min = int(delta.total_seconds() / 60)
        h, m = divmod(total_min, 60)
        return f"{h}h{m}m" if m else f"{h}h"
    except Exception:
        return "?"


# ---------------------------------------------------------------------------
# Platform UI URL builders
# ---------------------------------------------------------------------------

def platform_url(tenant, model, dataset_id, version="v1", page=None, platform_base=None):
    """Build the platform UI URL for a dataset run.
    page: None (overview), "visualization", "input", "output", "configuration"
    """
    base = f"{_pb(platform_base)}/{tenant}/models/{model}/{version}/runs/{dataset_id}"
    return f"{base}/{page}" if page else base


def platform_links(tenant, model, dataset_id, version="v1", platform_base=None):
    """Return a dict of all standard platform page URLs for a dataset."""
    return {
        "Overview":      platform_url(tenant, model, dataset_id, version, platform_base=platform_base),
        "Visualization": platform_url(tenant, model, dataset_id, version, "visualization", platform_base=platform_base),
        "Input":         platform_url(tenant, model, dataset_id, version, "input", platform_base=platform_base),
        "Output":        platform_url(tenant, model, dataset_id, version, "output", platform_base=platform_base),
        "Configuration": platform_url(tenant, model, dataset_id, version, "configuration", platform_base=platform_base),
    }



# ---------------------------------------------------------------------------
# Argparse helpers
# ---------------------------------------------------------------------------

def _add_platform_url_arg(parser):
    """Add --platform-url argument."""
    parser.add_argument(
        "--platform-url",
        default=os.environ.get("TIMEFOLD_PLATFORM_URL", DEFAULT_PLATFORM_BASE),
        metavar="URL",
        help=(
            "Platform base URL (default: %(default)s). "
            "Known installations: "
            "eu=https://app.timefold.ai, "
            "us=https://app-us1.timefold.ai, "
            "Or set TIMEFOLD_PLATFORM_URL env var."
        ),
    )


def add_common_args(parser):
    """Add --model-api-url (required), --platform-url, --dataset-id, --model, --tenant.

    There is deliberately no --api-key argument. The key is read from the
    TIMEFOLD_API_KEY environment variable only, so it never appears in a command line,
    in a shell history, or in the context of an agent that runs these scripts.
    """
    parser.add_argument(
        "--model-api-url",
        required=True,
        help="Model API base URL, e.g. https://app.timefold.ai/api/models/employee-scheduling/v1",
    )
    _add_platform_url_arg(parser)
    parser.add_argument("--dataset-id", required=True, help="Dataset / run ID to analyse")
    from model_config import MODEL_CONFIGS  # deferred: relies on the caller's sys.path setup
    parser.add_argument(
        "--model",
        required=True,
        choices=list(MODEL_CONFIGS),
        help="Model key — selects the terminology, field names, and endpoints to use",
    )
    parser.add_argument(
        "--tenant",
        default=os.environ.get("TIMEFOLD_TENANT"),
        metavar="ID",
        help="Tenant ID (UUID) for platform links, e.g. '00000000-0000-0000-0000-000000000000'; "
             "or set TIMEFOLD_TENANT env var",
    )


def resolve_args(args):
    """Validate parsed args and return (model_api_url, api_key, dataset_id, platform_base). Exits on errors.

    The API key comes from the environment, never from an argument. See add_common_args.
    """
    api_key = os.environ.get("TIMEFOLD_API_KEY")
    if not api_key:
        sys.exit(
            "Error: TIMEFOLD_API_KEY is not set.\n"
            "Export it in your own shell before you run this script:\n"
            "    export TIMEFOLD_API_KEY=<your-api-key>\n"
            "The scripts read the key from the environment only. They accept no --api-key argument, "
            "so the key stays out of your command line and out of your shell history."
        )
    if not args.model_api_url:
        sys.exit("Error: provide --model-api-url (model API base URL)")

    # Stamp every later request with the skill and script that make it.
    from model_config import MODEL_CONFIGS  # deferred: relies on the caller's sys.path setup
    skill = MODEL_CONFIGS.get(getattr(args, "model", None), {}).get("skill")
    script = os.path.splitext(os.path.basename(sys.argv[0]))[0] or None
    set_source(skill=skill, script=script, version=skill_version())

    return args.model_api_url, api_key, args.dataset_id, args.platform_url.rstrip("/")


# ---------------------------------------------------------------------------
# Entry-point wrapper
# ---------------------------------------------------------------------------

def run(main):
    """Run a script's main() and turn an expected failure into one clear line.

    A traceback tells the user nothing they can act on, and it fills the context of
    the agent that reads the output. An unexpected error still raises, because that
    is a bug in a script and the traceback is the useful part.
    """
    try:
        main()
    except TimefoldApiError as error:
        sys.exit(f"Error: {error}")
    except KeyboardInterrupt:
        sys.exit("Stopped.")
    except BrokenPipeError:
        # A downstream `head` closed the pipe. That is not a failure. Point stdout at
        # the null device, or Python prints its own error while it shuts down.
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except OSError:
            pass
        sys.exit(0)

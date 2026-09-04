# Timefold Skills

Agent Skills for users of [Timefold](https://timefold.ai) models.

A skill is a folder with a `SKILL.md` file. It gives an AI coding agent the instructions,
reference material and scripts it needs for one task. Agent Skills is an open standard, so
these skills work in Claude Code, Cursor, Codex, GitHub Copilot and many other agents.

## Skills in this repository

| Skill | Purpose |
|---|---|
| [`explain-dataset-ess`](./skills/explain-dataset-ess) | Explain an optimized dataset of the Employee Shift Scheduling model |
| [`explain-dataset-fsr`](./skills/explain-dataset-fsr) | Explain an optimized dataset of the Field Service Routing model |
| [`explain-dataset-pdr`](./skills/explain-dataset-pdr) | Explain an optimized dataset of the Pick-up and Delivery Routing model |
| [`explain-dataset-shared`](./skills/explain-dataset-shared) | The model-agnostic workflow and the Python scripts. The three skills above read it. Do not invoke it directly. |
| [`language-guidelines`](./skills/language-guidelines) | Timefold's language rules and terminology. The report prose follows them. |
| [`timefold-write-report`](./skills/timefold-write-report) | How a report is assembled, where it is saved, and which formats are available. |
| [`brand-guidelines`](./skills/brand-guidelines) | Timefold's brand colors and typography, for branded reports and for UI work. |
| [`timefold-logo`](./skills/timefold-logo) | The official Timefold logo files. Never draw or approximate the logo. |

The `explain-dataset` skills answer questions about a dataset that Timefold has optimized:

- Why is this work item unassigned?
- Why did the solver assign this resource to this work item?
- Where are the coverage gaps and the bottlenecks?
- What does this score mean?
- What can I change to get a better plan?

The skill reads the dataset through the Timefold API. It does not change your data.

## Installation

### Claude Code

```bash
claude plugin marketplace add TimefoldAI/skills
claude plugin install skills@timefold
```

### Other agents

```bash
npx skills add TimefoldAI/skills
```

The `skills` CLI finds the agents you have installed and asks which skills to add. Use `-g` to
install for all your projects.

## Prerequisites

- A Timefold account and an API key. See
  [API usage](https://docs.timefold.ai/timefold-platform/latest/api/api-usage). You find your
  tenant ID under
  [Tenant details](https://docs.timefold.ai/timefold-platform/latest/how-tos/tenant-details).
- Python 3.9 or later, and the `requests` package: `pip install requests`.

The scripts read these environment variables, so you do not have to pass the values on each
command:

| Variable | Purpose |
|---|---|
| `TIMEFOLD_API_KEY` | Your API key |
| `TIMEFOLD_TENANT` | Your tenant ID |
| `TIMEFOLD_PLATFORM_URL` | Your platform URL. The default is `https://app.timefold.ai` |

If your agent cannot run shell commands, the skill calls the API directly instead. It is
slower on large datasets.

## Usage

Ask your agent a question about a dataset. For example:

> Explain route plan `a1b2c3d4-...` for me. Why are 12 visits unassigned?

The agent selects the skill for your model, collects the data, and writes a report.

## Repository layout

```
.claude-plugin/
  plugin.json          # plugin manifest for Claude Code
  marketplace.json     # makes this repository a Claude Code marketplace
.github/workflows/
  bump-plugin-version.yml   # bumps the minor version when the skills change
skills/
  explain-dataset-ess/
  explain-dataset-fsr/
  explain-dataset-pdr/
  explain-dataset-shared/
    SKILL.md
    references/        # loaded on demand
    scripts/           # Python helpers that call the Timefold API
  language-guidelines/
  timefold-write-report/
  brand-guidelines/
  timefold-logo/
    assets/            # official logo files, SVG and PNG
```

## Versioning

The plugin version follows semantic versioning. A GitHub Actions workflow bumps the minor
version each time the skills change on `main`. Claude uses that version to find out that the
plugin must be reloaded, so do not remove the bump.

## Documentation

- [Timefold documentation](https://docs.timefold.ai)
- [Employee Shift Scheduling](https://docs.timefold.ai/employee-shift-scheduling/latest/)
- [Field Service Routing](https://docs.timefold.ai/field-service-routing/latest/)
- [Pick-up and Delivery Routing](https://docs.timefold.ai/pickup-delivery-routing/latest/)

## Contributing

Open an issue or a pull request. Keep each skill self-contained, and keep the shared workflow
model-agnostic.

## License

The skills, the scripts and the documentation are under the
[Apache License 2.0](./LICENSE).

The logo files in `skills/timefold-logo/assets/` are trademarks of Timefold BV. The license above
does not grant you a right to use them. Use them only to represent Timefold, and do not modify
them.

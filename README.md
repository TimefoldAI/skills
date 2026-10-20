# Timefold Skills

Agent Skills for users of [Timefold](https://timefold.ai) models, and the supporting skills
they build on.

A skill is a folder with a `SKILL.md` file. It gives an AI coding agent the instructions,
reference material, and scripts it needs for one task. Agent Skills is an open standard, so
these skills work in Claude Code, Cursor, Codex, GitHub Copilot, and many other agents.

## Skills in this repository

| Skill                                                       | Purpose                                                                                                        |
| ----------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| [`explain-dataset-ess`](./skills/explain-dataset-ess)       | Explain an optimized dataset of the Employee Shift Scheduling model                                            |
| [`explain-dataset-fsr`](./skills/explain-dataset-fsr)       | Explain an optimized dataset of the Field Service Routing model                                                |
| [`explain-dataset-pdr`](./skills/explain-dataset-pdr)       | Explain an optimized dataset of the Pick-up and Delivery Routing model                                         |
| [`explain-dataset-shared`](./skills/explain-dataset-shared) | The model-agnostic workflow and the Python scripts. The three skills above read it. Do not invoke it directly. |
| [`language-guidelines`](./skills/language-guidelines)       | Timefold's language rules and terminology. The report prose follows them.                                      |
| [`timefold-write-report`](./skills/timefold-write-report)   | How a report is assembled, which metadata it carries, and where it is saved.                                   |

The `explain-dataset` skills answer questions about a dataset that Timefold has optimized:

- Why is this work item unassigned?
- Why did the model assign this resource to this work item?
- Where are the coverage gaps and the bottlenecks?
- What does this score mean?
- What can I change to get a better plan?

The skills reach your dataset through the Timefold API. They only read it. The recommendation
call sends a request body, but it asks the model what an assignment would cost. It does not
change your dataset.

## Plugins in this repository

| Plugin                 | Purpose                                                                                                                        |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `timefold-skills`      | The skills above, as one Claude Code plugin                                                                                    |
| [`prd`](./plugins/prd) | Define the requirements of an optimization model with the Timefold PRD Assistant connector, with a requirements pane in Claude Code |

## Installation

### Any agent: give it this prompt

Copy this prompt into your agent. It installs the skills for you:

```text
Run 'npx skills add TimefoldAI/skills' and install all the skills locally in this project folder. Install them for the agent harness this prompt was run in.
```

The agent runs the command, and it selects the correct folder for its own harness. Use this
option if you do not know which of the commands below applies to your agent.

### Claude Code

```bash
claude plugin marketplace add TimefoldAI/skills
claude plugin install timefold-skills@timefold
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
- **No other prerequisite.** The scripts use the Python standard library only. There is nothing
  to `pip install`, and no virtual environment to create.

The skill finds a runtime by itself, in this order:

| Level | Condition                                                                  | What runs                                                           |
| ----- | -------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| 1     | [uv](https://docs.astral.sh/uv/getting-started/installation/) is installed | `uv run <script>`, and uv supplies a Python if the machine has none |
| 2     | Python 3.9 or later is installed                                           | `python3 <script>` (or `python` on Windows)                         |
| 3     | A shell, but no Python                                                     | `curl` calls the API directly                                       |
| 4     | No shell (Claude Desktop, Web UI)                                          | The agent calls the API with WebFetch                               |

Levels 1 and 2 are the fast path: the scripts handle pagination, they format the results, and
they keep large payloads out of the agent's context. Levels 3 and 4 still work, but on a large
dataset they are slower and the agent can miss detail.

If you have no Python, install uv. It is one binary, it needs no administrator rights, and it
works on macOS, Linux, and Windows:

```bash
# macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

The scripts read these environment variables. The dataset ID, the model, and the model API URL
stay on the command line.

| Variable           | Purpose                                                                  |
| ------------------ | ------------------------------------------------------------------------ |
| `TIMEFOLD_API_KEY` | Your API key. Required, and the environment is the only way to supply it |
| `TIMEFOLD_TENANT`  | Your tenant ID. Optional, `--tenant` also works                          |

Export your API key in the shell you start your agent from:

```bash
export TIMEFOLD_API_KEY=<your-api-key>
```

The scripts take no `--api-key` argument, on purpose. A key on a command line reaches the context
of the agent that runs the command, and from there it can end up in a transcript, a log, or a
report. Keep it in your shell profile or in a secret manager, and the agent never sees it.

If your agent cannot run shell commands, the skill calls the API directly instead (level 4
above). It is slower on large datasets.

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
  bump-plugin-version.yml       # bumps the minor version when the skills change
  bump-prd-plugin-version.yml   # bumps the minor version when the prd plugin changes
skills/
  explain-dataset-ess/
  explain-dataset-fsr/
  explain-dataset-pdr/
  explain-dataset-shared/
    SKILL.md
    VERSION            # version stamp for the report metadata
    references/        # loaded on demand
    scripts/           # Python helpers that call the Timefold API
  language-guidelines/
  timefold-write-report/
```

## Versioning

The plugin version follows semantic versioning. A GitHub Actions workflow bumps the minor
version each time the skills change on `main`. Claude uses that version to find out that the
plugin must be reloaded, so do not remove the bump.

The workflow writes the version into two files: `.claude-plugin/plugin.json`, which Claude Code
reads, and `skills/explain-dataset-shared/VERSION`, which the skills read for the report
metadata. Both are needed, because `npx skills add` copies the skill folders without the plugin
manifest. Keep them in sync.

The `prd` plugin has its own version in `plugins/prd/.claude-plugin/plugin.json`. A second
workflow, `bump-prd-plugin-version.yml`, bumps its minor version each time `plugins/prd/` changes
on `main`.

## Documentation

- [Timefold documentation](https://docs.timefold.ai)
- [Employee Shift Scheduling](https://docs.timefold.ai/employee-shift-scheduling/latest/)
- [Field Service Routing](https://docs.timefold.ai/field-service-routing/latest/)
- [Pick-up and Delivery Routing](https://docs.timefold.ai/pickup-delivery-routing/latest/)

## Contributing

We do not accept code contributions to this repository at this time. Only collaborators can open
pull requests.
Bug reports and requests are welcome as [issues](https://github.com/TimefoldAI/skills/issues).
See [CONTRIBUTING.md](./CONTRIBUTING.md).

## License

The skills, the scripts, and the documentation are under the
[Apache License 2.0](./LICENSE).

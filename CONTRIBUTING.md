# Contributing

Thank you for the interest. We are not accepting code contributions to this repository at this
time.

Only collaborators can open pull requests, so pull requests from forks, including pull requests
that add a new skill, are not possible.
This is not about the quality of the work. These skills describe how the Timefold models behave,
so we keep authorship of them with the team that builds those models. A skill that gives wrong
guidance about a model costs a user more than no skill at all.

## What you can do instead

- **Report a bug, or tell us a skill gave you wrong guidance.**
  [Open an issue](https://github.com/TimefoldAI/skills/issues). Tell us which skill, what you
  asked, and what it did. Please leave out your API key, your tenant ID, and any customer data.
- **Ask for a new skill, or for a change to one.** Open an issue and describe the question you
  wanted answered. We would rather hear the problem than receive the solution.
- **Ask a question about the Timefold models.** Use the
  [Timefold documentation](https://docs.timefold.ai) or contact Timefold support.
- **Build your own.** The skills, the scripts, and the documentation are under the
  [Apache License 2.0](./LICENSE). Copy them, change them, and keep the result in your own
  repository. You owe us nothing beyond the license terms.

## For Timefold employees

We develop the skills in the private repository
[TimefoldAI/skills-internal](https://github.com/TimefoldAI/skills-internal) and test them
internally first. This public repository is a copy of its `main` branch: a workflow pushes
`main` here after each change. Issues stay in this repository.

Do not push, merge, or edit files in this repository. The publish is a fast-forward push, so a
commit made here stops every publish until someone brings it into the private repository.

### Branches

| Branch | What it holds                                         | Who installs it                    |
| ------ | ----------------------------------------------------- | ---------------------------------- |
| `next` | Changes in internal test. The default branch.         | Timefold employees who test skills |
| `main` | Released changes. The workflow publishes them here.   | Everyone, from this repository     |

### Make a change

1. Make a branch from `next`, and open a pull request against `next`. To try the change before
   the merge, start Claude Code with `claude --plugin-dir <your clone>` (the `timefold-skills`
   plugin) or `claude --plugin-dir <your clone>/plugins/prd`.
2. Merge the pull request. The workflow gives the changed plugin a new minor version on `next`,
   so the testers get the change on their next plugin update.

### Test the internal version

The `next` branch has the same marketplace name as this repository, `timefold`. Replace the
public marketplace with it. The install commands stay the same, and you cannot install the
public and the internal skills at the same time by mistake.

```bash
claude plugin marketplace remove timefold   # this also uninstalls its plugins
claude plugin marketplace add TimefoldAI/skills-internal#next
claude plugin install timefold-skills@timefold
claude plugin install timefold-prd@timefold  # if you use it
```

The repository is private, so git on your machine needs access to it: a GitHub SSH key in
`ssh-agent`, or `gh auth login` and then `gh auth setup-git`. To get updates, turn on
auto-update for `timefold` under **Marketplaces** in `/plugin`, or run
`claude plugin marketplace update timefold`.

To go back to the public version, remove the marketplace again and add `TimefoldAI/skills`.

### Release

Open a pull request from `next` to `main`, and squash it. The repository allows only squash
merges, so the history of `main` has one commit for each release and each hotfix. The release
brings the versions from `next`, and the workflow publishes `main` here. Then the workflow
merges `main` back into `next`, so that the next release starts from this one.

A release takes everything that is on `next`. Merge into `next` only what you expect to
release within about a week. Keep a change that needs a longer test on its own branch, and
test it with `--plugin-dir`.

### Hotfix

Make a branch from `main`, and open a pull request against `main`. The workflow gives the
plugin a new patch version, publishes it, and merges `main` into `next`. In the version files,
the merge keeps the version of `next`, and `next` then gets a new minor version with the fix.

If the fix and a change on `next` changed the same lines, the merge into `next` stops and
changes nothing. Then merge `main` into `next` by hand, keep the version of `next` in the
version files, and push the merge commit to `next`.

### Rules

- **Everything on `next` becomes public at the next release.** A release publishes the content
  of `next`, not its commit history. Still, never commit customer data, API keys, internal URLs,
  or other internal content: a release can take it before someone removes it.
- Keep each skill self-contained, and keep the shared workflow model-agnostic.

### How the publish works

`.github/workflows/bump-and-publish.yml` runs in the private repository only. It bumps the
versions on `next` and `main`, and pushes `main` to this repository with a deploy key. The key
is the secret `PUBLIC_REPO_DEPLOY_KEY` in the private repository, and its public half is a
deploy key with write access in this repository. Then it merges `main` into `next`. A daily run
on `main` repeats what a failed run missed.

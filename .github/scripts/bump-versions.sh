#!/usr/bin/env bash
# Bumps the version of each plugin whose content changed after its last version change, then
# commits and pushes. At the end, HEAD is the commit that is safe to publish.
#
# Claude uses the plugin version to find out that a plugin changed and must be reloaded.
# Without a version bump, installed plugins do not update.
#
# - On next, changed content gets a new minor version. Internal testers install from next,
#   so they get each change.
# - On main, a release (a squash merge of next) brings its version from next. Nothing to bump.
#   A hotfix that does not change the version gets a new patch version.
#
# The script looks at the state of the branch, not at the commits of one push. GitHub can drop a
# waiting run when a newer push comes in, and a run can fail. The next run then still finds the
# content that has no version change yet.
#
# The timefold-skills version also goes into every skills/*/VERSION file. The skills read it for
# the report metadata, because some installs copy the skill folders without the manifest.
#
# Environment: BRANCH (next or main).
set -euo pipefail

branch=${BRANCH:?}

version_at() {
  git show "$1:$2" 2>/dev/null | jq -r '.version // empty' 2>/dev/null || true
}

# Prints the last commit on the first-parent line of HEAD that changed the version in MANIFEST.
# On main, a release merge counts, because it brings the version of next.
last_version_change() {
  local manifest=$1 commit
  while read -r commit; do
    if ! git rev-parse -q --verify "${commit}^1" > /dev/null; then
      echo "$commit"  # the first commit of the repository
      return
    fi
    if git diff --quiet "${commit}^1" "$commit" -- "$manifest"; then
      continue
    fi
    if [ "$(version_at "${commit}^1" "$manifest")" != "$(version_at "$commit" "$manifest")" ]; then
      echo "$commit"
      return
    fi
  done < <(git rev-list --first-parent HEAD)
}

# bump MANIFEST JSON_INDENT CONTENT_PATH [STAMP_FILE...]
bump() {
  local manifest=$1 indent=$2 path=$3
  shift 3
  local own=("$manifest" "$@")
  local name current since content major minor patch new

  name=$(jq -r '.name' "$manifest")
  current=$(jq -r '.version' "$manifest")
  since=$(last_version_change "$manifest")
  # The version files are not content. Never bump on them, or every bump triggers the next one.
  content=$(git diff --name-only "$since" HEAD -- "$path" \
    | grep -vxF -f <(printf '%s\n' "${own[@]}") || true)

  if [ -z "$content" ]; then
    echo "$name $current: no content change after the last version change."
    return
  fi
  IFS=. read -r major minor patch <<< "$current"
  if [ "$branch" = next ]; then
    new="${major}.$((minor + 1)).0"
  else
    new="${major}.${minor}.$((patch + 1))"
  fi

  jq --indent "$indent" --arg v "$new" '.version = $v' "$manifest" > tmp.json
  mv tmp.json "$manifest"
  for stamp in "$@"; do
    echo "$new" > "$stamp"
  done
  git add "${own[@]}"
  bumped+=("${name}:${new}")
  echo "Bumped $name: $current -> $new"
}

git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

for attempt in 1 2 3 4 5; do
  git fetch --quiet origin "$branch"
  git checkout --quiet -B "$branch" "origin/$branch"

  bumped=()
  stamps=(skills/*/VERSION)
  bump .claude-plugin/plugin.json 2 skills/ "${stamps[@]}"
  bump plugins/prd/.claude-plugin/plugin.json 4 plugins/prd/

  if [ ${#bumped[@]} -eq 0 ]; then
    exit 0
  fi
  # why: no [skip ci]. A push with the built-in token starts no workflow anyway, and the marker
  # in a squashed release would stop the publish.
  git commit --quiet -m "chore: bump plugin version: ${bumped[*]}"
  if git push --quiet origin "HEAD:$branch"; then
    exit 0
  fi
  echo "The branch moved while this job ran. Trying again."
  sleep $((attempt * 3))
done

echo "::error::Could not push the version bump after 5 attempts."
exit 1

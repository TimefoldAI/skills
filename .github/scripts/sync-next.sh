#!/usr/bin/env bash
# Merges main into next, so that next always has every commit of main.
#
# A release (next into main) and a hotfix are squash merges. Each one makes a new commit on main
# that next does not have. Without this merge, the next release would start from an old common
# commit and conflict in the version files.
#
# - next has all commits of main: nothing to do.
# - main has all commits of next: next moves forward to main, with no new commit.
# - main has the same content as a commit of next (a release): a merge commit on next that keeps
#   the content of next.
# - Else (a hotfix): a merge commit on next. The version files keep the version of next, and the
#   other manifest fields merge normally. The bump on next then gives a new minor version when
#   main brought content that next did not have.
# - A conflict in another file: the script stops and changes nothing. Merge main into next by
#   hand, as CONTRIBUTING.md says.
set -euo pipefail

git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

# keep_next_version MANIFEST BASE: merge the manifest of main into the merge in progress, but with
# the version of next. Other fields merge normally. Returns 1 on a conflict.
keep_next_version() {
  local file=$1 base=$2 dir version
  dir=$(mktemp -d)
  git show "origin/next:$file" > "$dir/ours"
  git show "origin/main:$file" > "$dir/theirs"
  git show "$base:$file" > "$dir/base" 2> /dev/null || : > "$dir/base"
  version=$(jq -r '.version' "$dir/ours")
  # The first "version" key is the version of the plugin. The text stays as it is, so the merge
  # sees only real changes.
  for side in base theirs; do
    VERSION=$version perl -0pi -e 's/("version"\s*:\s*")[^"]*"/${1}$ENV{VERSION}"/' "$dir/$side"
  done
  if ! git merge-file -p "$dir/ours" "$dir/base" "$dir/theirs" > "$dir/merged"; then
    rm -rf "$dir"
    return 1
  fi
  cp "$dir/merged" "$file"
  git add "$file"
  rm -rf "$dir"
}

for attempt in 1 2 3 4 5; do
  git fetch --quiet origin main next
  if git merge-base --is-ancestor origin/main origin/next; then
    echo "next has all commits of main. Nothing to merge."
    exit 0
  fi

  if git merge-base --is-ancestor origin/next origin/main; then
    git checkout --quiet -B next origin/main
    echo "next moves forward to main."
  elif git log --format=%T origin/main..origin/next | grep -qxF "$(git rev-parse 'origin/main^{tree}')"; then
    # A release: main has the content of a commit of next, so main brings nothing new. Keep the
    # content of next and record main as merged. A normal merge could conflict here, when next
    # changed released lines again before this job ran.
    git checkout --quiet -B next origin/next
    git merge --quiet -s ours -m "chore: merge main into next" origin/main
    echo "Merged main into next (a release: next keeps its content)."
  else
    git checkout --quiet -B next origin/next
    base=$(git merge-base origin/next origin/main)
    git merge --no-ff --no-commit origin/main > /dev/null || true
    # The version of next is the newer one. A file that only one side has stays as merged.
    manifest_conflicts=()
    for file in .claude-plugin/plugin.json plugins/prd/.claude-plugin/plugin.json; do
      if git cat-file -e "origin/next:$file" 2> /dev/null && git cat-file -e "origin/main:$file" 2> /dev/null; then
        keep_next_version "$file" "$base" || manifest_conflicts+=("$file")
      fi
    done
    for file in skills/*/VERSION; do
      if git cat-file -e "origin/next:$file" 2> /dev/null; then
        git checkout origin/next -- "$file"
      fi
    done
    conflicts=$( (git diff --name-only --diff-filter=U; printf '%s\n' "${manifest_conflicts[@]}") | sort -u | sed '/^$/d')
    if [ -n "$conflicts" ]; then
      echo "::error::main and next changed the same lines. Merge main into next by hand:"
      echo "$conflicts"
      git merge --abort
      exit 1
    fi
    git commit --quiet -m "chore: merge main into next"
    echo "Merged main into next."
  fi

  if git push --quiet origin HEAD:next; then
    exit 0
  fi
  echo "next moved while this job ran. Trying again."
  sleep $((attempt * 3))
done

echo "::error::Could not push the merge of main into next after 5 attempts."
exit 1

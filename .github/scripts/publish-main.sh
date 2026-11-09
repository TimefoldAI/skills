#!/usr/bin/env bash
# Pushes the checked-out main to main of the public TimefoldAI/skills repository.
#
# The push is a fast-forward only. When the public main has a commit that this main does not
# have, someone changed the public repository directly. The script then stops and changes
# nothing: bring that commit into this repository first.
#
# Environment: DEPLOY_KEY, the private half of a deploy key with write access to
# TimefoldAI/skills.
set -euo pipefail

: "${DEPLOY_KEY:?The secret PUBLIC_REPO_DEPLOY_KEY is not set. See CONTRIBUTING.md.}"
public=git@github.com:TimefoldAI/skills.git

dir=$(mktemp -d)
trap 'rm -rf "$dir"' EXIT
(umask 077 && printf '%s\n' "$DEPLOY_KEY" > "$dir/key")
# GitHub publishes its SSH host keys in the meta API, which is reached over HTTPS.
curl -fsSL https://api.github.com/meta | jq -r '.ssh_keys[] | "github.com " + .' > "$dir/known_hosts"
export GIT_SSH_COMMAND="ssh -i $dir/key -o IdentitiesOnly=yes -o UserKnownHostsFile=$dir/known_hosts -o StrictHostKeyChecking=yes"

git fetch --quiet "$public" main
if ! git merge-base --is-ancestor FETCH_HEAD HEAD; then
  echo "::error::The public main has commits that this main does not have:"
  git log --oneline HEAD..FETCH_HEAD
  exit 1
fi
if [ "$(git rev-parse FETCH_HEAD)" = "$(git rev-parse HEAD)" ]; then
  echo "The public main is up to date."
  exit 0
fi

echo "Publishing these commits:"
git log --oneline FETCH_HEAD..HEAD
git push "$public" HEAD:refs/heads/main

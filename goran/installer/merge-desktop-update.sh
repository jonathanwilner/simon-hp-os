#!/usr/bin/env bash
# Local-only integration. Keep recovery refs and original dirty state indefinitely.
set -euo pipefail
checkout=$1
record=$2
cd "$checkout"
mkdir -p "$record"
[[ -z $(git ls-files -u) ]] || { echo 'Resolve the existing Git conflict before updating.' >&2; exit 1; }
[[ ! -f $(git rev-parse --git-path MERGE_HEAD) ]] || { echo 'Finish the existing merge before updating.' >&2; exit 1; }
for operation in rebase-merge rebase-apply CHERRY_PICK_HEAD REVERT_HEAD; do
  [[ ! -e $(git rev-parse --git-path "$operation") ]] || { echo "Finish the existing Git operation: $operation" >&2; exit 1; }
done
git fetch origin main
original=$(git rev-parse HEAD)
published=$(git rev-parse FETCH_HEAD)
printf '%s\n' "$original" > "$record/original-revision"
printf '%s\n' "$published" > "$record/published-revision"
recovery="simon-recovery/$(date -u +%Y%m%dT%H%M%SZ)-$$"
git branch "$recovery" "$original"
printf '%s\n' "$recovery" > "$record/recovery-branch"
if ! git symbolic-ref -q HEAD >/dev/null; then
  git switch -c "simon-local/${recovery##*/}"
fi
if [[ -n $(git status --porcelain) ]]; then
  git stash push --include-untracked -m "Simon update recovery $recovery"
  stash=$(git rev-parse refs/stash)
  printf '%s\n' "$stash" > "$record/original-stash"
  # A permanent ref keeps the snapshot even if the ordinary stash list is cleared.
  git update-ref "refs/simon-update-recovery/${recovery##*/}" "$stash"
  git stash apply --index "$stash"
  git add -A
  git -c user.name='Simon local desktop' -c user.email='simon@localhost' commit -m 'Preserve local desktop changes before published update'
fi
if ! git -c user.name='Simon local desktop' -c user.email='simon@localhost' merge --no-edit "$published"; then
  printf 'Update stopped before build or activation. Resolve conflicts in %s, then rerun.\nRecovery details: %s\nUse git merge --abort to return to the saved local configuration.\n' "$checkout" "$record" >&2
  exit 1
fi
git rev-parse HEAD > "$record/merged-revision"

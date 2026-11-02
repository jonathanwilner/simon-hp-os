#!/usr/bin/env bash
# Shared with the bounded updater regression tests.
require_stable_checkout() {
  [[ "$1" == "$(git rev-parse HEAD)" && -z "$(git status --porcelain)" ]] || {
    echo 'Source changed during the build; rebuild before activation' >&2
    return 1
  }
}
activate_with_rollback() {
  local candidate=$1 profile=$2 previous=$3 result
  if "$candidate/activate"; then
    if [[ $(readlink -f "$profile") == "$candidate" ]]; then
      echo 'Activation completed and the Home Manager profile matches the candidate.'
      return 0
    fi
    result=1
    echo 'Activation returned success but the profile does not match the candidate.' >&2
  else
    result=$?
  fi
  echo "Activation failed with exit $result; candidate and recovery records retained." >&2
  if [[ -n "$previous" && -x "$previous/activate" ]]; then
    echo 'Reactivating the previous Home Manager generation.' >&2
    "$previous/activate" || echo "Automatic rollback failed. Run $previous/activate from Simon’s console." >&2
  fi
  return "$result"
}

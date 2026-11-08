#!/usr/bin/env bash
# Bootstrap the public desktop updater from Simon's existing Ubuntu login.
set -euo pipefail
fail() { printf 'update-hp-os: %s\n' "$*" >&2; exit 1; }
usage() {
  cat <<'EOF'
Usage: bash update-hp-os.sh [--checkout PATH] [--from LEGACY] [--legacy-base REV]
                          [--build-only] [--development] [--attach | --no-attach]
Clone the public HP-OS configuration, preserve local configuration changes, and
run its desktop updater. The existing Ubuntu installation stays in place.
--from selects the old checkout. Otherwise ~/src/nixos-amd is detected only
when it contains the Simon profile. --legacy-base identifies its clean baseline.
--development explicitly selects unpromoted main; the default is fleet-stable.
--build-only builds without activation. --attach displays the tracked task.
EOF
}
checkout="${SIMON_DESKTOP_CHECKOUT:-$HOME/src/simon-hp-os}"
legacy=
base=
build_only=false
attach=false
channel=fleet-stable
while (($#)); do
  case "$1" in
    --checkout|--from|--legacy-base)
      (($# >= 2)) && [[ -n "$2" ]] || fail "$1 requires a value"
      case "$1" in --checkout) checkout=$2;; --from) legacy=$2;; --legacy-base) base=$2;; esac
      shift 2 ;;
    --development) channel=main; shift ;;
    --build-only) build_only=true; shift ;;
    --attach) attach=true; shift ;;
    --no-attach) attach=false; shift ;;
    -h|--help) usage; exit 0 ;;
    *) fail "Unknown argument: $1 (use --help)" ;;
  esac
done
[[ ${EUID:-$(id -u)} -ne 0 ]] || fail 'Run from Simon’s own login, without sudo'
for command in git python3 tmux realpath flock; do
  command -v "$command" >/dev/null || fail "Required command missing: $command. Use the existing Simon Ubuntu installation."
done
if ! command -v nix >/dev/null; then
  for profile in /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh "$HOME/.nix-profile/etc/profile.d/nix.sh"; do
    if [[ -r "$profile" ]]; then source "$profile"; fi
    command -v nix >/dev/null && break
  done
fi
command -v nix >/dev/null || fail 'Nix is unavailable. Log in to the existing Nix-enabled Simon session.'
checkout=$(realpath -m -- "$checkout")
if [[ -z "$legacy" && -f "$HOME/src/nixos-amd/goran/installer/simon-home.nix" ]]; then
  candidate=$(realpath -- "$HOME/src/nixos-amd")
  if [[ "$candidate" != "$checkout" ]] && git -C "$candidate" rev-parse --show-toplevel >/dev/null 2>&1; then
    legacy=$candidate
  fi
fi
if [[ -n "$legacy" ]]; then
  legacy=$(realpath -e -- "$legacy") || fail 'Legacy checkout does not exist'
  [[ "$legacy" != "$checkout" ]] || fail '--from and --checkout must be different directories'
  [[ -f "$legacy/goran/installer/simon-home.nix" ]] || fail 'The legacy checkout does not contain the Simon profile'
  [[ $(git -C "$legacy" rev-parse --show-toplevel) == "$legacy" ]] || fail '--from must name the legacy repository root'
elif [[ -n "$base" ]]; then
  fail '--legacy-base requires --from or a detected legacy checkout'
fi
public_url=https://github.com/jonathanwilner/simon-hp-os.git
if [[ ! -e "$checkout" ]]; then
  mkdir -p -- "$(dirname -- "$checkout")"
  git clone --branch "$channel" -- "$public_url" "$checkout"
fi
[[ $(git -C "$checkout" rev-parse --show-toplevel 2>/dev/null) == "$checkout" ]] || fail '--checkout must name the public repository root'
origin=$(git -C "$checkout" remote get-url origin)
case "$origin" in
  https://github.com/jonathanwilner/simon-hp-os|https://github.com/jonathanwilner/simon-hp-os.git) ;;
  *) fail "Checkout origin must be $public_url; found $origin" ;;
esac
# Load the current merge tool from the verified public origin before using any
# checkout scripts. Old installations may predate migration support. The merge
# tool preserves dirty files and local commits with permanent recovery refs.
state="${XDG_STATE_HOME:-$HOME/.local/state}/simon-desktop-update"
mkdir -p -- "$state"
exec 9>"$state/update.lock"
flock -n 9 || fail 'Another Simon desktop update is running'
git -C "$checkout" fetch origin "refs/heads/$channel" || fail "Release channel $channel is unavailable; no fallback to main is permitted"
tools_dir=$(mktemp -d)
trap 'rm -rf -- "$tools_dir"' EXIT
git -C "$checkout" show FETCH_HEAD:goran/installer/merge-desktop-update.sh > "$tools_dir/merge-desktop-update.sh" \
  || fail 'The public branch does not contain the configuration-preserving update tool'
record="${XDG_STATE_HOME:-$HOME/.local/state}/simon-desktop-update/bootstrap-$(date -u +%Y%m%dT%H%M%SZ)-$$"
bash "$tools_dir/merge-desktop-update.sh" "$checkout" "$record" "$channel"
rm -rf -- "$tools_dir"
trap - EXIT
[[ -f "$checkout/goran/installer/update-desktop.sh" ]] || fail 'The public desktop updater is missing'
if [[ -n "$legacy" ]]; then
  helper="$checkout/goran/installer/migrate-local-config.py"
  [[ -f "$helper" ]] || fail 'Migration helper is missing. Download the current public source before migrating.'
  args=(--from "$legacy" --to "$checkout")
  [[ -z "$base" ]] || args+=(--legacy-base "$base")
  printf 'Preserving configuration from %s; the original checkout stays unchanged.\n' "$legacy"
  python3 "$helper" "${args[@]}"
fi
args=(--checkout "$checkout")
[[ "$channel" == fleet-stable ]] || args+=(--development)
[[ "$build_only" == false ]] || args+=(--build-only)
[[ "$attach" == false ]] || args+=(--attach)
flock -u 9
exec 9>&-
exec bash "$checkout/goran/installer/update-desktop.sh" "${args[@]}"

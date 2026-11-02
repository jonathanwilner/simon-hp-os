set -euo pipefail

state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/goran-brightness"
mkdir -p "$state_dir"
exec 9>"$state_dir/lock"
flock -x 9

percent=100
if [[ -f "$state_dir/percent" ]]; then
  read -r saved < "$state_dir/percent" || true
  if [[ "$saved" =~ ^[0-9]+$ ]] && (( saved >= 5 && saved <= 100 )); then
    percent=$saved
  fi
fi

case "${1:-status}" in
  up) percent=$(( percent + 5 ));;
  down) percent=$(( percent - 5 ));;
  restore) ;;
  set)
    [[ "${2:-}" =~ ^[0-9]+$ ]] || { echo 'usage: goran-brightness set 5..100' >&2; exit 2; }
    percent=$2
    ;;
  status)
    printf 'saved_percent=%s\n' "$percent"
    /usr/bin/sudo -n "$GORAN_PANEL_PYTHON" "$GORAN_PANEL_SCRIPT"
    exit
    ;;
  *) echo 'usage: goran-brightness up|down|restore|set 5..100|status' >&2; exit 2;;
esac

(( percent < 5 )) && percent=5
(( percent > 100 )) && percent=100
# Map 5..100 percent to 10..500 cd/m². The EDID's full-screen limit is 500.
nits=$(( 10 + (percent - 5) * 490 / 95 ))
/usr/bin/sudo -n "$GORAN_PANEL_PYTHON" "$GORAN_PANEL_SCRIPT" "$(( nits * 1000 ))"
printf '%s\n' "$percent" > "$state_dir/percent.tmp"
mv "$state_dir/percent.tmp" "$state_dir/percent"

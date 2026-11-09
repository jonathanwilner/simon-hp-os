mode="${1:-area}"
screenshot_dir="${XDG_SCREENSHOTS_DIR:-$HOME/Pictures/Screenshots}"
mkdir -p "$screenshot_dir"
file="$screenshot_dir/Screenshot-$(date '+%Y-%m-%d-%H-%M-%S-%N').png"
case "$mode" in
  area)
    geometry="$(slurp)" || exit 0
    grim -g "$geometry" "$file"
    ;;
  screen) grim "$file" ;;
  window)
    # Niri handles focused-window capture and the clipboard atomically.
    niri msg action screenshot-window --write-to-disk true --show-pointer false --path "$file"
    notify-send -a screenshot-copy "Screenshot copied" "$file" >/dev/null 2>&1 || true
    exit 0
    ;;
  *) echo 'usage: screenshot-copy {area|screen|window}' >&2; exit 2 ;;
esac
wl-copy --type image/png < "$file"
notify-send -a screenshot-copy "Screenshot copied" "$file" >/dev/null 2>&1 || true

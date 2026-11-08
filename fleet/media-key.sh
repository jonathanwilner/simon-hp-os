set -euo pipefail

# Explicit user intent keeps overlays visible with the shell's "yours" policy.
# A missing/stopped shell must never prevent the hardware key from working.
osd() {
  if command -v hp-os >/dev/null 2>&1; then
    timeout 2 hp-os ipc osd "$@" >/dev/null 2>&1 || true
  fi
}

case "${1:-}" in
  volume-up)
    wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 10%+
    wpctl set-mute @DEFAULT_AUDIO_SINK@ 0
    ;;
  volume-down)
    wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 10%-
    wpctl set-mute @DEFAULT_AUDIO_SINK@ 0
    ;;
  mute) wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle ;;
  mic-mute) wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle ;;
  play-pause|stop|next|previous) playerctl "$1" ;;
  brightness-up|brightness-down)
    if [[ "$1" == brightness-up ]]; then brightnessctl set +5%; else brightnessctl set 5%-; fi
    IFS=, read -r _device _class _current percent _maximum < <(brightnessctl -m)
    percent=${percent%\%}
    [[ "$percent" =~ ^[0-9]+$ ]] && (( 10#$percent <= 100 )) || exit 2
    osd brightnessValue "$percent"
    exit 0
    ;;
  brightness-osd)
    [[ "${2:-}" =~ ^[0-9]+$ ]] && (( 10#${2} <= 100 )) || exit 2
    osd brightnessValue "$2"
    exit 0
    ;;
  *)
    echo 'usage: hp-os-media-key volume-up|volume-down|mute|mic-mute|play-pause|stop|next|previous|brightness-up|brightness-down|brightness-osd PERCENT' >&2
    exit 2
    ;;
esac

case "$1" in
  volume-up|volume-down|mute) osd volume ;;
  mic-mute) osd mic ;;
  next|previous) osd media "$1" ;;
  play-pause) if [[ "$(playerctl status 2>/dev/null || true)" == Playing ]]; then osd media play; else osd media pause; fi ;;
  stop) osd media pause ;;
esac

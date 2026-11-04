set -euo pipefail

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
  *)
    echo 'usage: hp-os-media-key volume-up|volume-down|mute|mic-mute|play-pause|stop|next|previous' >&2
    exit 2
    ;;
esac

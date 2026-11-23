set -euo pipefail

# Explicit user intent keeps overlays visible with the shell's "yours" policy.
# A missing/stopped shell must never prevent the hardware key from working.
osd() {
  if command -v hp-os >/dev/null 2>&1; then
    timeout 2 hp-os ipc osd "$@" >/dev/null 2>&1 || true
  fi
}

# Keep hardware keys on the same speaker selected by either desktop.
# A saved speaker that is unavailable must never redirect a volume write.
main_volume_target() {
  local preference="${XDG_CONFIG_HOME:-$HOME/.config}/hp-os-primary-audio-output"
  local primary="" default_sink
  if [[ -e "$preference" ]]; then
    primary=$(<"$preference") || return 1
  fi

  if [[ -z "$primary" ]]; then
    default_sink=$(timeout 2 pactl get-default-sink 2>/dev/null) || default_sink=""
    case "$default_sink" in
      sink-sunshine-stereo|sink-sunshine-surround51|sink-sunshine-surround71|sink-sunshine-surround714) ;;
      *) printf '%s\n' '@DEFAULT_AUDIO_SINK@'; return ;;
    esac
  fi

  timeout 2 pactl --format=json list sinks | jq -er --arg primary "$primary" '
    map(select(
      (.properties["node.virtual"] // "false") != "true"
      and .properties["factory.name"] != "support.null-audio-sink"
      and (.name | test("^sink-sunshine-(stereo|surround51|surround71|surround714)$") | not)
      and (if $primary == "" then
        .name | test("^alsa_output[.]usb-Apple_Inc[.]_Studio_Display_.+[.]analog-stereo$")
      else .name == $primary end)
    ))
    | if length == 1 then
        .[0].properties["object.id"] | tostring | select(test("^[1-9][0-9]*$"))
      elif $primary == "" then "@DEFAULT_AUDIO_SINK@"
      else empty end'
}

case "${1:-}" in
  volume-up|volume-down|brightness-up|brightness-down)
    step=${2:-}
    if [[ -z "$step" ]]; then
      if [[ "$1" == volume-* ]]; then step=10; else step=5; fi
    fi
    [[ "$step" =~ ^[0-9]+$ ]] && (( 10#$step >= 1 && 10#$step <= 100 )) || exit 2
    step=$((10#$step))
    ;;
esac

case "${1:-}" in
  volume-up|volume-down|mute)
    target=$(main_volume_target) || exit 0
    ;;
esac

case "${1:-}" in
  volume-up)
    wpctl set-volume -l 1.0 "$target" "${step}%+"
    wpctl set-mute "$target" 0
    ;;
  volume-down)
    wpctl set-volume -l 1.0 "$target" "${step}%-"
    wpctl set-mute "$target" 0
    ;;
  mute) wpctl set-mute "$target" toggle ;;
  mic-mute) wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle ;;
  play-pause|stop|next|previous) playerctl "$1" ;;
  brightness-up|brightness-down)
    if [[ "$1" == brightness-up ]]; then brightnessctl set "+${step}%"; else brightnessctl set "${step}%-"; fi
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

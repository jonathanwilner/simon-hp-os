# Ported from Slazenger nixos-intc home.nix at 8d85a03 (28 Sep 2026).
{ config, pkgs }:
let
  hposMonoFontFamily = "Fira Mono";
  dmsEmacsThemeApplyScript = "${config.home.profileDirectory}/bin/dms-emacs-theme-apply";
in
pkgs.writeShellScript "dms-theme-sync" ''
    set -euo pipefail

    JQ_BIN="${pkgs.jq}/bin/jq"
    MKDIR_BIN="${pkgs.coreutils}/bin/mkdir"
    SLEEP_BIN="${pkgs.coreutils}/bin/sleep"
    SYSTEMCTL_BIN="${pkgs.systemd}/bin/systemctl"
    SWAYNC_CLIENT_BIN="${pkgs.swaynotificationcenter}/bin/swaync-client"
    GSETTINGS_BIN="${pkgs.glib}/bin/gsettings"
    GSETTINGS_SCHEMA_DIR="${pkgs.gsettings-desktop-schemas}/share/gsettings-schemas/${pkgs.gsettings-desktop-schemas.name}/glib-2.0/schemas"
    SED_BIN="${pkgs.gnused}/bin/sed"
    GREP_BIN="${pkgs.gnugrep}/bin/grep"
    AWK_BIN="${pkgs.gawk}/bin/awk"
    SHA256SUM_BIN="${pkgs.coreutils}/bin/sha256sum"
    READLINK_BIN="${pkgs.coreutils}/bin/readlink"
    MKTEMP_BIN="${pkgs.coreutils}/bin/mktemp"
    MV_BIN="${pkgs.coreutils}/bin/mv"
    FLOCK_BIN="${pkgs.util-linux}/bin/flock"
    export GSETTINGS_SCHEMA_DIR
    # Ubuntu's systemd user manager does not discover Nix GIO modules.
    # Load dconf explicitly so gsettings persists changes for GTK and portals.
    export GIO_EXTRA_MODULES="${pkgs.dconf.lib}/lib/gio/modules"
    export GSETTINGS_BACKEND=dconf

    cache_dir="''${XDG_CACHE_HOME:-$HOME/.cache}/DankMaterialShell"
    state_dir="''${XDG_STATE_HOME:-$HOME/.local/state}/DankMaterialShell"
    config_dir="''${XDG_CONFIG_HOME:-$HOME/.config}"
    theme_sync_state_dir="''${XDG_STATE_HOME:-$HOME/.local/state}/nixos-intc/dms-theme-sync"

    colors_json="$cache_dir/dms-colors.json"
    session_json="$state_dir/session.json"
    settings_json="$config_dir/DankMaterialShell/settings.json"
    mode_file="''${XDG_STATE_HOME:-$HOME/.local/state}/dms-theme-mode"

    # dms-theme-sunwait invokes this script directly while the systemd path
    # unit can start the same script for the palette write caused by that IPC
    # call. Serialize both entry points before reading DMS state or writing any
    # client configuration; otherwise their here-docs can interleave and leave
    # (for example) a light Emacs mode containing the dark palette.
    $MKDIR_BIN -p "$theme_sync_state_dir"
    exec 9>"$theme_sync_state_dir/sync.lock"
    $FLOCK_BIN 9

    for _ in $(seq 1 5); do
      if [ -s "$colors_json" ]; then
        break
      fi
      $SLEEP_BIN 1
    done
    if [ ! -s "$colors_json" ]; then
      exit 0
    fi

    # Explicit sunrise/sunset requests win.  Otherwise DMS session state wins
    # so a manual light/dark choice is honored, with the canonical mode file as
    # the startup fallback.  Persist the resolved choice before the fingerprint
    # short-circuit so Emacs and other clients never start from stale state.
    mode="''${DMS_THEME_MODE_OVERRIDE:-}"
    if [ "$mode" != "light" ] && [ "$mode" != "dark" ] && [ -s "$session_json" ]; then
      is_light="$($JQ_BIN -r 'if .isLightMode == true then "true" elif .isLightMode == false then "false" else empty end' "$session_json" 2>/dev/null || true)"
      case "$is_light" in
        true) mode="light" ;;
        false) mode="dark" ;;
      esac
    fi
    if [ "$mode" != "light" ] && [ "$mode" != "dark" ] && [ -s "$mode_file" ]; then
      mode="$(${pkgs.coreutils}/bin/head -n1 "$mode_file" | ${pkgs.coreutils}/bin/tr -d '\r\n' || true)"
    fi
    if [ "$mode" != "light" ] && [ "$mode" != "dark" ]; then
      mode="light"
    fi
    mode_file_tmp="$($MKTEMP_BIN "''${mode_file}.XXXXXX")"
    printf '%s\n' "$mode" > "$mode_file_tmp"
    $MV_BIN -f "$mode_file_tmp" "$mode_file"

    # COSMIC applications follow DMS through the config-only settings watcher.
    cosmic_mode_dir="$config_dir/cosmic/com.system76.CosmicTheme.Mode/v1"
    $MKDIR_BIN -p "$cosmic_mode_dir"
    cosmic_is_dark=false
    if [ "$mode" = "dark" ]; then cosmic_is_dark=true; fi
    if [ "$(cat "$cosmic_mode_dir/is_dark" 2>/dev/null || true)" != "$cosmic_is_dark" ]; then
      cosmic_mode_tmp="$($MKTEMP_BIN "$cosmic_mode_dir/.is_dark.XXXXXX")"
      printf '%s\n' "$cosmic_is_dark" > "$cosmic_mode_tmp"
      $MV_BIN -f "$cosmic_mode_tmp" "$cosmic_mode_dir/is_dark"
    fi

    # DMS updates its session state and palette asynchronously.  During the
    # transition it can briefly publish the active palette into both branches.
    # Never turn that transient state into (for example) a light Emacs theme
    # with dark colors.  Then extract every field with one jq file read so a
    # concurrent atomic replacement cannot mix two palette generations.
    palette_ready=0
    for _ in $(seq 1 20); do
      session_mode="$($JQ_BIN -r 'if .isLightMode == true then "light" elif .isLightMode == false then "dark" else empty end' "$session_json" 2>/dev/null || true)"
      if [ "$session_mode" = "$mode" ] && \
         $JQ_BIN -e '.colors.light.surface != .colors.dark.surface' "$colors_json" >/dev/null 2>&1; then
        palette_ready=1
        break
      fi
      $SLEEP_BIN 0.1
    done
    if [ "$palette_ready" -ne 1 ]; then
      # A path-triggered invocation can race the DMS writer.  Skipping is safe:
      # the final palette write triggers the path again, and sunwait also runs
      # this synchronously.  Do not leave the oneshot in a failed state merely
      # because an intermediate palette was intentionally rejected.
      echo "dms-theme-sync: skipping transient incoherent $mode palette" >&2
      exit 0
    fi

    palette_tsv="$($JQ_BIN -er --arg mode "$mode" '
      .colors[$mode] |
      [.surface, .surface_container_high, .surface_variant,
       .on_surface, .on_surface_variant, .outline,
       .primary, .on_primary, .secondary, .secondary_container,
       .on_secondary_container, .error, .error_container,
       .on_error_container] | @tsv
    ' "$colors_json")"
    IFS=$'\t' read -r \
      bg bg_alt bg_hover fg fg_muted border primary primary_fg \
      accent accent_bg accent_fg err err_bg err_fg <<< "$palette_tsv"

    if [ -z "$bg" ]; then bg="#1f1f1f"; fi
    if [ -z "$bg_alt" ]; then bg_alt="$bg"; fi
    if [ -z "$bg_hover" ]; then bg_hover="$bg_alt"; fi
    if [ -z "$fg" ]; then fg="#e6e6e6"; fi
    if [ -z "$fg_muted" ]; then fg_muted="$fg"; fi
    if [ -z "$border" ]; then border="$fg_muted"; fi
    if [ -z "$primary" ]; then primary="$border"; fi
    if [ -z "$primary_fg" ]; then primary_fg="$fg"; fi
    if [ -z "$accent" ]; then accent="$border"; fi
    if [ -z "$accent_bg" ]; then accent_bg="$bg_alt"; fi
    if [ -z "$accent_fg" ]; then accent_fg="$fg"; fi
    if [ -z "$err" ]; then err="$border"; fi
    if [ -z "$err_bg" ]; then err_bg="$bg_alt"; fi
    if [ -z "$err_fg" ]; then err_fg="$fg"; fi

    # DMS's decorative palette can use lower-contrast tones that work for
    # large shell UI, but Emacs applies these to dense 11pt text.  Keep the
    # HP-OS hue while enforcing >= 4.5:1 contrast on each mode's surfaces.
    if [ "$mode" = "light" ]; then
      emacs_fg_muted="#626a72"
      emacs_accent="#0064d0"
      emacs_error="#d92023"
    else
      emacs_fg_muted="$fg_muted"
      emacs_accent="$accent"
      emacs_error="#e95c5f"
    fi

    font_family="Inter Variable"
    mono_font_family="${hposMonoFontFamily}"
    font_weight="400"
    font_scale="1"
    if [ -s "$settings_json" ]; then
      font_family="$($JQ_BIN -r '.fontFamily // "Inter Variable"' "$settings_json" 2>/dev/null || echo "Inter Variable")"
      mono_font_family="$($JQ_BIN -r '.monoFontFamily // "${hposMonoFontFamily}"' "$settings_json" 2>/dev/null || echo "${hposMonoFontFamily}")"
      font_weight="$($JQ_BIN -r '.fontWeight // 400' "$settings_json" 2>/dev/null || echo "400")"
      font_scale="$($JQ_BIN -r '.fontScale // 1' "$settings_json" 2>/dev/null || echo "1")"
    fi
    if [ -z "$font_family" ] || [ "$font_family" = "null" ]; then font_family="Inter Variable"; fi
    if [ -z "$mono_font_family" ] || [ "$mono_font_family" = "null" ]; then mono_font_family="${hposMonoFontFamily}"; fi
    case "$font_weight" in ""|*[!0-9]*) font_weight="400" ;; esac
    case "$font_scale" in ""|*[!0-9.]*|.*|*.) font_scale="1" ;; esac

    # SessionData rewrites session.json for ordinary UI state (launcher, MPRIS,
    # DND, etc.).  Only refresh other desktop clients when their effective DMS
    # palette or typography actually changes.
    # The Nix store path of this script changes whenever any generated client
    # template changes.  Including it makes renderer changes self-invalidating
    # instead of depending on a manually bumped cache version.
    theme_renderer_version="4"
    theme_renderer_identity="$($READLINK_BIN -f "$0")"
    theme_fingerprint="$(printf '%s\0' \
      "$theme_renderer_version" "$theme_renderer_identity" \
      "$mode" "$bg" "$bg_alt" "$bg_hover" "$fg" "$fg_muted" \
      "$border" "$primary" "$primary_fg" "$accent" "$accent_bg" \
      "$accent_fg" "$err" "$err_bg" "$err_fg" \
      "$emacs_fg_muted" "$emacs_accent" "$emacs_error" "$font_family" \
      "$mono_font_family" "$font_weight" "$font_scale" | \
      $SHA256SUM_BIN | $AWK_BIN '{print $1}')"
    theme_fingerprint_file="$theme_sync_state_dir/effective-theme.sha256"
    if [ -f "$theme_fingerprint_file" ] && \
       [ "$(<"$theme_fingerprint_file")" = "$theme_fingerprint" ]; then
      exit 0
    fi

    css_string() {
      printf '%s' "$1" | $SED_BIN 's/\\/\\\\/g; s/"/\\"/g'
    }

    font_size_px() {
      $AWK_BIN -v scale="$font_scale" -v base="$1" 'BEGIN { printf "%d", (base * scale) + 0.5 }'
    }

    font_family_css="$(css_string "$font_family")"
    font_small_px="$(font_size_px 12)"
    font_medium_px="$(font_size_px 14)"
    gtk_font_size="$(font_size_px 11)"
    emacs_font_height="$(font_size_px 110)"
    font_medium_weight="500"

    hex_alpha() {
      echo "''${1}''${2:-ff}"
    }

    hex_rgb() {
      local h="''${1#\#}"
      printf '%d, %d, %d' "0x''${h:0:2}" "0x''${h:2:2}" "0x''${h:4:2}"
    }

    ensure_writable() {
      local path="$1"
      if [ -L "$path" ]; then
        local target
        target="$(readlink -f "$path" || true)"
        rm -f "$path"
        if [ -n "$target" ] && [ -f "$target" ]; then
          cp "$target" "$path"
        fi
      fi
      if [ -e "$path" ] && [ ! -w "$path" ]; then
        chmod u+w "$path" || true
      fi
    }

    fuzzel_dir="$config_dir/fuzzel"
    swaync_dir="$config_dir/swaync"
    gtk3_dir="$config_dir/gtk-3.0"
    gtk4_dir="$config_dir/gtk-4.0"
    emacs_dir="$config_dir/emacs"
    alacritty_dir="$config_dir/alacritty"
    $MKDIR_BIN -p "$fuzzel_dir" "$swaync_dir" "$gtk3_dir" "$gtk4_dir" "$emacs_dir" "$alacritty_dir"

    ensure_writable "$fuzzel_dir/fuzzel.ini"
    ensure_writable "$swaync_dir/style.css"
    ensure_writable "$alacritty_dir/hp-os.toml"

    # Alacritty cannot select a light/dark pair itself. Keep its imported,
    # writable palette synchronized with the same DMS mode used by GTK and
    # Emacs; live_config_reload updates existing terminal windows.
    alacritty_variant="$alacritty_dir/themes/hp-os-$mode.toml"
    if [ -s "$alacritty_variant" ]; then
      ${pkgs.coreutils}/bin/cp "$alacritty_variant" "$alacritty_dir/hp-os.toml"
    fi

    # Ghostty follows the desktop portal through its light/dark theme pair.
    # A persistent DMS override would leak this session mode into HP-OS.

    cat > "$fuzzel_dir/fuzzel.ini" <<EOF
[main]
font=$font_family,Noto Color Emoji:size=13
prompt=>
width=50
lines=10
horizontal-pad=24
vertical-pad=12
inner-pad=8
line-height=22
layer=overlay
keyboard-focus=exclusive
exit-on-keyboard-focus-loss=no
launch-prefix=${config.home.homeDirectory}/.local/bin/fuzzel-launch

[colors]
background=$(hex_alpha "$bg")
text=$(hex_alpha "$fg")
prompt=$(hex_alpha "$primary")
placeholder=$(hex_alpha "$fg_muted")
input=$(hex_alpha "$fg")
match=$(hex_alpha "$primary")
selection=$(hex_alpha "$primary")
selection-text=$(hex_alpha "$primary_fg")
selection-match=$(hex_alpha "$primary_fg")
counter=$(hex_alpha "$fg_muted")
border=$(hex_alpha "$primary")

[border]
width=2
radius=16
selection-radius=8
EOF

    cp "${pkgs.swaynotificationcenter}/etc/xdg/swaync/style.css" "$swaync_dir/style.css"
    cat >> "$swaync_dir/style.css" <<EOF

/* DMS theme overrides, appended to preserve SwayNC layout rules. */
* {
  font-family: "$font_family_css", "Noto Sans", "Noto Color Emoji", sans-serif;
  font-weight: $font_weight;
}

:root {
  --cc-bg: $bg;
  --noti-border-color: $border;
  --noti-bg: $(hex_rgb "$bg");
  --noti-bg-alpha: 1.0;
  --noti-bg-darker: $bg_alt;
  --noti-bg-hover: $bg_hover;
  --noti-bg-focus: $bg_hover;
  --noti-close-bg: $bg_alt;
  --noti-close-bg-hover: $bg_hover;
  --text-color: $fg;
  --text-color-disabled: $fg_muted;
  --bg-selected: $accent_bg;
  --font-size-body: ''${font_small_px}px;
  --font-size-summary: ''${font_medium_px}px;
}

.notification-row .notification-background .notification .notification-default-action .notification-content .text-box label {
  font-family: "$font_family_css", "Noto Sans", "Noto Color Emoji", sans-serif;
}

.notification-row .notification-background .notification .notification-default-action .notification-content .text-box .summary {
  font-size: ''${font_medium_px}px;
  font-weight: $font_medium_weight;
}

.notification-row .notification-background .notification .notification-default-action .notification-content .text-box .time,
.notification-row .notification-background .notification .notification-default-action .notification-content .text-box .body {
  font-size: ''${font_small_px}px;
  font-weight: $font_weight;
}

@define-color cc-bg $bg;
@define-color noti-border-color $border;
@define-color noti-bg rgba($(hex_rgb "$bg"), 1.0);
@define-color noti-bg-opaque $bg;
@define-color noti-bg-darker $bg_alt;
@define-color noti-bg-hover $bg_hover;
@define-color noti-bg-hover-opaque $bg_hover;
@define-color noti-bg-focus $bg_hover;
@define-color noti-close-bg $bg_alt;
@define-color noti-close-bg-hover $bg_hover;
@define-color text-color $fg;
@define-color text-color-disabled $fg_muted;
@define-color bg-selected $accent_bg;

.notification-row .notification-background .notification.critical {
  background: $bg;
  color: $fg;
  border-color: $primary;
}
EOF

    if ${pkgs.procps}/bin/pgrep -x swaync >/dev/null 2>&1; then
      $SWAYNC_CLIENT_BIN -R >/dev/null 2>&1 || $SYSTEMCTL_BIN --user restart swaync
    fi

    if [ "$mode" = "dark" ]; then
      gtk_pref=1
      gtk_scheme="prefer-dark"
      gtk_theme="Adwaita-dark"
      kde_scheme="BreezeDark"
    else
      gtk_pref=0
      gtk_scheme="prefer-light"
      gtk_theme="Adwaita"
      kde_scheme="BreezeLight"
    fi

    ensure_writable "$gtk3_dir/settings.ini"
    ensure_writable "$gtk4_dir/settings.ini"
    ensure_writable "$config_dir/kdeglobals"

    cat > "$gtk3_dir/settings.ini" <<EOF
[Settings]
gtk-application-prefer-dark-theme=$gtk_pref
gtk-theme-name=$gtk_theme
gtk-font-name=$font_family $gtk_font_size
EOF

    cat > "$gtk4_dir/settings.ini" <<EOF
[Settings]
gtk-application-prefer-dark-theme=$gtk_pref
gtk-theme-name=$gtk_theme
gtk-font-name=$font_family $gtk_font_size
EOF

    if [ -f "$config_dir/kdeglobals" ]; then
      if $GREP_BIN -q '^ColorScheme=' "$config_dir/kdeglobals"; then
        $SED_BIN -i "s/^ColorScheme=.*/ColorScheme=$kde_scheme/" "$config_dir/kdeglobals"
      else
        printf "\n[General]\nColorScheme=%s\n" "$kde_scheme" >> "$config_dir/kdeglobals"
      fi
    else
      cat > "$config_dir/kdeglobals" <<EOF
[General]
ColorScheme=$kde_scheme
EOF
    fi

    $GSETTINGS_BIN set org.gnome.desktop.interface color-scheme "$gtk_scheme" >/dev/null 2>&1 || true
    $GSETTINGS_BIN set org.gnome.desktop.interface gtk-theme "$gtk_theme" >/dev/null 2>&1 || true
    $GSETTINGS_BIN set org.gnome.desktop.interface font-name "$font_family $gtk_font_size" >/dev/null 2>&1 || true
    $GSETTINGS_BIN set org.gnome.desktop.interface document-font-name "$font_family $gtk_font_size" >/dev/null 2>&1 || true
    $GSETTINGS_BIN set org.gnome.desktop.interface monospace-font-name "$mono_font_family $gtk_font_size" >/dev/null 2>&1 || true

    font_family_el="$($JQ_BIN -Rn --arg value "$font_family" '$value')"
    mono_font_family_el="$($JQ_BIN -Rn --arg value "$mono_font_family" '$value')"
    emacs_theme="$emacs_dir/hp-os-desktop-theme.el"
    ensure_writable "$emacs_theme"
    emacs_theme_tmp="$($MKTEMP_BIN "$emacs_dir/.hp-os-desktop-theme.el.XXXXXX")"
    cat > "$emacs_theme_tmp" <<EOF
;;; hp-os-desktop-theme.el --- generated from the active DMS palette -*- lexical-binding: t; -*-

(require 'patrl-desktop-theme)

(defconst jw/hp-os-renderer-version $theme_renderer_version)

(patrl/desktop-theme-apply
 (list :mode '$mode
       :background "$bg"
       :background-alt "$bg_alt"
       :background-hover "$bg_hover"
       :foreground "$fg"
       :foreground-muted "$emacs_fg_muted"
       :border "$border"
       :primary "$primary"
       :primary-foreground "$primary_fg"
       :accent "$emacs_accent"
       :error "$emacs_error"
       :font-family $font_family_el
       :mono-font-family $mono_font_family_el
       :notmuch-font-family "JetBrains Mono"
       :font-height $emacs_font_height))

(provide 'hp-os-desktop-theme)
;;; hp-os-desktop-theme.el ends here
EOF

    $MV_BIN -f "$emacs_theme_tmp" "$emacs_theme"

    # Compatibility for the separately installed fleet Emacs loader.
    ${pkgs.coreutils}/bin/ln -sfn "$emacs_theme" "$emacs_dir/harmonyos-desktop-theme.el"
    ${dmsEmacsThemeApplyScript} || true
    theme_fingerprint_tmp="$($MKTEMP_BIN "''${theme_fingerprint_file}.XXXXXX")"
    printf '%s\n' "$theme_fingerprint" > "$theme_fingerprint_tmp"
    $MV_BIN -f "$theme_fingerprint_tmp" "$theme_fingerprint_file"
  ''

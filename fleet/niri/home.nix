# Shared session controls. Device identities and GPU configuration stay with hosts.
{ config, lib, pkgs, ... }:
let
  cfg = config.programs.hp-os-fleet.niri;
  screenshot = pkgs.writeShellApplication {
    name = "screenshot-copy";
    runtimeInputs = [ pkgs.coreutils pkgs.grim pkgs.slurp pkgs.wl-clipboard pkgs.libnotify cfg.niriPackage ];
    text = builtins.readFile ./screenshot-copy.sh;
  };
  focused = pkgs.writeShellApplication {
    name = "fuzzel-focused";
    runtimeInputs = [ pkgs.fuzzel pkgs.coreutils ];
    text = ''
      ${lib.optionalString (cfg.dmsPackage != null) ''
        for target in spotlight launcher keybinds; do
          timeout --kill-after=0.15s 0.35s ${cfg.dmsPackage}/bin/dms ipc "$target" close >/dev/null 2>&1 || true
        done
      ''}
      exec fuzzel --layer=overlay --keyboard-focus=exclusive --no-exit-on-keyboard-focus-loss "$@"
    '';
  };
  clipboard = pkgs.writeShellApplication {
    name = "hp-os-clipboard-menu";
    runtimeInputs = [ pkgs.cliphist pkgs.fuzzel pkgs.wl-clipboard ];
    text = ''
      selected=$(cliphist list | fuzzel --dmenu --prompt="Clipboard> ") || exit 0
      [ -n "$selected" ] || exit 0
      printf '%s\n' "$selected" | cliphist decode | wl-copy
    '';
  };
  media = config.programs.hp-os-fleet.mediaKeys.package;
  common = builtins.readFile ./navigation.kdl + ''
    Mod+Alt+V hotkey-overlay-title="Clipboard History" { spawn "${clipboard}/bin/hp-os-clipboard-menu"; }
    Mod+Return { spawn "${pkgs.foot}/bin/foot"; }
    Mod+T { spawn "${pkgs.cosmic-term}/bin/cosmic-term"; }
    Alt+T { spawn "${pkgs.cosmic-term}/bin/cosmic-term"; }
    Mod+D { spawn "${focused}/bin/fuzzel-focused"; }
    Alt+D { spawn "${focused}/bin/fuzzel-focused"; }
    Mod+Shift+D { spawn "${pkgs.fuzzel}/bin/fuzzel"; }
    Super+Shift+4 hotkey-overlay-title="Screenshot: Copy Area" { spawn "${screenshot}/bin/screenshot-copy" "area"; }
    Print hotkey-overlay-title="Screenshot: Copy Area" { spawn "${screenshot}/bin/screenshot-copy" "area"; }
    Ctrl+Print hotkey-overlay-title="Screenshot: Copy Screen" { spawn "${screenshot}/bin/screenshot-copy" "screen"; }
    Alt+Print hotkey-overlay-title="Screenshot: Copy Window" { spawn "${screenshot}/bin/screenshot-copy" "window"; }
    XF86AudioRaiseVolume allow-when-locked=true { spawn "${media}/bin/hp-os-media-key" "volume-up"; }
    XF86AudioLowerVolume allow-when-locked=true { spawn "${media}/bin/hp-os-media-key" "volume-down"; }
    XF86AudioMute allow-when-locked=true { spawn "${media}/bin/hp-os-media-key" "mute"; }
    XF86AudioMicMute allow-when-locked=true { spawn "${media}/bin/hp-os-media-key" "mic-mute"; }
    Mod+Shift+M { spawn "${media}/bin/hp-os-media-key" "mic-mute"; }
    XF86AudioPlay allow-when-locked=true { spawn "${media}/bin/hp-os-media-key" "play-pause"; }
    XF86AudioStop allow-when-locked=true { spawn "${media}/bin/hp-os-media-key" "stop"; }
    XF86AudioNext allow-when-locked=true { spawn "${media}/bin/hp-os-media-key" "next"; }
    XF86AudioPrev allow-when-locked=true { spawn "${media}/bin/hp-os-media-key" "previous"; }
    XF86MonBrightnessUp { spawn "${media}/bin/hp-os-media-key" "brightness-up"; }
    XF86MonBrightnessDown { spawn "${media}/bin/hp-os-media-key" "brightness-down"; }
  '';
  hpBindings = common + ''
    Mod+Space { spawn "hp-os" "ipc" "hpos" "applications"; }
    Mod+A { spawn "hp-os" "ipc" "hpos" "applications"; }
    Mod+S { spawn "hp-os" "ipc" "hpos" "search"; }
    Mod+C { spawn "hp-os" "ipc" "hpos" "controlCenter"; }
    Mod+Comma { spawn "hp-os" "settings"; }
    Mod+L { spawn "hp-os" "ipc" "lock" "activate"; }
    Mod+Alt+L { spawn "hp-os" "ipc" "lock" "activate"; }
    Alt+L { spawn "hp-os" "ipc" "lock" "activate"; }
    Mod+Shift+Left { move-column-left; }
    Mod+Shift+Right { move-column-right; }
    Mod+Shift+Page_Up { move-column-to-workspace-up; }
    Mod+Shift+Page_Down { move-column-to-workspace-down; }
    Mod+Shift+Tab { spawn "hp-os" "settings"; }
  '';
  dmsBindings = common + lib.optionalString (cfg.dmsPackage != null) ''
    Mod+Space { spawn "${cfg.dmsPackage}/bin/dms" "ipc" "call" "spotlight" "toggle"; }
    Mod+A { spawn "${cfg.dmsPackage}/bin/dms" "ipc" "call" "spotlight" "toggle"; }
    Mod+L { focus-column-right; }
    Mod+C { center-column; }
    Mod+Comma { consume-window-into-column; }
    Mod+Alt+L { spawn "${cfg.dmsPackage}/bin/dms" "ipc" "call" "lock" "lock"; }
    Alt+L { spawn "${cfg.dmsPackage}/bin/dms" "ipc" "call" "lock" "lock"; }
    Mod+Shift+Left { focus-monitor-left; }
    Mod+Shift+Right { focus-monitor-right; }
    Mod+Shift+Page_Up { move-workspace-up; }
    Mod+Shift+Page_Down { move-workspace-down; }
    Mod+Shift+Tab { spawn "${cfg.dmsPackage}/bin/dms" "ipc" "call" "wallhavenCarousel" "discover"; }
  '';
  hpSource = pkgs.writeText "fleet-hp-os-bindings.kdl" ("binds {\n" + hpBindings + "}\n");
  sync = pkgs.writeShellScriptBin "hp-os-fleet-sync-bindings" ''
    set -eu
    root="''${XDG_CONFIG_HOME:-$HOME/.config}/hp-os/niri"
    mkdir -p "$root/config.d"
    startup="$root/config.d/50-startup.kdl"
    touch "$startup"
    ${pkgs.gnused}/bin/sed -i '/\/\/ snapdragon-launcher$/d' "$startup"
    ${lib.optionalString (cfg.hpOsPackage != null) ''
      if [ ! -e "$root/config.kdl" ]; then
        cp ${cfg.hpOsPackage}/share/hp-os/packaging/niri.kdl "$root/config.kdl"
        chmod u+w "$root/config.kdl"
      fi
      exec ${pkgs.python3}/bin/python3 ${../../vendor/HP-OSShell/packaging/sync-niri-bindings.py} \
        --source ${hpSource} --target "$root/config.kdl" \
        --baseline ${cfg.hpOsPackage}/share/hp-os/packaging/niri.kdl --niri ${cfg.niriPackage}/bin/niri
    ''}
  '';
in {
  options.programs.hp-os-fleet.niri = {
    enable = lib.mkEnableOption "shared Niri controls and screenshot helpers";
    hpOsPackage = lib.mkOption { type = lib.types.nullOr lib.types.package; default = null; };
    dmsPackage = lib.mkOption { type = lib.types.nullOr lib.types.package; default = null; };
    niriPackage = lib.mkOption { type = lib.types.package; default = pkgs.niri; };
    hpOsBindings = lib.mkOption { type = lib.types.lines; readOnly = true; default = hpBindings; };
    dmsBindings = lib.mkOption { type = lib.types.lines; readOnly = true; default = dmsBindings; };
  };
  config = lib.mkIf (config.programs.hp-os-fleet.enable && cfg.enable) {
    home.packages = [ screenshot focused sync clipboard pkgs.wl-clip-persist pkgs.cliphist ];
    home.activation.hpOsFleetBindings = lib.mkIf (cfg.hpOsPackage != null)
      (lib.hm.dag.entryAfter [ "linkGeneration" "hposNiriBindings" "snapdragonSessionStartup" ] ''
        $DRY_RUN_CMD ${sync}/bin/hp-os-fleet-sync-bindings
      '');
  };
}

{ config, pkgs, lib, xwayland-satellite, ... }:
let
  system = pkgs.stdenv.hostPlatform.system;
  niri = pkgs.niri;
  mediaKeys = config.programs.hp-os-fleet.mediaKeys.package;
  hdrControl = pkgs.writeShellApplication {
    name = "goran-hdr";
    runtimeInputs = [ pkgs.python3 niri ];
    text = ''
      export NIRI_BINARY=${niri}/bin/niri
      exec ${pkgs.python3}/bin/python3 ${./dms-hdr/hdr-control.py} "$@"
    '';
  };
  brightness = pkgs.writeShellApplication {
    name = "goran-brightness";
    runtimeInputs = [ pkgs.coreutils pkgs.util-linux pkgs.python3 mediaKeys ];
    text = ''
      export GORAN_PANEL_SCRIPT=${./goran-panel.py}
      export GORAN_PANEL_PYTHON=${pkgs.python3}/bin/python3
      ${builtins.readFile ./brightness.sh}
    '';
  };
  startup = pkgs.writeShellScript "goran-niri-startup" ''
    set -eu
    # Select the gestures only after this compositor has started. This keeps
    # Home Manager activation compatible with an older running compositor.
    touch_tmp=$(mktemp "${config.xdg.configHome}/niri/.touch-gestures.XXXXXX")
    cp ${pkgs.writeText "goran-touch-gestures.kdl" ''
      gestures {
        touchscreen-swipe {
          fingers 3
          horizontal-swipe "move-view"
          tap-more { toggle-overview; }
          swipe-more-up { fullscreen-window; }
        }
        touchscreen-edge-swipe {
          left { focus-column-left; }
          right { focus-column-right; }
        }
      }
    ''} "$touch_tmp"
    mv -f "$touch_tmp" "${config.xdg.configHome}/niri/touch-gestures.kdl"
    ${pkgs.systemd}/bin/systemctl --user import-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE DBUS_SESSION_BUS_ADDRESS SSH_AUTH_SOCK || true
    ${pkgs.dbus}/bin/dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE DBUS_SESSION_BUS_ADDRESS SSH_AUTH_SOCK || true
    ${pkgs.systemd}/bin/systemctl --user start graphical-session.target goran-niri.target
  '';
  shutdown = pkgs.writeShellScript "goran-niri-shutdown" ''
    ${pkgs.systemd}/bin/systemctl --user stop goran-niri.target || true
  '';
in {
  home.packages = [
    niri brightness hdrControl xwayland-satellite.packages.${system}.default
    pkgs.cosmic-term pkgs.cosmic-launcher pkgs.cosmic-app-library
  ];

  # Seed before linking the new main config. Later activations keep user choices.
  home.activation.goranHdrSettingsInit = lib.hm.dag.entryBetween
    [ "linkGeneration" ] [ "writeBoundary" ] ''
      if [ -z "''${DRY_RUN_CMD:-}" ]; then
        ${hdrControl}/bin/goran-hdr init >/dev/null
      fi
    '';

  systemd.user.targets.goran-niri = {
    Unit = {
      Description = "Goran Niri session";
      PartOf = [ "graphical-session.target" ];
    };
  };

  # niri-session starts niri.service through the Ubuntu user systemd manager.
  # Home Manager installs this unit where that manager can discover it.
  systemd.user.services.niri = {
    Unit = {
      Description = "Niri Wayland compositor";
      # Keep current Wayland clients connected during Home Manager updates.
      # The new compositor starts after a coordinated logout and login.
      X-SwitchMethod = "keep-old";
      BindsTo = [ "graphical-session.target" ];
      Before = [ "graphical-session.target" "xdg-desktop-autostart.target" ];
      Wants = [ "graphical-session-pre.target" "xdg-desktop-autostart.target" ];
      After = [ "graphical-session-pre.target" ];
    };
    Service = {
      Slice = "session.slice";
      Type = "notify";
      ExecStart = "${niri}/bin/niri --session";
      Environment = [
        "PATH=%h/.nix-profile/bin:/usr/local/bin:/usr/bin:/bin"
        "GBM_BACKEND=nvidia-drm"
        "__GLX_VENDOR_LIBRARY_NAME=nvidia"
        "GTK_IM_MODULE=fcitx"
        "QT_IM_MODULE=fcitx"
        "XMODIFIERS=@im=fcitx"
      ];
    };
  };
  systemd.user.targets.niri-shutdown = {
    Unit = {
      Description = "Shutdown Niri session";
      DefaultDependencies = false;
      StopWhenUnneeded = true;
      Conflicts = [ "graphical-session.target" "graphical-session-pre.target" ];
      After = [ "graphical-session.target" "graphical-session-pre.target" ];
    };
  };

  xdg.configFile."xdg-desktop-portal/niri-portals.conf".text = ''
    [preferred]
    default=gnome;gtk;
    org.freedesktop.impl.portal.FileChooser=gtk;
    org.freedesktop.impl.portal.Access=gtk;
    org.freedesktop.impl.portal.Notification=gtk;
    org.freedesktop.impl.portal.Secret=gnome-keyring;
  '';

  xdg.configFile."niri/config.kdl".text = ''
    // Goran ARM64 Ubuntu session. Based on Slazenger's Niri and DMS layout.
    // First matching output wins. The HDR extension owns the same internal
    // output definition previously declared here, before DMS output includes.
    // Its writable include survives Home Manager updates and reloads live.
    include optional=true "${config.xdg.configHome}/niri/hdr.kdl"
    input {
      keyboard {
        xkb {
          // Caps Lock and both physical Control keys all send Control.
          options "ctrl:nocaps"
        }
      }
      touch {
        map-to-output "eDP-1"
      }
      touchpad {
        // Require a physical press so finger brushes cannot generate tap clicks.
        dwt
        drag false
        click-method "clickfinger"
        natural-scroll
        scroll-method "two-finger"
        scroll-factor 0.5
      }
    }
    include optional=true "${config.xdg.configHome}/niri/touch-gestures.kdl"
    layout {
      gaps 8
      focus-ring {
        width 2
        active-color "#0287c8"
        inactive-color "#988d6d"
      }
      border {
        off
      }
      shadow {
        on
        softness 24
        spread 2
        offset x=0 y=4
        color "#00000045"
      }
    }
    // Slazenger keeps client-side titlebars and window controls enabled.
    spawn-at-startup "${startup}"
    spawn-at-startup "${brightness}/bin/goran-brightness" "restore"
    spawn-at-startup "${xwayland-satellite.packages.${system}.default}/bin/xwayland-satellite"
    binds {
      // The OmniBook sends media keycodes directly; Fn+F1 sends plain F1.
      XF86AudioMute allow-when-locked=true { spawn "${mediaKeys}/bin/hp-os-media-key" "mute"; }
      XF86AudioLowerVolume allow-when-locked=true { spawn "${mediaKeys}/bin/hp-os-media-key" "volume-down"; }
      XF86AudioRaiseVolume allow-when-locked=true { spawn "${mediaKeys}/bin/hp-os-media-key" "volume-up"; }
      XF86AudioMicMute allow-when-locked=true { spawn "${mediaKeys}/bin/hp-os-media-key" "mic-mute"; }
      XF86AudioPlay allow-when-locked=true { spawn "${mediaKeys}/bin/hp-os-media-key" "play-pause"; }
      XF86AudioStop allow-when-locked=true { spawn "${mediaKeys}/bin/hp-os-media-key" "stop"; }
      XF86AudioNext allow-when-locked=true { spawn "${mediaKeys}/bin/hp-os-media-key" "next"; }
      XF86AudioPrev allow-when-locked=true { spawn "${mediaKeys}/bin/hp-os-media-key" "previous"; }
      XF86MonBrightnessUp allow-when-locked=true { spawn "${brightness}/bin/goran-brightness" "up"; }
      XF86MonBrightnessDown allow-when-locked=true { spawn "${brightness}/bin/goran-brightness" "down"; }
      // Slazenger desktop shortcuts, verified against its live config on 4 Oct 2026.
      // Alt aliases launch directly here; Slazenger's VNC wrappers are absent there.
      Mod+T hotkey-overlay-title="Open a Terminal: cosmic-term" { spawn "${pkgs.cosmic-term}/bin/cosmic-term"; }
      Alt+T hotkey-overlay-title="Open a Terminal (remote)" { spawn "${pkgs.cosmic-term}/bin/cosmic-term"; }
      Mod+D hotkey-overlay-title="Run an Application: fuzzel" { spawn "${config.home.homeDirectory}/.local/bin/fuzzel-focused"; }
      Alt+D hotkey-overlay-title="Run an Application (remote)" { spawn "${config.home.homeDirectory}/.local/bin/fuzzel-focused"; }
      Mod+A hotkey-overlay-title="Run an Application: cosmic-launcher" { spawn "${pkgs.cosmic-launcher}/bin/cosmic-launcher"; }
      Alt+A hotkey-overlay-title="Run an Application (remote)" { spawn "${pkgs.cosmic-launcher}/bin/cosmic-launcher"; }
      Mod+Shift+D hotkey-overlay-title="Open the App Library" { spawn "${pkgs.cosmic-app-library}/bin/cosmic-app-library"; }
      Mod+Shift+Tab hotkey-overlay-title="Search Wallhaven Wallpapers" { spawn "${config.programs.dank-material-shell.package}/bin/dms" "ipc" "call" "wallhavenCarousel" "discover"; }
      Alt+Shift+D hotkey-overlay-title="Open the App Library (remote)" { spawn "${pkgs.cosmic-app-library}/bin/cosmic-app-library"; }
      Mod+Alt+L hotkey-overlay-title="Lock the Screen" { spawn "${config.programs.dank-material-shell.package}/bin/dms" "ipc" "call" "lock" "lock"; }
      Alt+L hotkey-overlay-title="Lock the Screen (remote)" { spawn "${config.programs.dank-material-shell.package}/bin/dms" "ipc" "call" "lock" "lock"; }
      Mod+Shift+M hotkey-overlay-title="Toggle Microphone" { spawn "${pkgs.wireplumber}/bin/wpctl" "set-mute" "@DEFAULT_AUDIO_SOURCE@" "toggle"; }
      Super+Alt+S allow-when-locked=true hotkey-overlay-title=null { spawn-sh "${pkgs.procps}/bin/pkill orca || exec ${pkgs.orca}/bin/orca"; }
      // Native window, column, monitor, workspace, and wheel actions match Slazenger.
      Mod+M repeat=false hotkey-overlay-title="Maximize Window to Edges" { maximize-window-to-edges; }
      Mod+Shift+Slash { show-hotkey-overlay; }
      Mod+O repeat=false { toggle-overview; }
      Mod+Q repeat=false { close-window; }
      Mod+Left  { focus-column-left; }
      Mod+Down  { focus-window-down; }
      Mod+Up    { focus-window-up; }
      Mod+Right { focus-column-right; }
      Mod+H     { focus-column-left; }
      Mod+J     { focus-window-down; }
      Mod+K     { focus-window-up; }
      Mod+L     { focus-column-right; }
      Mod+Ctrl+Left  { move-column-left; }
      Mod+Ctrl+Down  { move-window-down; }
      Mod+Ctrl+Up    { move-window-up; }
      Mod+Ctrl+Right { move-column-right; }
      Mod+Ctrl+H     { move-column-left; }
      Mod+Ctrl+J     { move-window-down; }
      Mod+Ctrl+K     { move-window-up; }
      Mod+Ctrl+L     { move-column-right; }
      Mod+Home { focus-column-first; }
      Mod+End  { focus-column-last; }
      Mod+Ctrl+Home { move-column-to-first; }
      Mod+Ctrl+End  { move-column-to-last; }
      Mod+Shift+Left  { focus-monitor-left; }
      Mod+Shift+Down  { focus-monitor-down; }
      Mod+Shift+Up    { focus-monitor-up; }
      Mod+Shift+Right { focus-monitor-right; }
      Mod+Shift+H     { focus-monitor-left; }
      Mod+Shift+J     { focus-monitor-down; }
      Mod+Shift+K     { focus-monitor-up; }
      Mod+Shift+L     { focus-monitor-right; }
      Mod+Shift+Ctrl+Left  { move-column-to-monitor-left; }
      Mod+Shift+Ctrl+Down  { move-column-to-monitor-down; }
      Mod+Shift+Ctrl+Up    { move-column-to-monitor-up; }
      Mod+Shift+Ctrl+Right { move-column-to-monitor-right; }
      Mod+Shift+Ctrl+H     { move-column-to-monitor-left; }
      Mod+Shift+Ctrl+J     { move-column-to-monitor-down; }
      Mod+Shift+Ctrl+K     { move-column-to-monitor-up; }
      Mod+Shift+Ctrl+L     { move-column-to-monitor-right; }
      Mod+Page_Down      { focus-workspace-down; }
      Mod+Page_Up        { focus-workspace-up; }
      Mod+U              { focus-workspace-down; }
      Mod+I              { focus-workspace-up; }
      Mod+Ctrl+Page_Down { move-column-to-workspace-down; }
      Mod+Ctrl+Page_Up   { move-column-to-workspace-up; }
      Mod+Ctrl+U         { move-column-to-workspace-down; }
      Mod+Ctrl+I         { move-column-to-workspace-up; }
      Mod+Shift+Page_Down { move-workspace-down; }
      Mod+Shift+Page_Up   { move-workspace-up; }
      Mod+Shift+U         { move-workspace-down; }
      Mod+Shift+I         { move-workspace-up; }
      Mod+WheelScrollDown      cooldown-ms=150 { focus-workspace-down; }
      Mod+WheelScrollUp        cooldown-ms=150 { focus-workspace-up; }
      Mod+Ctrl+WheelScrollDown cooldown-ms=150 { move-column-to-workspace-down; }
      Mod+Ctrl+WheelScrollUp   cooldown-ms=150 { move-column-to-workspace-up; }
      Mod+WheelScrollRight      { focus-column-right; }
      Mod+WheelScrollLeft       { focus-column-left; }
      Mod+Ctrl+WheelScrollRight { move-column-right; }
      Mod+Ctrl+WheelScrollLeft  { move-column-left; }
      Mod+Shift+WheelScrollDown      { focus-column-right; }
      Mod+Shift+WheelScrollUp        { focus-column-left; }
      Mod+Ctrl+Shift+WheelScrollDown { move-column-right; }
      Mod+Ctrl+Shift+WheelScrollUp   { move-column-left; }
      Mod+1 { focus-workspace 1; }
      Mod+2 { focus-workspace 2; }
      Mod+3 { focus-workspace 3; }
      Mod+4 { focus-workspace 4; }
      Mod+5 { focus-workspace 5; }
      Mod+6 { focus-workspace 6; }
      Mod+7 { focus-workspace 7; }
      Mod+8 { focus-workspace 8; }
      Mod+9 { focus-workspace 9; }
      Mod+Ctrl+1 { move-column-to-workspace 1; }
      Mod+Ctrl+2 { move-column-to-workspace 2; }
      Mod+Ctrl+3 { move-column-to-workspace 3; }
      Mod+Ctrl+4 { move-column-to-workspace 4; }
      Mod+Ctrl+5 { move-column-to-workspace 5; }
      Mod+Ctrl+6 { move-column-to-workspace 6; }
      Mod+Ctrl+7 { move-column-to-workspace 7; }
      Mod+Ctrl+8 { move-column-to-workspace 8; }
      Mod+Ctrl+9 { move-column-to-workspace 9; }
      Mod+BracketLeft  { consume-or-expel-window-left; }
      Mod+BracketRight { consume-or-expel-window-right; }
      Mod+Comma  { consume-window-into-column; }
      Mod+Period { expel-window-from-column; }
      Mod+R { switch-preset-column-width; }
      Mod+Shift+R { switch-preset-window-height; }
      Mod+Ctrl+R { reset-window-height; }
      Mod+F { maximize-column; }
      Mod+Shift+F { fullscreen-window; }
      Mod+Ctrl+F { expand-column-to-available-width; }
      Mod+C { center-column; }
      Mod+Ctrl+C { center-visible-columns; }
      Mod+Minus { set-column-width "-10%"; }
      Mod+Equal { set-column-width "+10%"; }
      Mod+Shift+Minus { set-window-height "-10%"; }
      Mod+Shift+Equal { set-window-height "+10%"; }
      Mod+V       { toggle-window-floating; }
      Mod+Shift+V { switch-focus-between-floating-and-tiling; }
      Mod+W { toggle-column-tabbed-display; }
      Mod+Escape allow-inhibiting=false { toggle-keyboard-shortcuts-inhibit; }
      Mod+Shift+E hotkey-overlay-title="Quit Niri" { quit; }
      Ctrl+Alt+Delete hotkey-overlay-title="Quit Niri" { quit; }
      Mod+Shift+P { power-off-monitors; }
      Mod+Space hotkey-overlay-title="DMS Launcher" { spawn "${config.programs.dank-material-shell.package}/bin/dms" "ipc" "call" "spotlight" "toggle"; }
      Super+Shift+4 hotkey-overlay-title="Screenshot: Copy Area" { spawn "${config.home.homeDirectory}/.local/bin/screenshot-copy" "area"; }
      Print hotkey-overlay-title="Screenshot: Copy Area" { spawn "${config.home.homeDirectory}/.local/bin/screenshot-copy" "area"; }
      Ctrl+Print hotkey-overlay-title="Screenshot: Copy Screen" { spawn "${config.home.homeDirectory}/.local/bin/screenshot-copy" "screen"; }
      Alt+Print hotkey-overlay-title="Screenshot: Copy Window" { spawn "${config.home.homeDirectory}/.local/bin/screenshot-copy" "window"; }
    }
    hotkey-overlay {
      skip-at-startup
    }
    screenshot-path "~/Pictures/Screenshots/Screenshot from %Y-%m-%d %H-%M-%S.png"
    animations {
      slowdown 1.0
    }
    window-rule {
      geometry-corner-radius 12
      clip-to-geometry true
    }
    // Googlebook's SDL/virgl scanout is 1920x1080. At the internal panel's
    // 1.5 scale, allow 720 logical pixels plus the 26-pixel Xwayland titlebar.
    // Apply on every new VM window, including a native OTA reboot.
    window-rule {
      match app-id="^qemu-system-aarch64$" title="^QEMU \\(HP Googlebook OTA TEST-0\\)"
      open-floating true
      default-column-width { fixed 1280; }
      default-window-height { fixed 746; }
    }

    // Apply DMS theme geometry and colors after the baseline defaults.
    include optional=true "${config.home.homeDirectory}/.config/niri/dms/cursor.kdl"
    include optional=true "${config.home.homeDirectory}/.config/niri/dms/colors.kdl"
    include optional=true "${config.home.homeDirectory}/.config/niri/dms/outputs.kdl"
    include optional=true "${config.home.homeDirectory}/.config/niri/dms/layout.kdl"
    include optional=true "${config.home.homeDirectory}/.config/niri/dms/binds.kdl"
    include optional=true "${config.home.homeDirectory}/.config/niri/dms/alttab.kdl"
  '';

  home.file.".local/bin/goran-niri-shutdown" = {
    source = shutdown;
    executable = true;
  };
}

# Ubuntu owns the kernel, firmware, audio and networking. No NVIDIA assumptions.
{ config, lib, pkgs, snapdragonHpOs, snapdragonHpOsFonts, snapdragonDms, ... }:
let
  cfg = config.programs.hp-os-snapdragon;
  environment = ''
    if [[ -f "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh" ]]; then
      source "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh"
    fi
    export XDG_DATA_DIRS="$HOME/.local/share/flatpak/exports/share:$HOME/.nix-profile/share:''${XDG_DATA_DIRS:-/usr/local/share:/usr/share}:/var/lib/snapd/desktop"
    export PATH="$HOME/.nix-profile/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
    export XDG_SESSION_TYPE=wayland
    unset GBM_BACKEND __GLX_VENDOR_LIBRARY_NAME
  '';
  hpSession = pkgs.writeShellScriptBin "hp-os-session" ''
    ${environment}
    export HP_OS_PAM_SERVICE=hp-os-snapdragon
    exec ${snapdragonHpOs}/bin/hp-os session "$@"
  '';
  dmsSession = pkgs.writeShellScriptBin "snapdragon-dms-session" ''
    ${environment}
    export XDG_CURRENT_DESKTOP=niri
    exec ${pkgs.niri}/bin/niri --session --config ${config.xdg.configHome}/niri/snapdragon.kdl "$@"
  '';
in {
  options.programs.hp-os-snapdragon = {
    enable = lib.mkEnableOption "Ubuntu Snapdragon HP-OS and Niri/DMS sessions";
    device = lib.mkOption {
      type = lib.types.enum [ "generic" "hp-omnibook-ultra-14-kg0xxx" ];
      default = "generic";
      description = "Hardware identity for diagnostics; firmware remains Ubuntu-owned.";
    };
  };
  config = lib.mkIf cfg.enable {
    assertions = [{ assertion = pkgs.stdenv.hostPlatform.isAarch64; message = "The Snapdragon desktop requires aarch64-linux."; }];
    targets.genericLinux.enable = true;
    targets.genericLinux.gpu.enable = true;
    programs.home-manager.enable = true;
    fonts.fontconfig.enable = true;
    home.packages = [ (pkgs.callPackage ../../pkgs/nom-dashboard.nix {}) snapdragonHpOs snapdragonHpOsFonts snapdragonDms hpSession dmsSession pkgs.niri pkgs.xwayland-satellite pkgs.foot pkgs.brightnessctl pkgs.wireplumber ];
    xdg.configFile."hp-os/snapdragon-device".text = cfg.device + "\n";
    xdg.configFile."niri/snapdragon.kdl".text = ''
      input {
        keyboard { xkb {}; }
        touchpad { tap; natural-scroll; }
      }
      layout { gaps 8; default-column-width { proportion 0.5; }; }
      spawn-at-startup "${snapdragonDms}/bin/dms" "run"
      prefer-no-csd
      screenshot-path "~/Pictures/Screenshot-%Y-%m-%d-%H-%M-%S.png"
      binds {
        Mod+Return { spawn "${pkgs.foot}/bin/foot"; }
        Mod+D { spawn "${snapdragonDms}/bin/dms" "ipc" "call" "spotlight" "toggle"; }
        Mod+Q { close-window; }
        Mod+Left { focus-column-left; }
        Mod+Right { focus-column-right; }
        Mod+Up { focus-window-up; }
        Mod+Down { focus-window-down; }
        Mod+Shift+E { quit; }
        Mod+Space { toggle-window-floating; }
        XF86AudioRaiseVolume allow-when-locked=true { spawn "${pkgs.wireplumber}/bin/wpctl" "set-volume" "@DEFAULT_AUDIO_SINK@" "5%+"; }
        XF86AudioLowerVolume allow-when-locked=true { spawn "${pkgs.wireplumber}/bin/wpctl" "set-volume" "@DEFAULT_AUDIO_SINK@" "5%-"; }
        XF86AudioMute allow-when-locked=true { spawn "${pkgs.wireplumber}/bin/wpctl" "set-mute" "@DEFAULT_AUDIO_SINK@" "toggle"; }
        XF86MonBrightnessUp { spawn "${pkgs.brightnessctl}/bin/brightnessctl" "set" "5%+"; }
        XF86MonBrightnessDown { spawn "${pkgs.brightnessctl}/bin/brightnessctl" "set" "5%-"; }
      }
    '';
    xdg.configFile."xdg-desktop-portal/niri-portals.conf".text = ''
      [preferred]
      default=gnome;gtk
      org.freedesktop.impl.portal.FileChooser=gtk
      org.freedesktop.impl.portal.Secret=gnome-keyring
    '';
    xdg.configFile."xdg-desktop-portal/hp-os-portals.conf".text = ''
      [preferred]
      default=gnome;gtk
      org.freedesktop.impl.portal.FileChooser=gtk
      org.freedesktop.impl.portal.Secret=gnome-keyring
    '';
  };
}

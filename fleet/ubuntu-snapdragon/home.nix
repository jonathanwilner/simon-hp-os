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
  panelResume = pkgs.writeShellScriptBin "snapdragon-panel-resume" ''
    exec > >(${pkgs.systemd}/bin/systemd-cat -t snapdragon-panel-resume) 2>&1
    echo "Panel recovery requested: mode=''${1:-manual} socket=''${NIRI_SOCKET:-unset}"
    exec 9>"$XDG_RUNTIME_DIR/snapdragon-panel-resume.lock"
    ${pkgs.util-linux}/bin/flock -n 9 || { echo "Recovery already running"; exit 0; }
    # logind's resume signal can precede completion of compositor recovery.
    # Keep manual recovery immediate; give the automatic path time to settle.
    if [[ "''${1:-}" == --after-resume ]]; then
      ${pkgs.coreutils}/bin/sleep 3
    fi
    if ! ${pkgs.coreutils}/bin/timeout 5 ${pkgs.niri}/bin/niri msg action power-off-monitors; then
      echo "Panel power-off request failed"
      exit 1
    fi
    ${pkgs.coreutils}/bin/sleep 2
    if ! ${pkgs.coreutils}/bin/timeout 5 ${pkgs.niri}/bin/niri msg action power-on-monitors; then
      echo "Panel power-on request failed"
      exit 1
    fi
    echo "Panel power-cycle requests accepted; physical display acceptance remains separate"
  '';
  resumeWatcher = pkgs.writeShellScriptBin "snapdragon-resume-watch" ''
    exec > >(${pkgs.systemd}/bin/systemd-cat -t snapdragon-resume-watch) 2>&1
    exec 9>"$XDG_RUNTIME_DIR/snapdragon-resume-watch.lock"
    ${pkgs.util-linux}/bin/flock -n 9 || exit 0
    echo "Watching logind resume events: socket=''${NIRI_SOCKET:-unset}"
    exec ${pkgs.swayidle}/bin/swayidle -d -w after-resume "${panelResume}/bin/snapdragon-panel-resume --after-resume"
  '';
  hpSession = pkgs.writeShellScriptBin "hp-os-session" ''
    ${environment}
    export HP_OS_PAM_SERVICE=hp-os-snapdragon
    exec ${snapdragonHpOs}/bin/hp-os session "$@"
  '';
  dmsSession = pkgs.writeShellScriptBin "snapdragon-dms-session" ''
    ${environment}
    export GTK_IM_MODULE=fcitx
    export QT_IM_MODULE=fcitx
    export XMODIFIERS=@im=fcitx
    export XDG_CURRENT_DESKTOP=niri
    exec ${pkgs.niri}/bin/niri --session --config ${config.xdg.configHome}/niri/snapdragon.kdl "$@"
  '';
in {
  options.programs.hp-os-snapdragon = {
    enable = lib.mkEnableOption "Ubuntu Snapdragon HP-OS and Niri/DMS sessions";
    resumePanelRetrain = lib.mkEnableOption "OmniBook panel power cycle after resume";
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
    programs.dank-material-shell = {
      enable = true;
      package = snapdragonDms;
      # Niri starts DMS within its own session.
      systemd.enable = false;
      enableSystemMonitoring = true;
      enableVPN = true;
      enableDynamicTheming = true;
      enableCalendarEvents = true;
      enableClipboardPaste = true;
    };
    programs.hp-os-fleet.niri = {
      enable = true;
      hpOsPackage = snapdragonHpOs;
      dmsPackage = snapdragonDms;
      niriPackage = snapdragonHpOs.niri;
    };
    programs.hp-os-fleet.appearance = { enable = true; dmsPackage = snapdragonDms; };
    programs.hp-os-fleet.session.enable = true;
    programs.hp-os-fleet.session.searchIq.enable = true;
    programs.hp-os-fleet.session.inputMethod.enable = true;
    fonts.fontconfig.enable = true;
    home.packages = [ (pkgs.writeTextFile { name = "hp-os-ubuntu-account-check"; destination = "/bin/hp-os-ubuntu-account-check"; executable = true; text = builtins.readFile ./account-check.py; }) (pkgs.callPackage ../../pkgs/nom-dashboard.nix {}) snapdragonHpOs snapdragonHpOsFonts snapdragonDms hpSession dmsSession pkgs.niri pkgs.xwayland-satellite pkgs.foot pkgs.fuzzel pkgs.brightnessctl pkgs.wireplumber ] ++ lib.optionals cfg.resumePanelRetrain [ panelResume resumeWatcher ];
    # Preserve HP-OS's editable startup file and unrelated startup entries.
    home.activation.snapdragonSessionStartup = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      startup="$HOME/.config/hp-os/niri/config.d/50-startup.kdl"
      mkdir -p "$(dirname "$startup")"
      touch "$startup"
      ${pkgs.gnused}/bin/sed -i '/\/\/ snapdragon-panel-resume$/d' "$startup"
      ${pkgs.gnused}/bin/sed -i '/\/\/ snapdragon-launcher$/d' "$startup"
      ${pkgs.gnused}/bin/sed -i '/\/\/ fleet-session$/d' "$startup"
      printf '%s\n' 'spawn-at-startup "${config.programs.hp-os-fleet.session.package}/bin/hp-os-fleet-session-start" // fleet-session' >> "$startup"
      ${lib.optionalString cfg.resumePanelRetrain ''
        printf '%s\n' 'spawn-at-startup "${resumeWatcher}/bin/snapdragon-resume-watch" // snapdragon-panel-resume' >> "$startup"
      ''}
    '';
    xdg.configFile."hp-os/snapdragon-device".text = cfg.device + "\n";
    xdg.configFile."niri/snapdragon.kdl".text = ''
      input {
        keyboard { xkb {}; }
        touchpad { tap; natural-scroll; }
      }
      layout { gaps 8; default-column-width { proportion 0.5; }; }
      spawn-at-startup "${snapdragonDms}/bin/dms" "run"
      ${lib.optionalString cfg.resumePanelRetrain ''spawn-at-startup "${resumeWatcher}/bin/snapdragon-resume-watch"''}
      prefer-no-csd
      screenshot-path "~/Pictures/Screenshot-%Y-%m-%d-%H-%M-%S.png"
      spawn-at-startup "${config.programs.hp-os-fleet.session.package}/bin/hp-os-fleet-session-start"
      binds {
        ${config.programs.hp-os-fleet.niri.dmsBindings}
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

{ config, lib, pkgs, ... }:
let
  sunshine = import ./pkgs/foundation-sunshine.nix { inherit pkgs; };
  launch = pkgs.writeShellScript "hp-os-sunshine" ''
    export XDG_RUNTIME_DIR="/run/user/$(${pkgs.coreutils}/bin/id -u)"
    export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
    unset WAYLAND_DISPLAY
    for socket in "$XDG_RUNTIME_DIR"/wayland-*; do
      if [[ -S "$socket" ]] && ${pkgs.iproute2}/bin/ss -xl | ${pkgs.gnugrep}/bin/grep -qF -- "$socket"; then
        export WAYLAND_DISPLAY="''${socket##*/}"
        break
      fi
    done
    cd ${lib.escapeShellArg config.home.homeDirectory}
    if [[ -z "''${WAYLAND_DISPLAY:-}" ]]; then set -- capture=kms "$@"; fi
    exec /usr/local/libexec/hp-os-sunshine "$@"
  '';
  setup = pkgs.writeShellApplication {
    name = "hp-os-remote-access-setup";
    runtimeInputs = [ pkgs.tmux ];
    text = ''
      nom-tmux setup-simon-remote-access -- /usr/bin/sudo /usr/bin/bash ${./install-simon-system.sh} ${../../fleet/ubuntu-branding}/refresh-managed.sh
      exec tmux attach -t setup-simon-remote-access
    '';
  };
in {
  home.packages = [ setup sunshine pkgs.tailscale pkgs.openssh pkgs.mosh pkgs.waypipe pkgs.moonlight-qt pkgs.freerdp ];
  xdg.desktopEntries.hp-os-remote-access = {
    name = "Set Up Remote Access";
    comment = "Enable Sunshine, SSH, and an unenrolled Tailscale daemon";
    exec = "${pkgs.ghostty}/bin/ghostty -e ${setup}/bin/hp-os-remote-access-setup";
    icon = "preferences-desktop-remote-desktop";
    terminal = false;
    categories = [ "Settings" "Network" ];
  };
  xdg.configFile."hp-os/remote-access.json".text = builtins.toJSON {
    sunshine = "${sunshine}/bin/sunshine-${sunshine.version}";
    tailscaled = "${pkgs.tailscale}/bin/tailscaled";
  };
  home.activation.sunshineInitialConfig = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    directory=${lib.escapeShellArg "${config.xdg.configHome}/sunshine"}
    run mkdir -p "$directory"
    if [ ! -e "$directory/sunshine.conf" ]; then
      printf 'sunshine_name = HP-OS Simon\nupnp = disabled\nlocale = en\n' > "$directory/sunshine.conf"
      chmod 600 "$directory/sunshine.conf"
    fi
    if [ ! -e "$directory/apps.json" ]; then
      printf '%s\n' '{"env":{},"apps":[{"name":"Desktop","image-path":"desktop.png"}]}' > "$directory/apps.json"
      chmod 600 "$directory/apps.json"
    fi
  '';
  systemd.user.services.sunshine = {
    Unit = {
      Description = "Foundation Sunshine HP-OS streaming";
      After = [ "graphical-session.target" ];
      ConditionFileIsExecutable = "/usr/local/libexec/hp-os-sunshine";
    };
    Service = {
      ExecStart = launch;
      Environment = [ "PATH=%h/.nix-profile/bin:/usr/local/bin:/usr/bin:/bin" "XDG_SESSION_TYPE=wayland" ];
      Restart = "always";
      RestartSec = 5;
    };
    Install.WantedBy = [ "default.target" "goran-niri.target" ];
  };
}

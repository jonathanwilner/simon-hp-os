{ config, pkgs, lib, ... }:
let
  dashboard = pkgs.callPackage ../../pkgs/nom-dashboard.nix { };
  updater = pkgs.writeShellApplication {
    name = "simon-desktop-update";
    runtimeInputs = [ pkgs.bash pkgs.coreutils pkgs.git pkgs.nix pkgs.python3 pkgs.util-linux dashboard ];
    text = ''
      export HP_OS_FLEET_STATUS=${../../fleet/release/status.py}
      exec bash ${./update-desktop.sh} "$@"
    '';
  };
in {
  home.packages = [ updater dashboard pkgs.nix-output-monitor pkgs.tmux ];
  # Suppress only the interactive Ubuntu notifier in Simon's session. Ubuntu's
  # APT timers, unattended security maintenance and Snap updates remain enabled.
  xdg.configFile."autostart/update-notifier.desktop".text = ''
    [Desktop Entry]
    Type=Application
    Name=Update Notifier
    Hidden=true
  '';
  dconf.settings."com/ubuntu/update-notifier".no-show-notifications = true;
  xdg.desktopEntries.simon-updates = {
    name = "Update Applications";
    comment = "Apply the tested fleet release and update your Flatpak applications";
    exec = "${updater}/bin/simon-desktop-update --attach";
    icon = "system-software-update";
    terminal = true;
    categories = [ "System" "Settings" ];
  };
  xdg.desktopEntries.simon-update-status = {
    name = "Update Status";
    comment = "Show the desktop revision, application versions and Ubuntu update status";
    exec = "${updater}/bin/simon-desktop-update --status-window";
    icon = "system-software-update";
    terminal = true;
    categories = [ "System" "Settings" ];
  };
  home.activation.simonUpdateNotifier = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
    if [ -n "''${XDG_RUNTIME_DIR:-}" ] && [ -S "$XDG_RUNTIME_DIR/bus" ]; then
      if /usr/bin/systemctl --user is-active --quiet 'app-update\x2dnotifier@autostart.service'; then
        $DRY_RUN_CMD /usr/bin/systemctl --user stop 'app-update\x2dnotifier@autostart.service'
      fi
      $DRY_RUN_CMD /usr/bin/systemctl --user daemon-reload
    fi
  '';
  # An older installed updater can activate this generation before it knows
  # about boot/login integration. Run the versioned helper in that same update.
  home.activation.simonSharedBranding = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
    if [ -z "''${DRY_RUN_CMD:-}" ]; then
      branding_state="''${XDG_STATE_HOME:-${config.home.homeDirectory}/.local/state}/simon-desktop-update"
      mkdir -p "$branding_state"
      if /usr/bin/sudo /usr/bin/bash ${../../fleet/ubuntu-branding}/refresh-managed.sh simon; then
        rm -f "$branding_state/branding-pending"
      else
        printf '%s\n' 'Boot/login setup is incomplete. Check the update log, resolve its preflight, and run Update Applications again.' > "$branding_state/branding-pending"
        cat "$branding_state/branding-pending" >&2
      fi
    fi
  '';
  # Simon can add an authorized reporting destination later. No Jonathan SSH
  # account or dashboard upload identity is shipped in Simon's profile.
  xdg.configFile."nom-dashboard/reporting.env".text = ''
    export NOM_DASHBOARD_REMOTE=""
  '';
}

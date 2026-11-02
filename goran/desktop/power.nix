{ config, pkgs, lib, ... }:
let
  missingBatteryWarning = pkgs.writeShellScript "goran-battery-telemetry-warning" ''
    set -eu
    marker="''${XDG_RUNTIME_DIR}/goran-battery-telemetry-warning"
    for supply in /sys/class/power_supply/*; do
      [ -r "$supply/type" ] || continue
      [ "$(cat "$supply/type")" = Battery ] || continue
      if [ -r "$supply/scope" ] && [ "$(cat "$supply/scope")" = Device ]; then
        continue
      fi
      rm -f "$marker"
      exit 0
    done
    [ ! -e "$marker" ] || exit 0
    ${pkgs.libnotify}/bin/notify-send --urgency=critical --expire-time=0 \
      --app-name=Power "Battery monitoring unavailable" \
      "Linux cannot read this laptop's battery. Low-battery warnings and automatic suspend cannot work yet. Keep the charger connected until battery reporting is restored."
    touch "$marker"
  '';
in {
  systemd.user.services.goran-battery-telemetry-warning = {
    Unit = {
      Description = "Warn when firmware prevents laptop battery monitoring";
      After = [ "goran-niri.target" "dms.service" ];
      PartOf = [ "goran-niri.target" ];
    };
    Service = { Type = "oneshot"; ExecStart = missingBatteryWarning; };
  };
  systemd.user.timers.goran-battery-telemetry-warning = {
    Unit.PartOf = [ "goran-niri.target" ];
    Timer = { OnActiveSec = "15s"; OnUnitActiveSec = "1min"; };
    Install.WantedBy = [ "goran-niri.target" ];
  };

  home.activation.goranBatteryWarnings = lib.hm.dag.entryAfter [ "goranDmsSettingsInit" ] ''
    if [ -z "''${DRY_RUN_CMD:-}" ]; then
      settings="${config.xdg.configHome}/DankMaterialShell/settings.json"
      ${pkgs.jq}/bin/jq '. + {
        batteryNotifyLow: true, batteryNotifyCritical: true,
        batteryLowThreshold: 20, batteryCriticalThreshold: 10,
        batteryLowNotificationType: 1, batteryCriticalNotificationType: 1
      }' "$settings" > "$settings.tmp"
      mv "$settings.tmp" "$settings"
    fi
  '';
}

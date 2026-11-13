# HP-OS owns hotkey feedback; the retained DMS backend owns the CDE lock screen.
{ config, lib, pkgs, ... }:
let
  enabled = config.programs.hp-os-fleet.enable
    && lib.attrByPath [ "programs" "hp-os" "enable" ] false config
    && lib.attrByPath [ "programs" "hp-cde-lockscreen" "enable" ] false config;
  launcher = pkgs.writeShellScript "dms-hp-cde-run" (builtins.replaceStrings
    [ "chmod -R u+w \"$stage\"" ]
    [ ''chmod -R u+w "$stage"
if ! "$DMS_CDE_PYTHON" ${./disable-osd.py} "$stage"; then
  echo 'DMS OSD suppression failed for this revision; preserving lock-screen availability.' >&2
fi'' ]
    (builtins.readFile ../../goran/desktop/hp-cde-lockscreen/run.sh));
in {
  config = lib.mkIf enabled {
    xdg.dataFile."hp-cde-lockscreen/run".source = lib.mkForce launcher;
  };
}

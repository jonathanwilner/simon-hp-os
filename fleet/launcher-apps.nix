# Portable launcher applications observed on Goran. Use the consumer's native
# package set; NVIDIA overrides and host-specific launchers stay with the host.
{ config, lib, pkgs, ... }:
let
  defaults = pkgs.writeText "hp-os-fuzzel.ini" ''
    [main]
    font=HarmonyOS Sans,Noto Color Emoji:size=13
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
    terminal=${pkgs.ghostty}/bin/ghostty -e

    [colors]
    background=f1f3f5ff
    text=182431ff
    prompt=0a59f7ff
    placeholder=747c83ff
    input=182431ff
    match=0a59f7ff
    selection=0a59f7ff
    selection-text=ffffffff
    selection-match=ffffffff
    counter=747c83ff
    border=0a59f7ff

    [border]
    width=2
    radius=16
    selection-radius=8
  '';
in {
  config = lib.mkIf config.programs.hp-os-fleet.enable {
    home.packages = import ./launcher-packages.nix { inherit pkgs; };
    # Goran's theme service maintains its existing writable file. Seed the same
    # launcher appearance only for new accounts, without replacing user edits.
    home.activation.hpOsFleetLauncherDefaults = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      if [ ! -e "${config.xdg.configHome}/fuzzel/fuzzel.ini" ]; then
        $DRY_RUN_CMD ${pkgs.coreutils}/bin/install -Dm644 ${defaults} \
          "${config.xdg.configHome}/fuzzel/fuzzel.ini"
      fi
    '';
  };
}

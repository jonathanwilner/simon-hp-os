# Desktop session services shared by Ubuntu and NixOS consumers.
{ config, lib, pkgs, ... }:
let
  cfg = config.programs.hp-os-fleet.session;
  session = pkgs.writeShellApplication {
    name = "hp-os-fleet-session-start";
    runtimeInputs = [ pkgs.coreutils pkgs.util-linux pkgs.python3 pkgs.wl-clipboard pkgs.cliphist pkgs.wl-clip-persist pkgs.fcitx5 pkgs.dbus pkgs.systemd ];
    text = "export HP_OS_FLEET_POLKIT_AGENT=${pkgs.polkit_gnome}/libexec/polkit-gnome-authentication-agent-1\nexport HP_OS_FLEET_INPUT_METHOD=${if cfg.inputMethod.enable then "1" else "0"}\n" + builtins.readFile ./session-start.sh;
  };
in {
  imports = [ ./search-iq.nix ];
  options.programs.hp-os-fleet.session = {
    enable = lib.mkEnableOption "portable clipboard and input-method session services";
    inputMethod.enable = lib.mkEnableOption "Fcitx5 in sessions without an owned touch keyboard";
    package = lib.mkOption {
      type = lib.types.package;
      default = session;
      description = "Start from the compositor with its Wayland and D-Bus environment.";
    };
  };
  config = lib.mkIf (config.programs.hp-os-fleet.enable && cfg.enable) {
    home.packages = lib.optionals cfg.inputMethod.enable [ pkgs.fcitx5-rime ] ++ [ cfg.package pkgs.cliphist pkgs.wl-clip-persist pkgs.wf-recorder pkgs.wl-mirror pkgs.waypipe pkgs.noto-fonts-cjk-sans pkgs.noto-fonts-color-emoji pkgs.nerd-fonts.jetbrains-mono ];
  };
}

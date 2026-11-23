{ config, lib, pkgs, ... }:
let
  cfg = config.programs.hp-os-fleet.vysor;
  native = pkgs.stdenv.hostPlatform.system == "x86_64-linux";
  web = pkgs.writeShellScriptBin "vysor" ''
    exec ${pkgs.xdg-utils}/bin/xdg-open https://app.vysor.io/
  '';
  connectionLauncher = id: connection:
    if connection.type == "launcher" then connection.target else
    pkgs.writeShellScript "vysor-connect-${id}" (if connection.type == "share" then ''
      exec ${pkgs.xdg-utils}/bin/xdg-open ${lib.escapeShellArg connection.target}
    '' else ''
      set -eu
      ${pkgs.android-tools}/bin/adb connect ${lib.escapeShellArg connection.target}
      ${pkgs.android-tools}/bin/adb -s ${lib.escapeShellArg connection.target} get-state
      exec ${cfg.package}/bin/vysor
    '');
in {
  options.programs.hp-os-fleet.vysor = {
    enable = lib.mkEnableOption "Vysor on Linux fleet desktops" // {
      default = pkgs.stdenv.hostPlatform.isLinux;
    };
    package = lib.mkOption {
      type = lib.types.package;
      default = if native then pkgs.callPackage ./package.nix {} else web;
      description = "Vysor desktop client, or the official web app on Linux architectures without a native release.";
    };
    connections = lib.mkOption {
      type = lib.types.attrsOf (lib.types.submodule ({ name, ... }: {
        options = {
          label = lib.mkOption { type = lib.types.str; default = name; };
          type = lib.mkOption { type = lib.types.enum [ "share" "adb" "launcher" ]; };
          target = lib.mkOption {
            type = lib.types.str;
            description = "HTTPS share URL, Android ADB host:port, or absolute path to a host-defined executable with no arguments.";
          };
        };
      }));
      default = {};
      description = "Optional host-specific device launchers. Devices selected in Vysor remain user-managed.";
    };
  };
  config = lib.mkIf (config.programs.hp-os-fleet.enable && cfg.enable) {
    assertions = lib.mapAttrsToList (id: connection: {
      assertion = builtins.match "[A-Za-z0-9_-]+" id != null &&
        (if connection.type == "launcher" then builtins.match "/[A-Za-z0-9_./+-]+" connection.target != null
         else if connection.type == "share" then lib.hasPrefix "https://" connection.target
         else native && builtins.match "([[:alnum:]._-]+|[[][0-9a-fA-F:]+[]]):[0-9]+" connection.target != null);
      message = "Vysor connection '${id}' needs a launcher-safe id and an HTTPS share URL, native Linux ADB host:port, or absolute launcher path.";
    }) cfg.connections;
    home.packages = [ cfg.package ];
    xdg.desktopEntries = lib.optionalAttrs (!native) {
      vysor = { name = "Vysor"; exec = "${cfg.package}/bin/vysor"; categories = [ "Utility" ]; };
    } // lib.mapAttrs' (id: connection: lib.nameValuePair "vysor-connect-${id}" {
      name = connection.label;
      exec = toString (connectionLauncher id connection);
      categories = [ "Utility" "RemoteAccess" ];
    }) cfg.connections;
  };
}

{ config, lib, pkgs, ... }:
let
  python = pkgs.python3.withPackages (ps: [ ps.msal ]);
  mimeTypes = builtins.fromJSON (builtins.readFile ./mime-types.json);
  package = pkgs.writeShellApplication {
    name = "cloud-office-open";
    runtimeInputs = [ pkgs.libnotify ];
    text = ''exec ${python}/bin/python3 ${./opener.py} "$@"'';
  };
in {
  home.packages = [ package ];
  home.file.".local/bin/cloud-office-open".source = "${package}/bin/cloud-office-open";
  xdg.desktopEntries.cloud-office = {
    name = "Microsoft 365 Cloud Office";
    genericName = "Word, Excel and PowerPoint";
    exec = "${package}/bin/cloud-office-open %U";
    icon = "applications-office";
    terminal = false;
    categories = [ "Office" ];
    mimeType = mimeTypes;
  };
  xdg.mimeApps.enable = true;
  xdg.mimeApps.defaultApplications = lib.genAttrs mimeTypes (_: [ "cloud-office.desktop" ]);
}

{ pkgs, channel, package }:
let
  dist = if channel == "dev" then "unstable" else channel;
  launcher = pkgs.writeShellScript "google-chrome-${channel}-isolated" ''
    ${builtins.readFile ./launch.sh}
  '';
  command = pkgs.writeShellScript "google-chrome-${channel}" ''
    exec ${launcher} ${channel} ${package}/bin/google-chrome-${dist} "$@"
  '';
in pkgs.runCommand "google-chrome-${channel}-${package.version}" {
  inherit (package) version meta;
  passthru = { unwrapped = package; inherit channel; };
} ''
  mkdir -p $out/bin $out/share
  ln -s ${command} $out/bin/google-chrome-${channel}
  ${pkgs.lib.optionalString (dist != channel) "ln -s ${command} $out/bin/google-chrome-${dist}"}
  # Expose channel icons without registering vendor MIME handlers/defaults.
  ln -s ${package}/share/icons $out/share/icons
''

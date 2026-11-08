{ pkgs }:
let
  launcher = pkgs.writeShellScript "steam-arm64" (builtins.replaceStrings
    [ "@systemctl@" "@gpu@" "@python@" ]
    [ "${pkgs.systemd}/bin/systemctl" "${./gpu.py}" "${pkgs.python3}/bin/python3" ]
    (builtins.readFile ./steam-arm64.sh));
  desktop = pkgs.makeDesktopItem {
    name = "steam";
    desktopName = "Steam";
    comment = "Native ARM64 Steam beta";
    exec = "${launcher} %U";
    icon = "${./steam.png}";
    terminal = false;
    categories = [ "Game" "Network" ];
    mimeTypes = [ "x-scheme-handler/steam" "x-scheme-handler/steamlink" ];
    startupWMClass = "Steam";
  };
in pkgs.runCommand "hp-os-steam-arm64" {} ''
  mkdir -p "$out/bin" "$out/share/applications" "$out/share/hp-os-steam"
  cp -r ${./.}/* "$out/share/hp-os-steam/"
  ln -s ${launcher} "$out/bin/steam"
  cp ${desktop}/share/applications/steam.desktop "$out/share/applications/"
  for entry in bootstrap gpu-check; do
    cat > "$out/bin/hp-os-steam-$entry" <<EOF
#!${pkgs.bash}/bin/bash
exec /usr/bin/env bash "$out/share/hp-os-steam/$entry.sh" "\$@"
EOF
    chmod +x "$out/bin/hp-os-steam-$entry"
  done
''

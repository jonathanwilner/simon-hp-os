{ runtimeShell, runCommand, quickshell, omdrop, owly, controller, callPackage, python3 }:
let
  printingClient = callPackage ../printing/package.nix {};
  printingGui = callPackage ../printing/gui-package.nix { client = printingClient; };
in
runCommand "hp-os-omdrop-gui" {} ''
  mkdir -p "$out/share/omdrop" "$out/bin"
  cp -r ${./gui}/* "$out/share/omdrop/"
  chmod -R u+w "$out/share/omdrop"
  substituteInPlace "$out/share/omdrop/OmdropPanel.qml" \
    --replace-fail '@omdrop@' '${omdrop}' \
    --replace-fail '@owly@' '${owly}' \
    --replace-fail '@controller@' '${controller}' \
    --replace-fail '@printingGui@' '${printingGui}'
  cp ${./launcher.sh} "$out/bin/hp-os-omdrop"
  substituteInPlace "$out/bin/hp-os-omdrop" \
    --replace-fail '@shell@' '${runtimeShell}' \
    --replace-fail '@quickshell@' '${quickshell}/bin/quickshell' \
    --replace-fail '@panel@' "$out/share/omdrop"
  LAUNCHER_SOURCE=${./launcher.sh} BASH=${runtimeShell} ${python3}/bin/python3 ${./launcher-tests.py}
  chmod +x "$out/bin/hp-os-omdrop"
''

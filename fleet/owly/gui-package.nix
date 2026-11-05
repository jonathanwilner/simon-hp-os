{ runtimeShell, runCommand, quickshell, omdrop, owly, controller, callPackage }:
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
  cat > "$out/bin/hp-os-omdrop" <<SCRIPT
  #!${runtimeShell}
  export QT_QUICK_CONTROLS_STYLE=Basic
  if command -v hp-os >/dev/null 2>&1 && hp-os ipc hpos sharing 2>/dev/null; then
    exit 0
  fi
  if ${quickshell}/bin/quickshell ipc -p "$out/share/omdrop" call omdrop open 2>/dev/null; then
    exit 0
  fi
  exec ${quickshell}/bin/quickshell -p "$out/share/omdrop" --no-duplicate
  SCRIPT
  chmod +x "$out/bin/hp-os-omdrop"
''

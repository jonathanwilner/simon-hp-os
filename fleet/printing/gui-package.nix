{ runtimeShell, runCommand, quickshell, client }:
runCommand "hp-os-aware-print-gui" {} ''
  mkdir -p "$out/share/hp-os-printing" "$out/bin"
  cp -r ${./gui}/* "$out/share/hp-os-printing/"
  chmod -R u+w "$out/share/hp-os-printing"
  substituteInPlace "$out/share/hp-os-printing/PrintingPanel.qml" \
    --replace-fail '@client@' '${client}'
  cat > "$out/bin/hp-os-aware-print-gui" <<SCRIPT
  #!${runtimeShell}
  export QT_QUICK_CONTROLS_STYLE=Basic
  if command -v hp-os >/dev/null 2>&1 && hp-os ipc hpos printing 2>/dev/null; then
    exit 0
  fi
  if ${quickshell}/bin/quickshell ipc -p "$out/share/hp-os-printing" call printing open 2>/dev/null; then
    exit 0
  fi
  exec ${quickshell}/bin/quickshell -p "$out/share/hp-os-printing" --no-duplicate
  SCRIPT
  chmod +x "$out/bin/hp-os-aware-print-gui"
''

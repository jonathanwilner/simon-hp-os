{ writeShellScriptBin }:
writeShellScriptBin "hp-os-install-branding" ''
  exec /bin/bash ${./.}/install.sh "$@"
''

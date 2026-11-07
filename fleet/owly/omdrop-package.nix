# The GUI and receiver share the pinned upstream Rust command contract.
# Privileged hooks and the polkit entry point are immutable store paths.
{ lib, rustPlatform, fetchFromGitHub, callPackage, owlySource, makeWrapper
, bash, coreutils, gnugrep, iproute2, openssl, systemd, avahi, wl-clipboard
, runCommand, python3, libnotify }:
let
  radioHooks = (callPackage "${owlySource}/nix/package.nix" {}).overrideAttrs (_: {
    pname = "omdrop-owl-hooks";
    buildPhase = ''
      runHook preBuild
      cargo build --frozen --release -p omdrop-owl
      runHook postBuild
    '';
    installPhase = ''
      runHook preInstall
      install -Dm755 target/release/omdrop-owl $out/libexec/omdrop-owl
      mkdir -p $out/lib/omdrop/radio
      for hook in probe up tick down peers; do
        ln -s $out/libexec/omdrop-owl $out/lib/omdrop/radio/$hook
      done
      runHook postInstall
    '';
  });
  notificationAdapter = runCommand "hp-os-omdrop-notifications" {} ''
    mkdir -p $out/bin
    cp ${./notify.py} $out/bin/omarchy-notification-send
    substituteInPlace $out/bin/omarchy-notification-send \
      --replace-fail '#!/usr/bin/env python3' '#!${python3}/bin/python3' \
      --replace-fail '@notifySend@' '${libnotify}/bin/notify-send'
    chmod 755 $out/bin/omarchy-notification-send
  '';
  runtimePath = lib.makeBinPath [ notificationAdapter coreutils gnugrep iproute2 openssl systemd avahi wl-clipboard ];
  # pkexec must be the host's privileged executable. Ubuntu supplies it in
  # /usr/bin; NixOS supplies its setuid wrapper in /run/wrappers/bin.
  commandPath = "/run/wrappers/bin:/usr/bin:/usr/sbin:${runtimePath}";
in rustPlatform.buildRustPackage {
  pname = "omdrop";
  version = "0.18.7";
  src = fetchFromGitHub {
    owner = "netmojo-systems";
    repo = "omdrop-plugin";
    rev = "0ac99a8c469e67a3fd15934d985fe0de0cc8abb0";
    hash = "sha256-nGd0vdhb9mssHzUEw7Wx2woFbgNw2c2aH+EWULxOUkI=";
  };
  cargoRoot = "core";
  buildAndTestSubdir = "core";
  cargoHash = "sha256-fAZEBU7Uy4NTVY/Xp6IuU7yG+41ULFopY4j+z8iWaYw=";
  nativeBuildInputs = [ makeWrapper ];
  nativeCheckInputs = [ openssl ];
  postPatch = ''
    # Upstream's timeout fixture uses FHS /bin/sleep; Nix provides coreutils.
    substituteInPlace core/crates/omdrop-identity/src/op.rs \
      --replace-fail '"/bin/sleep"' '"${coreutils}/bin/sleep"'
    substituteInPlace core/crates/omdrop-cli/src/ctx.rs \
      --replace-fail '"/usr/lib/omdrop-core"' '"'"$out"'/lib/omdrop-core"' \
      --replace-fail '"/usr/lib/omdrop/radio"' '"${radioHooks}/lib/omdrop/radio"'
    # Home Manager owns the launcher and panel. Keep upstream setup limited
    # to receiver service, identity and user-selected receiver preferences.
    substituteInPlace core/crates/omdrop-cli/src/window.rs \
      --replace-fail 'if !plugin_packaged(&plugin) && link_command() {' 'if false && !plugin_packaged(&plugin) && link_command() {' \
      --replace-fail 'if link_plugin(&plugin) {' 'if false && link_plugin(&plugin) {' \
      --replace-fail 'if add_widget(&plugin) {' 'if false && add_widget(&plugin) {'
    substituteInPlace core/crates/omdrop-radio/src/ctx.rs \
      --replace-fail '"/usr/lib/omdrop/radio"' '"${radioHooks}/lib/omdrop/radio"' \
      --replace-fail '"/usr/bin/busctl"' '"${systemd}/bin/busctl"' \
      --replace-fail '"/usr/bin/avahi-set-host-name"' '"${avahi}/bin/avahi-set-host-name"' \
      --replace-fail '"/usr/bin:/usr/sbin"' '"${runtimePath}"'
    substituteInPlace core/crates/omdrop-radio/src/main.rs \
      --replace-fail '/usr/lib/omdrop-core/omdrop-radio' "$out/lib/omdrop-core/omdrop-radio"
    substituteInPlace core/packaging/org.omarchy.omdrop.radio.policy \
      --replace-fail '/usr/lib/omdrop-core/omdrop-radio' "$out/lib/omdrop-core/omdrop-radio"
    substituteInPlace share/airdrop-receiver.service \
      --replace-fail '[Service]' '[Service]
    Environment=PATH=${commandPath}'
  '';
  # Network-namespace integration tests require privileges the builder lacks.
  # Unit tests exercise parsing, identity validation and protocol boundaries.
  cargoTestFlags = [ "--workspace" "--lib" ];
  installPhase = ''
    runHook preInstall
    mkdir -p $out/lib/omdrop-core $out/share/omdrop/bin $out/bin
    for program in omdrop omdrop-radio omdrop-receiver omdrop-adv airdrop-send send-to-peer; do
      install -m755 target/*/release/$program $out/lib/omdrop-core/$program
    done
    cp manifest.json README.md $out/share/omdrop/
    cp -r share $out/share/omdrop/
    install -Dm644 core/packaging/org.omarchy.omdrop.radio.policy \
      $out/share/polkit-1/actions/org.omarchy.omdrop.radio.policy
    # argv[0] anchors upstream plugin discovery and systemd command generation.
    # Installation is declarative; upstream's mutable installer is not used.
    cat > $out/share/omdrop/bin/omdrop <<WRAPPER
    #!${bash}/bin/bash
    export PATH=${commandPath}:\$PATH
    export OMDROP_IMPLEMENTATION=rust
    # pkexec rejects inherited Nix shell paths absent from the host /etc/shells.
    # The Rust CLI does not need SHELL; let the host privilege helper use its defaults.
    unset SHELL
    if [[ \''${1:-} == install-core || \''${1:-} == install-driver ]]; then
      echo 'Omdrop and Owly are managed by the HP-OS Nix configuration.' >&2
      exit 2
    fi
    exec -a "$out/share/omdrop/bin/omdrop" "$out/lib/omdrop-core/omdrop" "\$@"
    WRAPPER
    chmod 755 $out/share/omdrop/bin/omdrop
    ln -s $out/share/omdrop/bin/omdrop $out/bin/omdrop
    runHook postInstall
  '';
  passthru = { inherit radioHooks notificationAdapter; coreVersion = "0.1.11"; };
  meta = {
    description = "Omdrop AirDrop sender and receiver with the Owly radio backend";
    homepage = "https://github.com/netmojo-systems/omdrop-plugin";
    license = lib.licenses.mit;
    platforms = [ "aarch64-linux" "x86_64-linux" ];
    mainProgram = "omdrop";
  };
}

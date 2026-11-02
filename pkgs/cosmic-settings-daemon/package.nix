{
  lib,
  fetchFromGitHub,
  runCommand,
  rustPlatform,
  stdenv,
  pop-gtk-theme,
  adw-gtk3,
  pkg-config,
  libpulseaudio,
  libinput,
  udev,
  openssl,
  nixosTests,
  nix-update-script,
  withBatterySounds ? true,
}:

rustPlatform.buildRustPackage (finalAttrs: let
  upstreamSrc = fetchFromGitHub {
    owner = "pop-os";
    repo = "cosmic-settings-daemon";
    tag = "epoch-${finalAttrs.version}";
    hash = "sha256-np1syOfFqL6eZpnlwNb8WOXB0oqSkxIshX0JiyDlN1A=";
  };
in {
  pname = "cosmic-settings-daemon";
  version = "1.0.8";

  src = runCommand "cosmic-settings-daemon-src-patched" {} ''
    cp -r ${upstreamSrc} "$out"
    chmod -R u+w "$out"
    cp ${./Cargo.lock.patched} "$out/Cargo.lock"
  '';

  # DMS uses only the configuration watcher API; COSMIC sessions keep full behavior.
  patches = [ ./config-only-mode.patch ];

  # Config-only sessions do not start the battery monitor. Avoid pulling the
  # legacy Pop GTK theme into those builds; newer nixpkgs has removed it.
  postPatch = lib.optionalString withBatterySounds ''
    substituteInPlace src/battery.rs \
      --replace-fail '/usr/share/sounds/Pop/' '${pop-gtk-theme}/share/sounds/Pop/'
  '' + ''
    substituteInPlace src/theme.rs \
      --replace-fail '/usr/share/themes/adw-gtk3' '${adw-gtk3}/share/themes/adw-gtk3'
  '';

  cargoHash = null;
  cargoLock = {
    lockFile = ./Cargo.lock.patched;
    allowBuiltinFetchGit = true;
  };

  nativeBuildInputs = [ pkg-config ];

  buildInputs = [
    libinput
    libpulseaudio
    openssl
    udev
  ];

  makeFlags = [
    "prefix=$(out)"
    "CARGO_TARGET_DIR=target/${stdenv.hostPlatform.rust.cargoShortTarget}"
  ];

  dontCargoInstall = true;

  passthru = {
    tests = {
      inherit (nixosTests)
        cosmic
        cosmic-autologin
        cosmic-noxwayland
        cosmic-autologin-noxwayland
        ;
    };

    updateScript = nix-update-script {
      extraArgs = [
        "--version-regex"
        "epoch-(.*)"
      ];
    };
  };

  meta = {
    homepage = "https://github.com/pop-os/cosmic-settings-daemon";
    description = "Settings Daemon for the COSMIC Desktop Environment";
    mainProgram = "cosmic-settings-daemon";
    license = lib.licenses.gpl3Only;
    teams = [ lib.teams.cosmic ];
    platforms = lib.platforms.linux;
  };
})

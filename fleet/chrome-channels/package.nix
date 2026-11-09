# Reuse nixpkgs' maintained binary patching and runtime dependencies.
{ lib, fetchurl, google-chrome, stdenv, channel, commandLineArgs ? "", withSymlink ? true, sources ? builtins.fromJSON (builtins.readFile ./sources.json) }:
let
  dist = if channel == "dev" then "unstable" else channel;
  appname = if channel == "stable" then "chrome" else "chrome-${dist}";
  release = sources.${channel};
  source = release.platforms.${stdenv.hostPlatform.system};
  upstream = google-chrome.override { inherit commandLineArgs withSymlink; };
in
upstream.overrideAttrs (old: {
  pname = "google-chrome-${dist}";
  version = source.version;
  src = fetchurl { inherit (source) url hash; };
  installPhase = builtins.replaceStrings
    [ "appname=chrome" "dist=stable" "com.google.Chrome.desktop" "patchelf --set-rpath $rpath $out/share/google/$appname/lib*GL*" ]
    [ "appname=${appname}" "dist=${dist}" (if channel == "stable" then "com.google.Chrome.desktop" else "com.google.Chrome.${dist}.desktop") "" ]
    old.installPhase;
  meta = old.meta // {
    platforms = [ "x86_64-linux" "aarch64-linux" ];
    mainProgram = "google-chrome-${dist}";
    description = "Google Chrome ${channel} (official Google Linux release)";
  };
  passthru = (old.passthru or {}) // {
    inherit channel;
    # Keep the original nixpkgs package when the overlay is imported twice.
    fleetChromeUpstream = google-chrome;
    updateScript = ./update.py;
  };
})

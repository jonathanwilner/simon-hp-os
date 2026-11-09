final: prev:
let
  raw = channel: final.callPackage ./package.nix { inherit channel; google-chrome = prev.google-chrome.fleetChromeUpstream or prev.google-chrome; withSymlink = channel == "stable"; };
  isolated = channel: import ./isolated.nix { pkgs = final; inherit channel; package = raw channel; };
in {
  google-chrome = raw "stable";
  google-chrome-stable = raw "stable";
  google-chrome-beta = isolated "beta";
  google-chrome-dev = isolated "dev";
  google-chrome-unstable = isolated "dev";
  google-chrome-canary = isolated "canary";
}

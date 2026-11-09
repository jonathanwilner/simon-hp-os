{ source, system }:
let
  fleet = builtins.getFlake source;
  overlay = fleet.overlays.chromeChannels;
  make = overlays: import fleet.inputs.nixpkgs { inherit system overlays; config.allowUnfree = true; };
  once = make [ overlay ];
  twice = make [ overlay overlay ];
  args = "--remote-debugging-port=9222 --remote-allow-origins=* --remote-debugging-address=127.0.0.1";
  configured = twice.google-chrome.override { commandLineArgs = args; withSymlink = false; };
  names = [ "google-chrome" "google-chrome-stable" "google-chrome-beta" "google-chrome-dev" "google-chrome-canary" ];
in assert configured.postInstall == "";
assert builtins.match ".*google-chrome-stable.*" twice.google-chrome.postInstall != null;
assert builtins.all (name: once.${name}.drvPath == twice.${name}.drvPath) names;
assert twice.google-chrome-beta.unwrapped.postInstall == "";
assert twice.google-chrome-dev.unwrapped.postInstall == "";
assert twice.google-chrome-canary.unwrapped.postInstall == "";
{
  inherit system;
  stableOverride = configured.drvPath;
  channelPaths = builtins.listToAttrs (map (name: { inherit name; value = twice.${name}.drvPath; }) names);
  originalVersion = twice.google-chrome.fleetChromeUpstream.version;
}

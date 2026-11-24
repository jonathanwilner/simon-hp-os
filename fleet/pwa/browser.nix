{ pkgs }:
let
  # Host wrappers retain their established profile and hardware configuration.
  # New fleet devices get native Chrome without Goran's NVIDIA-specific flags.
  browser = if (pkgs.google-chrome.channel or null) == "stable" then pkgs.google-chrome else pkgs.callPackage ../chrome-channels/package.nix {
    channel = "stable";
    google-chrome = pkgs.google-chrome;
  };
in pkgs.writeShellScript "hp-os-pwa-browser" ''
    if [ -x "$HOME/.local/bin/chrome-live-control" ]; then
      exec "$HOME/.local/bin/chrome-live-control" "$@"
    fi
    exec ${browser}/bin/google-chrome-stable \
      --ozone-platform=wayland \
      --remote-debugging-address=127.0.0.1 --remote-debugging-port=9222 \
      --user-data-dir="$HOME/.config/google-chrome-live-control" "$@"
  ''

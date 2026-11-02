{ pkgs }:
pkgs.writeShellScript "chrome-live-control" ''
  set -euo pipefail
  # Use the Nix VA-API driver with Nix Chrome. Ubuntu's driver depends on
  # libraries outside Chrome's Nix loader search path.
  export LIBVA_DRIVER_NAME=nvidia
  export LIBVA_DRIVERS_PATH=${pkgs.nvidia-vaapi-driver}/lib/dri
  export NVD_BACKEND=direct
  exec "$HOME/.nix-profile/bin/google-chrome" \
    --ozone-platform=wayland \
    --enable-features=AcceleratedVideoDecodeLinuxGL,VaapiOnNvidiaGPUs,VaapiIgnoreDriverChecks,PlatformHEVCDecoderSupport \
    --ignore-gpu-blocklist --use-gl=angle --use-angle=gl \
    --user-data-dir="$HOME/.config/google-chrome-live-control" \
    --remote-debugging-address=127.0.0.1 \
    --remote-debugging-port=9222 "$@"
''

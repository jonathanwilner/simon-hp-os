# Shared with Home Manager and NixOS environment.systemPackages so launchers
# work for every normal account. Never add personal data or hardware overrides.
{ pkgs, ghostty ? pkgs.ghostty }:
let
  cosmicFiles = pkgs.callPackage ./cosmic/files-package.nix { };
  moonlight = pkgs.callPackage ./pkgs/moonlight-qt-foundation { };
  openfreebudsCompatible = import ./pkgs/openfreebuds { inherit pkgs; };
in with pkgs; [
  # Prefer the shared release over legacy host lists that still include
  # Nixpkgs Ghostty. This also selects its matching desktop and D-Bus files.
  (lib.hiPrio ghostty) alacritty foot cosmic-term cosmicFiles fuzzel swaylock
  # Managed Emacs modules supply their own commands and desktop entries.
  # Keep the standalone editor as the lower-priority fleet fallback.
  (lib.lowPrio emacs-pgtk) (lib.lowPrio bluebubbles) kdePackages.kdeconnect-kde librepods openfreebudsCompatible
  networkmanagerapplet networkmanager_dmenu blueman
  pavucontrol easyeffects playerctl
  # The dock image-viewer entry uses Exec=gwenview; install its executable too.
  kdePackages.gwenview
  mpv celluloid vlc ffmpeg ffmpegthumbnailer
  simple-scan kdePackages.skanpage remmina moonlight obs-studio
  neovim vim yad ulauncher
  fcitx5 kdePackages.fcitx5-configtool
  wl-clipboard grim slurp libnotify desktop-file-utils xdg-utils
]

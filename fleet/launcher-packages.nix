# Shared with Home Manager and NixOS environment.systemPackages so launchers
# work for every normal account. Never add personal data or hardware overrides.
{ pkgs }:
let
  cosmicFiles = pkgs.symlinkJoin {
    name = "cosmic-files-gvfs";
    paths = [ pkgs.cosmic-files ];
    nativeBuildInputs = [ pkgs.makeWrapper ];
    postBuild = ''
      wrapProgram "$out/bin/cosmic-files" \
        --prefix GIO_EXTRA_MODULES : "${pkgs.gvfs}/lib/gio/modules"
    '';
  };
  moonlight = pkgs.callPackage ./pkgs/moonlight-qt-foundation { };
in with pkgs; [
  ghostty alacritty foot cosmic-term cosmicFiles fuzzel swaylock
  # Managed Emacs modules supply their own commands and desktop entries.
  # Keep the standalone editor as the lower-priority fleet fallback.
  (lib.lowPrio emacs-pgtk) bluebubbles kdePackages.kdeconnect-kde librepods openfreebuds
  networkmanagerapplet networkmanager_dmenu blueman
  pavucontrol easyeffects playerctl
  mpv celluloid vlc ffmpeg ffmpegthumbnailer
  simple-scan kdePackages.skanpage remmina moonlight obs-studio
  neovim vim yad ulauncher
  fcitx5 kdePackages.fcitx5-configtool
  wl-clipboard grim slurp libnotify desktop-file-utils xdg-utils
]

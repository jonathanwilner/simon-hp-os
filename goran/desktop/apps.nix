{ config, pkgs, lib, ... }:
{
  # Slazenger uses the Flathub BlueBubbles client. Flathub packages the
  # upstream ARM64 release; the Flutter application source is public. Ubuntu provides Flatpak's host
  # integration; Home Manager declares the user application and launcher.
  home.activation.goranBlueBubbles = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    if [ -x /usr/bin/flatpak ]; then
      # Flatpak is an Ubuntu binary. Keep Nix's GPG engine out of its PATH.
      $DRY_RUN_CMD ${pkgs.coreutils}/bin/env PATH=/usr/bin:/bin /usr/bin/flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
      $DRY_RUN_CMD ${pkgs.coreutils}/bin/env PATH=/usr/bin:/bin /usr/bin/flatpak install --user --noninteractive --or-update flathub app.bluebubbles.BlueBubbles
    fi
  '';

  home.file.".local/bin/bluebubbles-single" = {
    executable = true;
    text = ''
      #!/usr/bin/env bash
      set -euo pipefail
      case "''${1:-}" in
        "") ;;
        --recover-input)
          if /usr/bin/flatpak ps --columns=application | ${pkgs.gnugrep}/bin/grep -Fxq app.bluebubbles.BlueBubbles; then
            /usr/bin/flatpak kill app.bluebubbles.BlueBubbles
          fi
          ;;
        *) echo "Usage: bluebubbles-single [--recover-input]" >&2; exit 2 ;;
      esac
      # GTK activation restores a hidden tray window and focuses an existing one.
      # Avoid parsing Niri's versioned window JSON with a newer installed CLI.
      if [ "''${1:-}" != --recover-input ] && ${pkgs.systemd}/bin/busctl --user --timeout=3 call \
        app.bluebubbles.BlueBubbles /app/bluebubbles/BlueBubbles \
        org.freedesktop.Application Activate 'a{sv}' 0 >/dev/null 2>&1; then
        exit 0
      fi
      # Keep native GTK/Flutter diagnostics for the next intermittent failure.
      # Flatpak data and drafts stay in their existing application directory.
      umask 077
      state_dir="''${XDG_STATE_HOME:-$HOME/.local/state}/bluebubbles"
      ${pkgs.coreutils}/bin/mkdir -p "$state_dir"
      ${pkgs.coreutils}/bin/date -Is >> "$state_dir/launcher.log"
      exec /usr/bin/flatpak run app.bluebubbles.BlueBubbles >> "$state_dir/launcher.log" 2>&1
    '';
  };
  home.file.".local/bin/bluebubbles-recover-input" = {
    executable = true;
    text = ''
      #!/usr/bin/env bash
      exec "$HOME/.local/bin/bluebubbles-single" --recover-input
    '';
  };
  xdg.desktopEntries.bluebubbles = {
    name = "BlueBubbles";
    genericName = "iMessage client";
    exec = "${config.home.homeDirectory}/.local/bin/bluebubbles-single";
    icon = "app.bluebubbles.BlueBubbles";
    terminal = false;
    categories = [ "Network" "InstantMessaging" ];
    settings.StartupWMClass = "bluebubbles";
  };

  home.packages = with pkgs; [
    (callPackage ./depthscape/package.nix { })
    # Slazenger desktop and media baseline. Architecture-specific packages are
    # tracked separately in slazenger-software-inventory.md.
    ghostty alacritty foot fuzzel swaylock
    grim slurp wf-recorder wl-clipboard wl-clip-persist cliphist libnotify
    inotify-tools xclip xsel wl-mirror wayvnc waypipe
    pavucontrol easyeffects playerctl brightnessctl
    networkmanagerapplet blueman
    mpv celluloid vlc ffmpeg ffmpegthumbnailer imagemagick streamlink uxplay
    simple-scan kdePackages.skanpage remmina
    desktop-file-utils xdg-utils networkmanager_dmenu wofi ulauncher
    atuin neovim vim opencode chawan browserpass
    git gh ripgrep fd jq curl
    gnumake cmake clang libtool nodejs_22 typescript python3 uv
    typst pandoc
    nil nixd nixfmt tinymist texlab ghostscript
    msmtp oama gnupg pinentry-qt pass-wayland age
    cachix cloudflared sunwait dust
    usbutils pciutils lshw dmidecode texinfo yad dpkg
    mosh socat rsync dnsutils zip unzip
    obs-studio
    fcitx5 fcitx5-rime kdePackages.fcitx5-configtool
    hunspell hunspellDicts.en_US
    nerd-fonts.jetbrains-mono noto-fonts noto-fonts-cjk-sans
    noto-fonts-cjk-serif noto-fonts-color-emoji iosevka fira monaspace commit-mono
  ];

  fonts.fontconfig.enable = true;

  services.kdeconnect.enable = true;
  services.kdeconnect.indicator = true;

  systemd.user.services.fcitx5 = {
    Unit = {
      Description = "Fcitx5 input method in the Goran Niri session";
      PartOf = [ "goran-niri.target" ];
      After = [ "goran-niri.target" ];
    };
    Service = {
      ExecStart = "${pkgs.fcitx5}/bin/fcitx5 --replace";
      Restart = "on-failure";
      RestartSec = 2;
      Environment = [ "PATH=%h/.nix-profile/bin:/usr/local/bin:/usr/bin:/bin" ];
    };
    Install.WantedBy = [ "goran-niri.target" ];
  };

  systemd.user.services.wl-clip-persist = {
    Unit = {
      Description = "Persist the Wayland clipboard";
      PartOf = [ "goran-niri.target" ];
      After = [ "goran-niri.target" ];
    };
    Service = {
      ExecStart = "${pkgs.wl-clip-persist}/bin/wl-clip-persist --clipboard both --write-timeout 5000 --reconnect-tries INF";
      Restart = "on-failure";
      RestartSec = 2;
    };
    Install.WantedBy = [ "goran-niri.target" ];
  };

  programs.fish = {
    enable = true;
    shellAliases.e = "emacsclient";
  };
  programs.tmux = {
    enable = true;
    terminal = "tmux-256color";
    extraConfig = ''
      set -g default-shell "${pkgs.fish}/bin/fish"
      set -g mouse on
      set -g history-limit 50000
      set -g set-clipboard on
      set -as terminal-features ",xterm-ghostty:RGB"
    '';
  };
  programs.direnv = {
    enable = true;
    nix-direnv.enable = true;
  };

  home.sessionVariables.GIT_EDITOR = "emacsclient";
  xdg.mimeApps = {
    enable = true;
    defaultApplications = {
      "text/plain" = [ "emacs.desktop" ];
      "text/html" = [ "google-chrome.desktop" ];
      "x-scheme-handler/http" = [ "google-chrome.desktop" ];
      "x-scheme-handler/https" = [ "google-chrome.desktop" ];
      "x-scheme-handler/about" = [ "google-chrome.desktop" ];
      "x-scheme-handler/unknown" = [ "google-chrome.desktop" ];
      "video/mp4" = [ "io.github.celluloid_player.Celluloid.desktop" ];
      "video/x-matroska" = [ "io.github.celluloid_player.Celluloid.desktop" ];
      "video/webm" = [ "io.github.celluloid_player.Celluloid.desktop" ];
      "video/quicktime" = [ "io.github.celluloid_player.Celluloid.desktop" ];
      "video/x-msvideo" = [ "io.github.celluloid_player.Celluloid.desktop" ];
      "video/mpeg" = [ "io.github.celluloid_player.Celluloid.desktop" ];
      "video/mp2t" = [ "io.github.celluloid_player.Celluloid.desktop" ];
    };
  };
}

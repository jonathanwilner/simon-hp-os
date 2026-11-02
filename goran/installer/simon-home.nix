{ config, lib, pkgs, ... }:
{
  # Independent account. Reuse the desktop modules, without importing the
  # Jonathan mail, age, pairing, proxy or browser-account modules.
  home.username = "simon";
  home.homeDirectory = "/home/simon";
  home.stateVersion = "26.05";
  programs.home-manager.enable = true;
  programs.goran-hp-os.enable = true;

  targets.genericLinux.gpu = {
    enable = true;
    nvidia = {
      enable = true;
      version = "615.78.08";
      sha256 = "sha256-UHYBE1AYHoGgMfD9AS/jX+S+N8eCDWUft6qolK9Eejc=";
    };
  };
  home.packages = [
    pkgs.codex
    (pkgs.google-chrome.override { commandLineArgs = "--disable-setuid-sandbox"; })
  ];
  programs.emacs = {
    enable = true;
    package = pkgs.emacs-pgtk;
    extraConfig = builtins.readFile ../desktop/emacs-desktop-mode.el;
  };
  services.emacs.enable = true;

  home.file.".local/bin/chrome-live-control" = {
    source = import ../desktop/chrome-live-control.nix { inherit pkgs; };
    executable = true;
  };
  # The desktop VPN controls remain available for Simon's own enrollment.
  # No login state, SSH identity, mail credentials or pairing state is seeded.
  xdg.userDirs = {
    enable = true;
    createDirectories = true;
  };
  home.activation.simonDirectories = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    run ${pkgs.coreutils}/bin/mkdir -p ${lib.escapeShellArg "${config.home.homeDirectory}/src"}
  '';
}

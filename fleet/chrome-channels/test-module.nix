let
  flake = builtins.getFlake (toString ../..);
  evaluate = system:
    let
      pkgs = import flake.inputs.nixpkgs { inherit system; config.allowUnfree = true; overlays = [ (import ./overlay.nix) ]; };
      home = flake.inputs.home-manager.lib.homeManagerConfiguration {
        inherit pkgs;
        modules = [ ./home.nix {
          home.username = "test";
          home.homeDirectory = "/home/test";
          home.stateVersion = "26.05";
          programs.hp-os-fleet.chromeChannels.enable = true;
        } ];
      };
      cfg = home.config;
    in
    assert builtins.length cfg.home.packages >= 3;
    assert !(cfg.home.file ? ".local/bin/google-chrome-stable");
    assert cfg.home.file ? ".local/bin/google-chrome-beta";
    assert cfg.home.file ? ".local/bin/google-chrome-dev";
    assert cfg.home.file ? ".local/bin/google-chrome-canary";
    assert !(cfg.xdg.desktopEntries ? google-chrome);
    assert cfg.xdg.desktopEntries.google-chrome-beta.mimeType == null;
    assert (pkgs.google-chrome.override { commandLineArgs = "--disable-setuid-sandbox"; }).version == "157.0.8103.38";
    { versions = map (name: pkgs.${name}.version) [ "google-chrome" "google-chrome-beta" "google-chrome-dev" "google-chrome-canary" ];
      wrapper = cfg.home.file.".local/bin/google-chrome-dev".source;
    };
in { x86_64-linux = evaluate "x86_64-linux"; aarch64-linux = evaluate "aarch64-linux"; }

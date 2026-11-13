# Evaluate with nix eval --impure --json --file fleet/dms-compat/test-integration.nix
let
  flake = builtins.getFlake (toString ../..);
  lib = flake.inputs.nixpkgs.lib;
  check = system: flag: let
    pkgs = flake.inputs.nixpkgs.legacyPackages.${system};
    hm = flake.inputs.home-manager.lib.homeManagerConfiguration {
      inherit pkgs;
      modules = [
        flake.inputs.dank-material-shell.homeModules.dank-material-shell
        ../../goran/desktop/hp-cde-lockscreen/home.nix
        ./home.nix
        ({ lib, ... }: {
          options.programs.${flag}.enable = lib.mkEnableOption "test HP-OS";
          options.programs.hp-os-fleet.enable = lib.mkEnableOption "test fleet";
          config = {
            home.username = "test";
            home.homeDirectory = "/home/test";
            home.stateVersion = "25.11";
            programs.${flag}.enable = true;
            programs.hp-os-fleet.enable = true;
            programs.hp-cde-lockscreen.enable = true;
          };
        })
      ];
    };
    launcher = hm.config.xdg.dataFile."hp-cde-lockscreen/run".source;
  in assert lib.hasInfix "disable-osd.py" launcher.text;
     assert lib.hasInfix "dms-hp-cde-lock.py" launcher.text;
     assert lib.hasInfix "run --session" launcher.text;
     { inherit system flag; drvPath = launcher.drvPath; launcher = launcher.text; };
in lib.concatMap (system: map (check system) [ "hp-os" "goran-hp-os" ]) [ "x86_64-linux" "aarch64-linux" ]

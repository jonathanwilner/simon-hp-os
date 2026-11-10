{
  description = "HP-OS: a mobile-inspired desktop environment";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    inir = {
      url = "github:snowarch/iNiR/48cdcecb0f6089cfbb7019054602eab28e154b3b";
      flake = false;
    };
  };
  outputs = { self, nixpkgs, inir }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      each = nixpkgs.lib.genAttrs systems;
    in {
      packages = each (system: let
        pkgs = nixpkgs.legacyPackages.${system};
        package = pkgs.callPackage ./packaging/package.nix { inherit inir; };
      in { default = package; hp-os = package; niri = package.niri; niri-stock = package.niriStock; touch-support = package.touchSupport; hp-os-input-backend = package.touchBackend; });
      apps = each (system: {
        default = { type = "app"; program = "${self.packages.${system}.default}/bin/hp-os"; };
      });
      nixosModules.default = import ./packaging/nixos-module.nix self;
      homeManagerModules.default = import ./packaging/home-module.nix self;
      homeModules.default = self.homeManagerModules.default;
      checks = each (system: let pkgs = nixpkgs.legacyPackages.${system}; in {
        package = self.packages.${system}.default;
        touchController = pkgs.runCommand "hp-os-touch-policy-tests" { nativeBuildInputs = [ pkgs.python3 ]; } ''
          cp -r ${./touch/controller} controller
          chmod -R u+w controller
          cd controller
          python3 -m unittest -v
          touch "$out"
        '';
        touchQmlModels = pkgs.runCommand "hp-os-touch-qml-model-tests" { nativeBuildInputs = [ pkgs.nodejs pkgs.python3 ]; } ''
          cp -r ${./touch/qml} qml
          node qml/layouts.test.cjs
          python3 qml/preferences.test.py
          touch "$out"
        '';
        touchNiriConfig = pkgs.runCommand "hp-os-touch-niri-config-tests" {
          nativeBuildInputs = [ self.packages.${system}.niri pkgs.python3 ];
        } ''
          export HOME="$TMPDIR/home"
          mkdir -p "$HOME"
          cp -r ${./touch/controller} controller
          python3 - <<'PYTHON'
          import pathlib,sys
          sys.path.insert(0,'controller')
          import touch_support as t
          for mode in ('off','manual','tablet-only','always'):
              cfg={'enable':True,'keyboard':{'mode':mode,'backend':'hp-os-qml'},'gestures':{'enable':True,'keyboardEdge':True,'controlsEdge':True,'controlCenterCommand':['hp-os','ipc','hpos','controlCenter']}}
              pathlib.Path(mode+'.kdl').write_text(t.gesture_config(cfg,True))
          pathlib.Path('disabled.kdl').write_text(t.gesture_config({'enable':False},True))
          PYTHON
          for config in *.kdl; do niri validate --config "$config"; done
          touch "$out"
        '';
        touchDefaults = let
          defaults = profile: (pkgs.lib.evalModules { modules = [ ./packaging/touch-options.nix { programs.hp-os.touchSupport.profile = profile; } ]; }).config.programs.hp-os.touchSupport;
        in assert (defaults "laptop").keyboard.mode == "off";
           assert (defaults "convertible").keyboard.mode == "tablet-only";
           assert (defaults "tablet").keyboard.mode == "always";
           pkgs.writeText "hp-os-touch-defaults" (builtins.toJSON (defaults "laptop"));
        nixosModule = let
          evaluated = nixpkgs.lib.nixosSystem {
            inherit system;
            modules = [ self.nixosModules.default {
              programs.hp-os.enable = true;
              system.stateVersion = "26.05";
              boot.loader.grub.enable = false;
              fileSystems."/" = { device = "none"; fsType = "tmpfs"; };
            } ];
          };
          cfg = evaluated.config;
          failed = builtins.filter (a: !a.assertion) cfg.assertions;
        in assert failed == [];
          assert builtins.hasAttr "login" cfg.security.pam.services;
          pkgs.writeText "hp-os-module-evaluation.json" (builtins.toJSON {
            sessions = map (p: p.name) cfg.services.displayManager.sessionPackages;
            niri = cfg.programs.niri.package.version;
            pamService = "login";
            assertions = "PASS";
          });
        packaging = pkgs.runCommand "hp-os-packaging-tests" { nativeBuildInputs = [ pkgs.python3 pkgs.bash pkgs.coreutils pkgs.patch pkgs.nodejs ]; } ''
          export HOME="$TMPDIR/home"
          mkdir -p "$HOME"
          cp -r ${./.} source
          chmod -R u+w source
          python3 source/tests/test_packaging.py
          python3 source/tests/test_runtime_control.py
          python3 source/tests/test_brand_migration.py
          python3 source/tests/test_floating_all.py
          python3 source/tests/test_niri_bindings.py
          python3 source/tests/test_desktop_defaults.py
          python3 source/tests/test_files_profile.py
          python3 source/tests/test_recents.py
          python3 source/tests/test_unified_search.py
          HP_OS_UPSTREAM=${inir} python3 source/tests/test_wallpaper_startup.py
          HP_OS_UPSTREAM=${inir} python3 source/tests/test_hpos_contract.py
          touch "$out"
        '';
      });
    };
}

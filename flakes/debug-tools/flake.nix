{
  description = "Binary, Android, packet, and database inspection tools for Linux and macOS";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs =
    { self, nixpkgs }:
    let
      inherit (nixpkgs) lib;
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ];
      forSystems = lib.genAttrs systems;
      pkgsFor = forSystems (system: nixpkgs.legacyPackages.${system});
      toolsFor = forSystems (system: import ./packages.nix { pkgs = pkgsFor.${system}; });

      bundle =
        system: exclude:
        pkgsFor.${system}.symlinkJoin {
          name = "fleet-debug-tools";
          paths = lib.attrValues (removeAttrs toolsFor.${system} exclude);
        };

      module =
        installPath:
        {
          config,
          lib,
          pkgs,
          ...
        }:
        let
          cfg = config.programs.fleet-debug-tools;
          system = pkgs.stdenv.hostPlatform.system;
          supported = builtins.elem system systems;
        in
        {
          options.programs.fleet-debug-tools = {
            enable = lib.mkEnableOption "the fleet debugging tools";
            exclude = lib.mkOption {
              type = lib.types.listOf (lib.types.enum (builtins.attrNames toolsFor.x86_64-linux));
              default = [ ];
              example = [ "ghidra" ];
              description = "Tools to omit when the host already provides its own versions.";
            };
          };

          config = lib.mkIf cfg.enable (
            lib.mkMerge [
              {
                assertions = [
                  {
                    assertion = supported;
                    message = "fleet-debug-tools does not support ${system}. Supported systems: ${lib.concatStringsSep ", " systems}.";
                  }
                ];
              }
              (lib.mkIf supported (
                lib.setAttrByPath installPath [
                  (lib.lowPrio (
                    if cfg.exclude == [ ] then self.packages.${system}.default else bundle system cfg.exclude
                  ))
                ]
              ))
            ]
          );
        };
    in
    {
      packages = forSystems (system: toolsFor.${system} // { default = bundle system [ ]; });
      devShells = forSystems (system: {
        default = pkgsFor.${system}.mkShell { packages = [ self.packages.${system}.default ]; };
      });
      checks = forSystems (system: {
        smoke = pkgsFor.${system}.callPackage ./smoke.nix {
          inherit (self.packages.${system}) ghidra;
          inherit (self.packages.${system}.apktool) aapt;
          tools = self.packages.${system}.default;
        };
      });

      homeModules.default = module [
        "home"
        "packages"
      ];
      nixosModules.default = module [
        "environment"
        "systemPackages"
      ];

      formatter = forSystems (system: pkgsFor.${system}.nixfmt);
    };
}

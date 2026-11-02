{
  description = "Reversible HarmonyOS-inspired DankMaterialShell and Niri theme";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
      pkgsFor =
        system:
        import nixpkgs {
          inherit system;
          config.allowUnfree = true;
        };
    in
    {
      packages = forAllSystems (
        system:
        let
          pkgs = pkgsFor system;
        in
        {
          default = pkgs.callPackage ./package.nix { };
          harmonyos-dms-theme = self.packages.${system}.default;
        }
      );

      checks = forAllSystems (
        system:
        let
          pkgs = pkgsFor system;
          theme = self.packages.${system}.default;
        in
        {
          package = theme;
          content =
            pkgs.runCommand "harmonyos-dms-theme-content-check"
              {
                nativeBuildInputs = [
                  pkgs.fontconfig
                  pkgs.jq
                ];
              }
              ''
                set -euo pipefail
                jq -e '
                  (.dark | has("primary") and has("surface") and has("background")) and
                  (.light | has("primary") and has("surface") and has("background"))
                ' ${theme}/share/harmonyos-dms-theme/themes/harmonyos.json >/dev/null
                jq -e '.typography.body.medium == 14 and .shape.dialog == 16' \
                  ${theme}/share/harmonyos-dms-theme/tokens/harmonyos.json >/dev/null
                test "$(find ${theme}/share/fonts/truetype/harmonyos -type f -name 'HarmonyOS_Sans*.ttf' | wc -l)" -eq 11
                for font in ${theme}/share/fonts/truetype/harmonyos/HarmonyOS_Sans*.ttf; do
                  fc-scan "$font" >/dev/null
                done
                grep -Fq 'This theme software uses and bundles unmodified HarmonyOS Sans Fonts' \
                  ${theme}/share/doc/harmonyos-dms-theme/README.md
                test -s ${theme}/share/licenses/harmonyos-dms-theme/LICENSE_Fonts
                touch "$out"
              '';
        }
      );

      nixosModules.default = import ./modules/nixos.nix { inherit self; };
      nixosModules.harmonyos-dms-theme = self.nixosModules.default;
      homeManagerModules.default = import ./modules/home-manager.nix { inherit self; };
      homeManagerModules.harmonyos-dms-theme = self.homeManagerModules.default;
    };
}

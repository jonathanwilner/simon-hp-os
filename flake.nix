{
  description = "Simon HP-OS desktop for Ubuntu 26.04 ARM64";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    home-manager = { url = "github:nix-community/home-manager"; inputs.nixpkgs.follows = "nixpkgs"; };
    hp-os.url = "path:./vendor/HP-OSShell";
    codex-fleet = { url = "path:./vendor/codex-fleet"; inputs.nixpkgs.follows = "nixpkgs"; };
    ghostty-upstream.url = "github:ghostty-org/ghostty/ce787fc18a7782e81585beb63f0d905ccaf69284";
    dank-material-shell = { url = "github:AvengeMedia/DankMaterialShell/ef191babb72c83bf16254d3f9416e7b2e8ef61d6"; inputs.nixpkgs.follows = "nixpkgs"; };
    dms-plugin-registry = { url = "github:AvengeMedia/dms-plugin-registry/bd0adca992b502178e70cc015f2a34f2b7031186"; inputs.nixpkgs.follows = "nixpkgs"; };
    xwayland-satellite = { url = "github:Supreeeme/xwayland-satellite/8d135d3b2854b30fd01ea6cd6c27e523dd50a839"; inputs.nixpkgs.follows = "nixpkgs"; };
  };
  outputs = { nixpkgs, home-manager, hp-os, codex-fleet, ghostty-upstream, dank-material-shell, dms-plugin-registry, xwayland-satellite, ... }:
    let
      system = "aarch64-linux";
      ghosttyCpuPresentation = ghostty-upstream.packages.${system}.default.overrideAttrs (old: {
        patches = (old.patches or [ ]) ++ [ ./goran/desktop/ghostty-n1x-cpu-presentation.patch ];
      });
      pkgs = import nixpkgs {
        inherit system;
        config = { allowUnfree = true; nvidia.acceptLicense = true; };
        overlays = [
          (final: prev: { cloudflared = final.callPackage ./pkgs/cloudflared-release.nix { }; })
          codex-fleet.overlays.default
          (import ./goran/desktop/ghostty-overlay.nix { ghosttyPackage = ghosttyCpuPresentation; })
          (import ./goran/desktop/niri-hdr-overlay.nix)
        ];
      };
    in {
      packages.${system}.foundation-sunshine = import ./goran/remote-access/pkgs/foundation-sunshine.nix { inherit pkgs; };
      homeConfigurations.simon-daytona = home-manager.lib.homeManagerConfiguration {
        inherit pkgs;
        extraSpecialArgs = {
          inherit hp-os dank-material-shell dms-plugin-registry xwayland-satellite;
          n1xPersonalServices = false;
        };
        modules = [
          ./goran/installer/simon-home.nix
          ./goran/remote-access/simon.nix
          ./goran/installer/simon-apps.nix
          ./goran/installer/simon-update.nix
          ./goran/desktop/microsoft365-webapps.nix
          ./goran/desktop/cosmic-niri.nix
          ./goran/desktop/hp-os.nix
          ./goran/desktop/search-iq.nix
          ./goran/desktop/niri.nix
          ./goran/desktop/launchers.nix
          ./goran/desktop/dms.nix
          ./goran/desktop/power.nix
          ./goran/desktop/hp-os-theme.nix
          ./goran/desktop/apps.nix
          ./goran/headphones/home.nix
        ];
      };
    };
}

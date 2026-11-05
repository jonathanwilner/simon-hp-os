{
  description = "Simon HP-OS desktop for Ubuntu 26.04 ARM64";
  inputs = {
    owly = { url = "github:t4t5/owly/6f2e8ea99aed0687558d78a1dd49154ab3a5fa76"; inputs.nixpkgs.follows = "nixpkgs"; };
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    home-manager = { url = "github:nix-community/home-manager"; inputs.nixpkgs.follows = "nixpkgs"; };
    hp-os.url = "path:./vendor/HP-OSShell";
    codex-fleet = { url = "path:./vendor/codex-fleet"; inputs.nixpkgs.follows = "nixpkgs"; };
    ghostty-upstream.url = "github:ghostty-org/ghostty/ce787fc18a7782e81585beb63f0d905ccaf69284";
    dank-material-shell = { url = "github:AvengeMedia/DankMaterialShell/ef191babb72c83bf16254d3f9416e7b2e8ef61d6"; inputs.nixpkgs.follows = "nixpkgs"; };
    dms-plugin-registry = { url = "github:AvengeMedia/dms-plugin-registry/bd0adca992b502178e70cc015f2a34f2b7031186"; inputs.nixpkgs.follows = "nixpkgs"; };
    xwayland-satellite = { url = "github:Supreeeme/xwayland-satellite/8d135d3b2854b30fd01ea6cd6c27e523dd50a839"; inputs.nixpkgs.follows = "nixpkgs"; };
  };
  outputs = { owly, nixpkgs, home-manager, hp-os, codex-fleet, ghostty-upstream, dank-material-shell, dms-plugin-registry, xwayland-satellite, ... }:
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
      nixosConfigurations.hp-os-test = nixpkgs.lib.nixosSystem {
        system = "x86_64-linux";
        modules = [ (import ./tests/desktop-vm/configuration.nix { inherit hp-os home-manager owly; }) ];
      };
      homeModules.fleetApps = { imports = [ ./fleet/home.nix ]; _module.args.owlySource = owly; };
      homeManagerModules.default = { imports = [ ./fleet/home.nix ]; _module.args.owlySource = owly; };
      packages.x86_64-linux.hp-os-aware-radio = nixpkgs.legacyPackages.x86_64-linux.callPackage ./fleet/printing/radio.nix {};
      packages.aarch64-linux.hp-os-aware-radio = pkgs.callPackage ./fleet/printing/radio.nix {};
      packages.x86_64-linux.hp-os-aware-install-system = nixpkgs.legacyPackages.x86_64-linux.callPackage ./fleet/printing/ubuntu-system.nix {};
      packages.aarch64-linux.hp-os-aware-install-system = pkgs.callPackage ./fleet/printing/ubuntu-system.nix {};
      nixosModules.aware-printing = import ./fleet/printing/nixos.nix;
      packages.x86_64-linux.hp-os-aware-print-gui = nixpkgs.legacyPackages.x86_64-linux.callPackage ./fleet/printing/gui-package.nix {
        client = nixpkgs.legacyPackages.x86_64-linux.callPackage ./fleet/printing/package.nix {};
      };
      packages.aarch64-linux.hp-os-aware-print-gui = pkgs.callPackage ./fleet/printing/gui-package.nix {
        client = pkgs.callPackage ./fleet/printing/package.nix {};
      };
      packages.x86_64-linux.hp-os-aware-print = nixpkgs.legacyPackages.x86_64-linux.callPackage ./fleet/printing/package.nix {};
      packages.aarch64-linux.hp-os-aware-print = pkgs.callPackage ./fleet/printing/package.nix {};
      packages.x86_64-linux.hp-os-aware-supplicant = nixpkgs.legacyPackages.x86_64-linux.callPackage ./fleet/printing/supplicant.nix {};
      packages.aarch64-linux.hp-os-aware-supplicant = pkgs.callPackage ./fleet/printing/supplicant.nix {};
      nixosModules.owly = { lib, pkgs, ... }: {
        imports = [ owly.nixosModules.default ];
        services.owly.enable = lib.mkDefault true;
        environment.systemPackages = [ (pkgs.callPackage ./fleet/owly/omdrop-package.nix { owlySource = owly; }) ];
      };
      packages.x86_64-linux.omdrop = nixpkgs.legacyPackages.x86_64-linux.callPackage ./fleet/owly/omdrop-package.nix { owlySource = owly; };
      packages.aarch64-linux.omdrop = pkgs.callPackage ./fleet/owly/omdrop-package.nix { owlySource = owly; };
      packages.x86_64-linux.owly = nixpkgs.legacyPackages.x86_64-linux.callPackage "${owly}/nix/package.nix" {};
      packages.aarch64-linux.owly = pkgs.callPackage "${owly}/nix/package.nix" {};
      packages.x86_64-linux.omdrop-gui = let p = nixpkgs.legacyPackages.x86_64-linux; in p.callPackage ./fleet/owly/gui-package.nix { controller = p.callPackage ./fleet/owly/controller-package.nix { owly = p.callPackage "${owly}/nix/package.nix" {}; omdrop = p.callPackage ./fleet/owly/omdrop-package.nix { owlySource = owly; }; }; omdrop = p.callPackage ./fleet/owly/omdrop-package.nix { owlySource = owly; }; owly = p.callPackage "${owly}/nix/package.nix" {}; };
      packages.aarch64-linux.omdrop-gui = pkgs.callPackage ./fleet/owly/gui-package.nix { controller = pkgs.callPackage ./fleet/owly/controller-package.nix { owly = pkgs.callPackage "${owly}/nix/package.nix" {}; omdrop = pkgs.callPackage ./fleet/owly/omdrop-package.nix { owlySource = owly; }; }; omdrop = pkgs.callPackage ./fleet/owly/omdrop-package.nix { owlySource = owly; }; owly = pkgs.callPackage "${owly}/nix/package.nix" {}; };
      packages.x86_64-linux.owly-ubuntu-system = nixpkgs.legacyPackages.x86_64-linux.callPackage ./fleet/owly/ubuntu-system.nix { owlySource = owly; owly = nixpkgs.legacyPackages.x86_64-linux.callPackage "${owly}/nix/package.nix" {}; };
      packages.aarch64-linux.owly-ubuntu-system = pkgs.callPackage ./fleet/owly/ubuntu-system.nix { owlySource = owly; owly = pkgs.callPackage "${owly}/nix/package.nix" {}; };
      packages.x86_64-linux.upscayl = let p = import nixpkgs { system = "x86_64-linux"; config.allowUnfree = true; }; in p.callPackage ./goran/desktop/upscayl/package.nix {};
      packages.aarch64-linux.upscayl = pkgs.callPackage ./goran/desktop/upscayl/package.nix {};
      packages.x86_64-linux.hp-os-media-key = let p = import nixpkgs { system = "x86_64-linux"; }; in p.callPackage ./fleet/media-key-package.nix {};
      packages.aarch64-linux.hp-os-media-key = pkgs.callPackage ./fleet/media-key-package.nix {};
      packages.aarch64-linux.foundation-sunshine = import ./goran/remote-access/pkgs/foundation-sunshine.nix { inherit pkgs; };
      homeConfigurations.simon-daytona = home-manager.lib.homeManagerConfiguration {
        inherit pkgs;
        extraSpecialArgs = {
          owlySource = owly;
          inherit hp-os dank-material-shell dms-plugin-registry xwayland-satellite;
          n1xPersonalServices = false;
        };
        modules = [
          ./fleet/home.nix
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

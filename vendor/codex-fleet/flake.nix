{
  description = "Pinned Codex CLI packaging for the desktop";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    codex-desktop-linux = {
      url = "github:ilysenko/codex-desktop-linux";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      codex-desktop-linux,
    }:
    let
      lib = nixpkgs.lib;
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = lib.genAttrs systems;
      codexRevision = codex-desktop-linux.rev or (throw "codex-desktop-linux must be a locked Git input");
      bundledCliVersions = {
        "26.810.52044" = "0.148.0-alpha.9";
        "26.901.51231" = "0.153.4";
        "26.915.31945" = "0.155.0-alpha.9.2";
        "26.924.22138" = "0.158.0-alpha.2.1";
      };
      cliRelease = {
        version = "0.164.0";
        sources = {
          x86_64-linux = {
            url = "https://registry.npmjs.org/@openai/codex/-/codex-0.164.0-linux-x64.tgz";
            hash = "sha512-XLAoaWsGOT2khzl+P4FYDPTkzAr9W0VFXFaVkqlFdkM0soa1gH/4S0wSD57Ek3HHwkirAEGz2/Mwehseh+l5Mg==";
            platformTriple = "x86_64-unknown-linux-musl";
          };
          aarch64-linux = {
            url = "https://registry.npmjs.org/@openai/codex/-/codex-0.164.0-linux-arm64.tgz";
            hash = "sha512-LL5iTQjyDL4YRX44EWqhIfEQ5uGnmgxkQBJSxjZSeJ8L1Og83pdlzUJW/PRJ76oaVwOVgh6HXwuPEiBNEHU4lg==";
            platformTriple = "aarch64-unknown-linux-musl";
          };
        };
      };
      packagesFor =
        system:
        let
          pkgs = import nixpkgs {
            inherit system;
            config.allowUnfree = true;
          };
          codexDesktop = codex-desktop-linux.packages.${system}.codex-desktop;
          bundledCliVersion =
            bundledCliVersions.${codexDesktop.version}
              or (throw "codex-fleet has no CLI version mapping for desktop ${codexDesktop.version}");
          codexCli = pkgs.callPackage ./pkgs/codex-cli.nix {
            inherit codexDesktop bundledCliVersion;
            codexCliRelease = cliRelease.sources.${system} // {
              inherit (cliRelease) version;
            };
          };
          codexNodeRepl = pkgs.callPackage ./pkgs/codex-node-repl.nix {
            inherit codexDesktop;
          };
        in
        {
          default = codexCli;
          codex-cli = codexCli;
          codex-browser-use-node-repl = codexNodeRepl;
          codex-desktop = codexDesktop;
        };
    in
    {
      formatter = forAllSystems (system: nixpkgs.legacyPackages.${system}.nixfmt-rfc-style);

      packages = forAllSystems packagesFor;

      overlays.default = final: _prev: {
        codex = self.packages.${final.stdenv.hostPlatform.system}.codex-cli;
        codex-browser-use-node-repl =
          self.packages.${final.stdenv.hostPlatform.system}.codex-browser-use-node-repl;
      };

      homeManagerModules = codex-desktop-linux.homeManagerModules;
      nixosModules = codex-desktop-linux.nixosModules;

      checks = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          fleetPackages = self.packages.${system};
        in
        {
          codex-cli-layout =
            pkgs.runCommand "codex-cli-layout"
              {
                nativeBuildInputs = [ pkgs.python3 ];
              }
              ''
                python3 - ${fleetPackages.codex-cli} <<'PY'
                import json
                import pathlib
                import sys
                root = pathlib.Path(sys.argv[1])
                manifest = json.loads((root / "codex-package.json").read_text())
                assert manifest["layoutVersion"] == 1
                assert manifest["version"] == "${fleetPackages.codex-cli.version}"
                assert manifest["target"] == "${cliRelease.sources.${system}.platformTriple}"
                for path in [manifest["entrypoint"], "bin/codex-code-mode-host",
                             manifest["pathDir"] + "/rg",
                             manifest["resourcesDir"] + "/bwrap"]:
                    assert (root / path).is_file(), path
                    assert (root / path).stat().st_mode & 0o111, path
                PY
                touch "$out"
              '';
          codex-fleet-contract = pkgs.runCommand "codex-fleet-contract" { } ''
            test "$(${fleetPackages.codex-cli}/bin/codex --version)" = \
              'codex-cli ${fleetPackages.codex-cli.version}'
            test -x ${fleetPackages.codex-cli}/bin/codex-code-mode-host
            ${fleetPackages.codex-cli}/bin/codex-code-mode-host --help | \
              grep -Fq -- '--listen'
            test -x ${fleetPackages.codex-browser-use-node-repl}/bin/node_repl
            mkdir -p "$out"
            printf '%s\n' ${lib.escapeShellArg codexRevision} > "$out/revision"
            printf '%s\n' ${lib.escapeShellArg fleetPackages.codex-desktop.version} > "$out/desktop-version"
            printf '%s\n' ${lib.escapeShellArg fleetPackages.codex-cli.version} > "$out/cli-version"
          '';
        }
      );

      lib = {
        inherit codexRevision bundledCliVersions cliRelease;
        desktopVersion = self.packages.x86_64-linux.codex-desktop.version;
        cliVersion = self.packages.x86_64-linux.codex-cli.version;
      };
    };
}

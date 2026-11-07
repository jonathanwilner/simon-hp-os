{ nixpkgs, home-manager, owly, standaloneGui }:
let
  systems = [ "aarch64-linux" "x86_64-linux" ];
  configuration = system: automatic: autostart: home-manager.lib.homeManagerConfiguration {
    pkgs = import nixpkgs { inherit system; config.allowUnfree = true; };
    modules = [
      { imports = [ ../../fleet/home.nix ]; _module.args.owlySource = owly; }
      { home.username = "fleet-test"; home.homeDirectory = "/home/fleet-test"; home.stateVersion = "26.05"; }
      (if automatic == null then {} else { programs.hp-os-fleet.owly.automaticWifiSwitching = automatic; })
      (if autostart == null then {} else { programs.hp-os-fleet.owly.autostartReceiving = autostart; })
    ];
  };
  controllerFor = config: builtins.head (builtins.filter
    (p: (p.name or "") == "hp-os-omdrop-controller") config.config.home.packages);
  contract = system:
    let
      enabled = configuration system null null;
      disabled = configuration system false null;
      persistent = configuration system null true;
      p = enabled.pkgs;
      backend = p.callPackage ../../fleet/owly/omdrop-package.nix { owlySource = owly; };
      radio = p.callPackage "${owly}/nix/package.nix" {};
      expected = allowSteering: p.callPackage ../../fleet/owly/controller-package.nix {
        omdrop = backend; owly = radio; inherit allowSteering;
      };
      expectedGui = p.callPackage ../../fleet/owly/gui-package.nix {
        controller = expected true; omdrop = backend; owly = radio;
      };
    in assert (standaloneGui system).drvPath == expectedGui.drvPath;
       assert enabled.config.programs.hp-os-fleet.owly.automaticWifiSwitching;
       assert !disabled.config.programs.hp-os-fleet.owly.automaticWifiSwitching;
       assert !enabled.config.programs.hp-os-fleet.owly.autostartReceiving;
       assert !(enabled.config.systemd.user.services ? hp-os-omdrop-auto);
       assert persistent.config.programs.hp-os-fleet.owly.autostartReceiving;
       assert persistent.config.systemd.user.services.hp-os-omdrop-auto.Service.ExecStart == [ "${controllerFor persistent}/bin/hp-os-omdrop-controller automatic" ];
       assert persistent.config.systemd.user.services.hp-os-omdrop-auto.Service.Restart == "on-failure";
       assert persistent.config.systemd.user.services.hp-os-omdrop-auto.Install.WantedBy == [ "default.target" ];
       assert persistent.config.systemd.user.services.hp-os-omdrop-auto.Unit.PartOf == [ "default.target" ];
       assert (controllerFor enabled).drvPath == (expected true).drvPath;
       assert (controllerFor disabled).drvPath == (expected false).drvPath;
       { inherit system; defaultEnabled = true; optOutDisabled = true; packageWiringVerified = true; persistentReceivingOptInVerified = true; };
  contracts = builtins.map contract systems;
in builtins.listToAttrs (builtins.map (system:
  let
    p = nixpkgs.legacyPackages.${system};
    # These controller builds use the real renderer with harmless radio paths.
    # The module-to-package derivation comparisons above use real dependencies.
    rendered = allowSteering: p.callPackage ../../fleet/owly/controller-package.nix {
      omdrop = "/test/omdrop"; owly = "/test/owly"; inherit allowSteering;
    };
    omdrop = p.callPackage ../../fleet/owly/omdrop-package.nix { owlySource = owly; };
  in {
    name = system;
    value = {
      omdrop-fleet-contract = p.runCommand "omdrop-fleet-contract" { nativeBuildInputs = [ p.python3 p.bash p.nodejs ]; } ''
        cat > contracts.json <<'JSON'
        ${builtins.toJSON contracts}
        JSON
        BASH=${p.bash}/bin/bash LAUNCHER_SOURCE=${../../fleet/owly/launcher.sh} python3 ${../../fleet/owly/launcher-tests.py}
        RADIO_POLICY_SOURCE=${../../fleet/owly/radio-policy.rules} node --test ${../../fleet/owly/radio-policy-tests.cjs}
        python3 ${./rendered-controller.py} ${rendered true}/bin/hp-os-omdrop-controller true
        python3 ${./rendered-controller.py} ${rendered false}/bin/hp-os-omdrop-controller false
        mkdir -p "$out"
        cp contracts.json "$out/"
      '';
      omdrop-package-contract = p.runCommand "omdrop-package-contract" { nativeBuildInputs = [ p.python3 p.bash ]; } ''
        python3 ${./installed-wrapper.py} ${omdrop}
        touch "$out"
      '';
    };
  }) systems)

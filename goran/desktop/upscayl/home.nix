{ config, lib, pkgs, ... }:
let
  app = pkgs.callPackage ./package.nix { };
  sandboxPolicy = pkgs.writeText "upscayl-electron.apparmor" ''
    abi <abi/5.0>,
    include <tunables/global>
    # Permit the pinned Electron runtime to create its user namespace sandbox.
    profile upscayl-electron ${pkgs.electron.unwrapped}/libexec/electron/electron flags=(unconfined) {
      userns,
      @{exec_path} mr,
    }
  '';
in {
 config = lib.mkIf (config.programs.hp-os-fleet.enable && config.programs.hp-os-fleet.upscayl.enable && pkgs.stdenv.hostPlatform.isLinux) {
  home.packages = [ app ];
  home.activation.upscaylSandbox = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    if [[ -x /usr/sbin/apparmor_parser && -d /sys/module/apparmor ]] \
      && ! ${pkgs.diffutils}/bin/cmp -s ${sandboxPolicy} /etc/apparmor.d/upscayl-electron; then
      run /usr/bin/sudo -n /usr/bin/install -m 0644 ${sandboxPolicy} /etc/apparmor.d/upscayl-electron
      run /usr/bin/sudo -n /usr/sbin/apparmor_parser -r /etc/apparmor.d/upscayl-electron
    fi
  '';
 };
}

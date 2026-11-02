{ pkgs, lib, ... }:
let
  bundle = import ./package.nix { inherit pkgs; };
in {
  home.activation.goranHeadphones = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    $DRY_RUN_CMD ${pkgs.bash}/bin/bash ${./install.sh} ${bundle}
  '';
}

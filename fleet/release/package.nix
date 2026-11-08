{ lib, stdenvNoCC, makeWrapper, python3, git, gh, nix, coreutils, iproute2, tmux, callPackage }:
let dashboard = callPackage ../../pkgs/nom-dashboard.nix {};
in stdenvNoCC.mkDerivation {
  pname = "hp-os-fleet-release";
  version = "1";
  src = ./.;
  nativeBuildInputs = [ makeWrapper ];
  installPhase = ''
    mkdir -p $out/lib $out/bin
    cp *.py $out/lib/
    for entry in status publish consumers canary controller report; do
      makeWrapper ${python3}/bin/python3 $out/bin/fleet-$entry \
        --add-flags $out/lib/$entry.py \
        --prefix PATH : ${lib.makeBinPath [ git gh nix coreutils iproute2 tmux dashboard ]}
    done
  '';
}

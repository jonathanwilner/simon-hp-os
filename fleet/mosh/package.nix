{ lib, writeShellApplication, python3, mosh, openssh }:
writeShellApplication {
  name = "fleet-mosh";
  runtimeInputs = [ python3 mosh openssh ];
  text = ''
    export FLEET_MOSH_BINARY=${lib.getExe mosh}
    exec python3 ${./client.py} "$@"
  '';
}

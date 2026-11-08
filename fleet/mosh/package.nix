{ lib, symlinkJoin, writeShellApplication, writeShellScriptBin, python3, mosh, openssh }:
let
  client = writeShellApplication {
    name = "fleet-mosh";
    runtimeInputs = [ python3 mosh openssh ];
    text = ''
      export FLEET_MOSH_BINARY=${lib.getExe mosh}
      exec python3 ${./client.py} "$@"
    '';
  };
  server = writeShellScriptBin "fleet-mosh-server" ''
    export MOSH_SERVER_NETWORK_TMOUT=604800
    exec ${mosh}/bin/mosh-server "$@"
  '';
in symlinkJoin {
  name = "fleet-mosh";
  paths = [ client server ];
  meta.mainProgram = "fleet-mosh";
}

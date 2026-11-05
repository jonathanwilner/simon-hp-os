{ lib, runCommand, python3, makeWrapper }:
runCommand "hp-os-aware-print" {
  nativeBuildInputs = [ makeWrapper ];
  meta = {
    description = "Wi-Fi Aware IPP printing client";
    platforms = lib.platforms.linux;
    mainProgram = "hp-os-aware-print";
  };
} ''
  mkdir -p $out/libexec $out/bin
  cp ${./controller.py} $out/libexec/aware-print.py
  makeWrapper ${python3}/bin/python3 $out/bin/hp-os-aware-print \
    --add-flags "$out/libexec/aware-print.py"
  cp ${./test_controller.py} test_controller.py
  cp ${./controller.py} controller.py
  ${python3}/bin/python3 -m unittest -v test_controller
''

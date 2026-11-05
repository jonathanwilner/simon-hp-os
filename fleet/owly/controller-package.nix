{ runCommand, python3, omdrop, owly, allowSteering ? false }:
runCommand "hp-os-omdrop-controller" {} ''
  mkdir -p $out/bin
  cp ${./controller.py} $out/bin/hp-os-omdrop-controller
  substituteInPlace $out/bin/hp-os-omdrop-controller \
    --replace-fail '#!/usr/bin/env python3' '#!${python3}/bin/python3' \
    --replace-fail '@omdrop@' '${omdrop}' \
    --replace-fail '@allowSteering@' '${if allowSteering then "true" else "false"}' \
    --replace-fail '@owly@' '${owly}' \
    --replace-fail '@out@' "$out"
  CONTROLLER_SOURCE=$out/bin/hp-os-omdrop-controller ${python3}/bin/python3 ${./controller-tests.py}
  chmod 755 $out/bin/hp-os-omdrop-controller
  ${python3}/bin/python3 -c "import ast; ast.parse(open('$out/bin/hp-os-omdrop-controller').read())"
''

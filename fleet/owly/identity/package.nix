{ runCommand, python3, makeWrapper, openssl, libnotify, omdrop }:
runCommand "hp-os-omdrop-identity" { nativeBuildInputs = [ makeWrapper ]; } ''
  mkdir -p "$out/bin" "$out/lib/omdrop-identity/upstream/bin" "$out/lib/omdrop-identity/upstream/share/certs" "$out/share/omdrop-identity"
  cp ${omdrop.src}/bin/{identity.py,contacts.py,safeplist.py} "$out/lib/omdrop-identity/upstream/bin/"
  cp -r ${omdrop.src}/bin/apple-ca "$out/lib/omdrop-identity/upstream/bin/"
  cp ${omdrop.src}/share/certs/apple_root_ca.pem "$out/lib/omdrop-identity/upstream/share/certs/"
  cp ${omdrop.src}/LICENSE "$out/lib/omdrop-identity/upstream/LICENSE"
  cp -r ${./mac-helper} "$out/share/omdrop-identity/mac-helper"
  cp ${./README.md} "$out/share/omdrop-identity/README.md"
  cp ${./identity_setup.py} "$out/lib/omdrop-identity/setup.py"
  substituteInPlace "$out/lib/omdrop-identity/setup.py" \
    --replace-fail '@upstream@' "$out/lib/omdrop-identity/upstream" \
    --replace-fail '@omdrop@' '${omdrop}' \
    --replace-fail '@helper@' "$out/share/omdrop-identity/mac-helper"
  makeWrapper ${python3}/bin/python3 "$out/bin/hp-os-omdrop-identity" \
    --add-flags "$out/lib/omdrop-identity/setup.py" \
    --prefix PATH : '${openssl}/bin:${libnotify}/bin'
  cp ${./identity_setup.py} identity_setup.py
  cp ${./test_identity_setup.py} test_identity_setup.py
  PYTHONDONTWRITEBYTECODE=1 ${python3}/bin/python3 test_identity_setup.py
  ${python3}/bin/python3 -m py_compile "$out/lib/omdrop-identity/setup.py"
''

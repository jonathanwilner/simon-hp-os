{ pkgs }:
# Nixpkgs 0.17.1 predates Pillow 12. Its image API usage remains compatible;
# retain every other runtime constraint and test its actual image operations.
pkgs.openfreebuds.overridePythonAttrs (old: {
  doInstallCheck = true;
  postInstallCheck = (old.postInstallCheck or "") + ''
    QT_QPA_PLATFORM=offscreen PYTHONPATH="$PWD:$PYTHONPATH" python ${./test_pillow.py}
  '';
  pythonRelaxDeps = if (old.pythonRelaxDeps or false) == true then true
    else (old.pythonRelaxDeps or [ ]) ++ [ "pillow" ];
})

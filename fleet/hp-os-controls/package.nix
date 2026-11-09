# Opt-in package adaptation; leaves gesture policy, keyboard and PAM untouched.
{ hpOs }:
let
  niri = hpOs.niri.overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [ ../../goran/desktop/niri-long-press.patch ];
  });
  touchSupport = hpOs.touchSupport.override { inherit niri; };
in hpOs.overrideAttrs (old: {
  passthru = old.passthru // { inherit niri touchSupport; };
  postFixup = (old.postFixup or "") + ''
    for tool in touch-support hp-os-keyboard; do
      ln -sfn ${touchSupport}/bin/$tool "$out/bin/$tool"
    done
    substituteInPlace "$out/bin/hp-os" \
      --replace-fail '${hpOs.touchSupport}' '${touchSupport}'
    substituteInPlace "$out/bin/hp-os" "$out/bin/hp-os-toggle-floating-all" \
      --replace-fail '${hpOs.niri}' '${niri}'
  '';
})

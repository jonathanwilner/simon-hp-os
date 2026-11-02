# Goran's HDR panel requires the experimental color-management implementation.
# Keep both forks pinned together: upstream niri does not yet support HDR.
final: prev:
let
  niriRevision = "1bfaa833dce073d53d9db72c2c12a77f452864eb";
  smithayRevision = "064e3066ea377ef8c628323031e5eb4632819c97";
  niriSource = prev.fetchFromGitHub {
    owner = "losnoco";
    repo = "niri";
    rev = niriRevision;
    hash = "sha256-ICejOlb0pV71S2rc+TGRLAF8xZIrnbxikrBbRq2DEws=";
  };
  smithaySource = prev.fetchFromGitHub {
    owner = "losnoco";
    repo = "smithay";
    rev = smithayRevision;
    hash = "sha256-hteyKrqUZwtMUWhh2h6BMHL9RSK4bLvbSpNgdeiyBCA=";
  };
  # The fork uses sibling path dependencies. Put them inside one immutable
  # source tree so Cargo vendor and the sandbox see the same pinned inputs.
  source = prev.runCommand "niri-hdr-source-${builtins.substring 0 8 niriRevision}" { } ''
    cp -R ${niriSource} "$out"
    chmod -R u+w "$out"
    cp -R ${smithaySource} "$out/smithay"
    substituteInPlace "$out/Cargo.toml" \
      --replace-fail 'path = "../smithay"' 'path = "smithay"' \
      --replace-fail 'path = "../smithay/smithay-drm-extras"' 'path = "smithay/smithay-drm-extras"'
  '';
in {
  niri = prev.niri.overrideAttrs (old: {
    version = "26.4.0-hdr-touch-${builtins.substring 0 8 niriRevision}";
    src = source;
    patches = (old.patches or [ ]) ++ [ ./niri-displayid-hdr.patch ./niri-hdr-touch.patch ./niri-long-press-hdr.patch ];
    postPatch = (old.postPatch or "") + ''
      cp ${./niri-displayid-hdr.rs} src/backend/displayid_hdr.rs
      cp ${./samsung-sdc4257.edid} src/backend/samsung-sdc4257.edid
    '';
    cargoDeps = prev.rustPlatform.fetchCargoVendor {
      src = source;
      hash = "sha256-SDn6PghO/vFlcl8BKuEOvDy17DKZI5pxhsw8b7Ospaw=";
    };
    nativeBuildInputs = old.nativeBuildInputs ++ [ prev.cmake ];
    buildInputs = old.buildInputs ++ [ prev.shaderc prev.vulkan-loader ];
    env = old.env // {
      NIRI_BUILD_COMMIT = "goran-hdr-${builtins.substring 0 8 niriRevision}";
      SHADERC_LIB_DIR = "${prev.shaderc.lib}/lib";
    };
    # The fork's displayed version includes its own revision label.
    doInstallCheck = false;
    passthru = old.passthru // {
      inherit niriRevision smithayRevision;
    };
  });
}

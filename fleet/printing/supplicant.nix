{ wpa_supplicant, fetchgit }:
# Standalone NAN daemon. Never substitute this for NetworkManager's supplicant.
wpa_supplicant.overrideAttrs (old: {
  pname = "hp-os-aware-supplicant";
  version = "unstable-2026-11-05";
  src = fetchgit {
    url = "https://git.w1.fi/hostap.git";
    rev = "2ea78bb9af5f27250f97eda04d429d87bd88705f";
    hash = "sha256-s3JxaHJI7JgEVCuWmO+7EwFXOxbrIW1xjsiS2H4d2JU=";
  };
  patches = [];
  extraConfig = old.extraConfig + ''
    CONFIG_NAN=y
    CONFIG_NAN_USD=y
    CONFIG_PASN=y
  '';
  # Git source does not carry release-generated man pages.
  postInstall = ''
    install -Dm444 wpa_supplicant.conf $out/share/doc/wpa_supplicant/wpa_supplicant.conf.example
  '';
  passthru = {};
})

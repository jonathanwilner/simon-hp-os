{
  lib,
  rustPlatform,
  fetchFromGitHub,
  pkg-config,
  openssl,
  onnxruntime,
  makeWrapper,
  curl,
}:

rustPlatform.buildRustPackage {
  pname = "depthscape-engine";
  version = "0.1.0-unstable-2026-10-04";

  src = fetchFromGitHub {
    owner = "Tz-slayer";
    repo = "depthscape";
    rev = "6384aed7e1dbbb09dac1c3a95376eb8cc7aa1821";
    hash = "sha256-18MCcaqlYZAJSN7mQjBObB+j4FDZyeQ8Pr1+qRjrzg0=";
  };
  cargoRoot = "engine";
  buildAndTestSubdir = "engine";
  cargoHash = "sha256-rkNnmrhwjau1H3SNk12vH/EDEf0KNsO0tzPiBTlg20c=";

  nativeBuildInputs = [
    pkg-config
    makeWrapper
  ];
  buildInputs = [
    openssl
    onnxruntime
  ];
  env = {
    OPENSSL_NO_VENDOR = "true";
    # ort rc.13's default API level is 27, matching the locked ONNX Runtime.
    # Link the Nix library and keep the build independent of binary downloads.
    ORT_LIB_PATH = "${lib.getLib onnxruntime}/lib";
    ORT_PREFER_DYNAMIC_LINK = "1";
    ORT_SKIP_DOWNLOAD = "1";
  };

  postFixup = ''
    wrapProgram "$out/bin/depthscape-engine" --prefix PATH : ${lib.makeBinPath [ curl ]}
  '';

  meta = {
    description = "Local depth estimation and wallpaper occlusion masks for DMS";
    homepage = "https://github.com/Tz-slayer/depthscape";
    license = lib.licenses.mit;
    mainProgram = "depthscape-engine";
    platforms = lib.platforms.linux;
  };
}

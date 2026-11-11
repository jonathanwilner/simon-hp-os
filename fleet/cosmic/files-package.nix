{ lib, cosmic-files, gvfs, symlinkJoin, makeWrapper, runCommand, python3, patch, rustc }:
let
  # Patch the already pinned vendor tree, keeping the upstream source and lock
  # hashes unchanged. Only the trash crate is writable; other crates stay links.
  patchedVendor = runCommand "${cosmic-files.name}-vendor-remote-trash" {
    nativeBuildInputs = [ python3 patch ];
  } ''
    mkdir -p "$out"
    cp -rs ${cosmic-files.cargoDeps}/. "$out/"
    find "$out" -type d -exec chmod u+w {} +
    python3 ${./patch-trash-vendor.py} "$out" ${./trash-network-discovery.patch} ${./remote-trash-mount.rs}
  '';
  patchedFiles = cosmic-files.overrideAttrs (old: {
    cargoDeps = patchedVendor;
  });
  discoveryTest = runCommand "cosmic-files-remote-trash-discovery-test" {
    nativeBuildInputs = [ rustc ];
  } ''
    rustc --edition=2021 --test ${./remote-trash-mount.rs} -o remote-trash-tests
    ./remote-trash-tests
    touch "$out"
  '';
in symlinkJoin {
  name = "cosmic-files-gvfs";
  paths = [ patchedFiles ];
  nativeBuildInputs = [ makeWrapper ];
  postBuild = ''
    wrapProgram "$out/bin/cosmic-files" \
      --prefix GIO_EXTRA_MODULES : "${gvfs}/lib/gio/modules"
  '';
  passthru = {
    unwrapped = patchedFiles;
    tests.remoteTrashDiscovery = discoveryTest;
  };
  meta = cosmic-files.meta;
}

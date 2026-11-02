{ pkgs, ... }:
let
  artcraft = import ../../flakes/artcraft-suite/packages.nix { inherit pkgs; };
  suite = pkgs.symlinkJoin {
    name = "artcraft-suite-n1x";
    paths = [ artcraft.suite ];
    nativeBuildInputs = [ pkgs.makeWrapper pkgs.gnused ];
    postBuild = ''
      for exe in "$out"/bin/*; do
        wrapProgram "$exe" \
          --prefix LD_LIBRARY_PATH : /run/opengl-driver/lib \
          --set-default __EGL_VENDOR_LIBRARY_FILENAMES /run/opengl-driver/share/glvnd/egl_vendor.d/10_nvidia.json \
          --set-default __GLX_VENDOR_LIBRARY_NAME nvidia \
          --unset LIBGL_ALWAYS_SOFTWARE
      done
      for entry in "$out"/share/applications/*.desktop; do
        app="$(basename "$entry" .desktop | sed 's/^ai\.storyteller\.//')"
        sed -i "s|^Exec=[^ ]*|Exec=$out/bin/$app|" "$entry"
        sed -i "s|^TryExec=[^ ]*|TryExec=$out/bin/$app|" "$entry"
      done
    '';
  };
in {
  imports = [
    ../../pkgs/cloud-office-personal/home-module.nix
    ../../pkgs/relay-clients/linux/home-manager.nix
  ];
  home.packages = [ suite ];
  # The service waits for Simon's own private enrollment file. No token or
  # Jonathan endpoint is included in this profile or in the Nix store.
  services.relayClipboard.enable = true;
}

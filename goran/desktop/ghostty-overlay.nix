{ ghosttyPackage }:
final: prev: {
  # Keep NVIDIA rendering, but use the verified native Wayland frame fallback.
  ghostty = ghosttyPackage.overrideAttrs (old: {
    preFixup = (old.preFixup or "") + ''
      gappsWrapperArgs+=(
        --set GDK_BACKEND wayland
        --set __EGL_VENDOR_LIBRARY_FILENAMES /run/opengl-driver/share/glvnd/egl_vendor.d/10_nvidia.json
        --set __GLX_VENDOR_LIBRARY_NAME nvidia
        --unset LIBGL_ALWAYS_SOFTWARE
        --set GSK_RENDERER gl
      )
    '';
  });
  # NVIDIA 615 on N1X corrupts Ghostty's native Wayland glyph rendering.
  # XWayland renders cleanly with NVIDIA OpenGL; scope this to Ghostty.
  ghostty-x11 = prev.symlinkJoin {
    name = "ghostty-${prev.ghostty.version}-n1x-nvidia";
    paths = [ prev.ghostty ];
    nativeBuildInputs = [ prev.makeWrapper ];
    postBuild = ''
      wrapProgram "$out/bin/ghostty" \
        --set GDK_BACKEND x11 \
        --set __EGL_VENDOR_LIBRARY_FILENAMES /run/opengl-driver/share/glvnd/egl_vendor.d/10_nvidia.json \
        --set __GLX_VENDOR_LIBRARY_NAME nvidia \
        --unset LIBGL_ALWAYS_SOFTWARE \
        --set GSK_RENDERER gl
    '';
    inherit (prev.ghostty) meta;
  };
}

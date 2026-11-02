{ pkgs, inir, touchGestures ? true }:
let
  lib = pkgs.lib;
  upstream = pkgs.callPackage (inir + "/nix/package.nix") { inherit pkgs; };
  # Fetch the existing reference artwork from its public origins. Its original
  # terms remain applicable; these files are not redistributed in this Git tree.
  glow = pkgs.fetchurl {
    url = "https://raw.githubusercontent.com/zeankundev/HMOSLarp/9e3d184c31f2c5c25419e130eae9eabd4e5950f0/icons/misc/hmglow.png";
    sha256 = "a5028c63399d5c90aca8cb8bf1ef310e1b48ab8f69fe959e3cd3400597e8f821";
  };
  assistantArtwork = pkgs.fetchurl {
    url = "https://raw.githubusercontent.com/zeankundev/HMOSLarp/9e3d184c31f2c5c25419e130eae9eabd4e5950f0/icons/misc/celia.png";
    sha256 = "d28216bcdec5d13deaff5202df876f9d0080e77d9ada2bde6b3f4c68518968d2";
  };
  wallpaperJpeg = pkgs.fetchurl {
    url = "https://file.moyubuluo.com/d/file/2025-08-29/d0fcb1ec3ec6e5ae87415278e17fbcd3.jpg";
    sha256 = "9de8e566d7f85ba121d620530bb47a3f230f5702ec20e4873f526c7c5a94deda";
  };
  wallpaper = pkgs.runCommand "hp-os-reference-wallpaper.png" {
    nativeBuildInputs = [ (pkgs.python3.withPackages (ps: [ ps.pillow ])) ];
  } ''
    python3 -c 'from PIL import Image; import os; Image.open("${wallpaperJpeg}").save(os.environ["out"], "PNG")'
  '';
  shell = upstream.overrideAttrs (old: {
    pname = "hp-os-runtime";
    patches = (old.patches or []) ++ [ ../patches/inir-harmony.patch ../patches/harmony-style.patch ../patches/harmony-wallpaper-startup.patch ../patches/harmony-desktop-labels.patch ../patches/harmony-portable-icons.patch ../patches/harmony-notification-banners.patch ];
    postPatch = (old.postPatch or "") + ''
      cp -r ${../overlay}/. .
      mkdir -p assets/larp
      cp ${glow} assets/larp/hmglow.png
      cp ${assistantArtwork} assets/larp/hp-os.png
      cp ${wallpaper} assets/harmony-wallpaper.png
      chmod -R u+w modules/harmony
    '';
  });
  touchBackend = pkgs.callPackage ../touch/backend/default.nix { };
  touchPython = pkgs.python3.withPackages (ps: [ ps.evdev ps.pyudev ]);
  touchSupport = pkgs.callPackage ../touch/package.nix {
    inherit touchBackend touchPython touchGestures niri;
    squeekboard = pkgs.callPackage ../touch/squeekboard.nix { };
  };
  qmlDeps = [ pkgs.kdePackages.kirigami.unwrapped pkgs.kdePackages.syntax-highlighting pkgs.qt6.qt5compat pkgs.qt6.qtdeclarative pkgs.qt6.qtmultimedia pkgs.qt6.qtwayland ];
  fontsConf = pkgs.makeFontsConf {
    fontDirectories = [ pkgs.inter pkgs.material-symbols pkgs.noto-fonts-cjk-sans pkgs.noto-fonts-color-emoji ];
    impureFontDirectories = [ "~/.local/share/fonts" "~/.fonts" "/run/current-system/sw/share/X11/fonts" "/usr/share/fonts" "~/.nix-profile/share/fonts" ];
  };
  # HP-OS owns a private D-Bus session without importing the global user
  # manager environment. Enable Niri's portal service channel in that mode.
  tabletPatches = pkgs.fetchFromGitHub {
    owner = "GGEZUS"; repo = "niri-tablet";
    rev = "d4dbaef7072599719835959e995cc0b561cb06a6";
    hash = "sha256-9/lU9xTk739oZkehUBVOlS3NH4eAyxow3og1LWpGkOU=";
  };
  niriStock = pkgs.niri.overrideAttrs (old: {
    patches = (old.patches or []) ++ [ ../patches/niri-private-session-service-channel.patch ];
  });
  niri = if !touchGestures then niriStock else niriStock.overrideAttrs (old: {
    # v26.04.20 is an ordered patch series against upstream v26.04.
    # Reject a silent upstream version change instead of applying loosely.
    prePatch = (old.prePatch or "") + ''
      test "${old.version}" = "26.04"
      for patch in ${tabletPatches}/pkg/*.patch; do
        patch -p1 --fuzz=0 < "$patch"
      done
    '';
    patches = (old.patches or []) ++ [ ../patches/niri-keyboard-touch-ownership.patch ];
  });
  # Keep the dynamic Users KCM and its QML imports on the same Qt/KDE version.
  # The shell and the host desktop can use different Nixpkgs revisions.
  userSettings = pkgs.writeShellScriptBin "hp-os-user-settings" ''
    if [ "''${1-}" = "--available" ]; then
      test -x ${pkgs.kdePackages.systemsettings}/bin/systemsettings
      exit $?
    fi
    unset QML_IMPORT_PATH QML2_IMPORT_PATH QT_PLUGIN_PATH
    unset NIXPKGS_QT6_QML_IMPORT_PATH NIXPKGS_QT6_PLUGIN_PATH
    export NIXPKGS_QT6_QML_IMPORT_PATH="${pkgs.kdePackages.plasma-workspace}/lib/qt-6/qml:${pkgs.kdePackages.kirigami-addons}/lib/qt-6/qml"
    export NIXPKGS_QT6_PLUGIN_PATH="${pkgs.kdePackages.plasma-workspace}/lib/qt-6/plugins"
    export XDG_DATA_DIRS="${pkgs.kdePackages.plasma-workspace}/share:''${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
    exec ${pkgs.kdePackages.systemsettings}/bin/systemsettings kcm_users
  '';
  desktopApps = [ pkgs.kdePackages.dolphin pkgs.kdePackages.gwenview ];
  runtimeDeps = [ niri touchSupport ] ++ (builtins.filter (p: lib.getName p != "niri") shell.runtimeDependencies) ++ [ pkgs.swayidle pkgs.dbus pkgs.polkit_gnome pkgs.fontconfig pkgs.patch ];
in pkgs.stdenvNoCC.mkDerivation {
  pname = "hp-os";
  version = "0.1.0";
  src = ./.;
  nativeBuildInputs = [ pkgs.makeWrapper ];
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/share/hp-os" "$out/share/wayland-sessions" "$out/share/applications" "$out/share/hp-os/applications"
    cp -r . "$out/share/hp-os/packaging"
    cp hp-os "$out/bin/hp-os"
    chmod +x "$out/bin/hp-os"
    substituteInPlace "$out/bin/hp-os" \
      --replace-fail '@dbusSessionConfig@' '${pkgs.dbus}/share/dbus-1/session.conf' \
      --replace-fail '@runtime@' '${shell}/share/quickshell/inir' \
      --replace-fail '@packaging@' "$out/share/hp-os/packaging"
    ln -s ${touchSupport}/bin/touch-support "$out/bin/touch-support"
    ln -s ${touchSupport}/bin/hp-os-keyboard "$out/bin/hp-os-keyboard"
    ln -s ${userSettings}/bin/hp-os-user-settings "$out/bin/hp-os-user-settings"
    cp hp_os_theme.py "$out/bin/hp_os_theme.py"
    cp hp-os-appearance.py "$out/bin/hp-os-appearance"
    chmod +x "$out/bin/hp-os-appearance"
    substituteInPlace "$out/bin/hp-os-appearance" \
      --replace-fail '@python@' '${pkgs.python3}/bin/python3' \
      --replace-fail '@filesAssets@' "$out/share/hp-os/packaging/files" \
      --replace-fail '@gsettings@' '${pkgs.glib}/bin/gsettings' \
      --replace-fail '@dconfModules@' '${pkgs.dconf.lib}/lib/gio/modules' \
      --replace-fail '@schemas@' '${pkgs.gsettings-desktop-schemas}/share/gsettings-schemas/${pkgs.gsettings-desktop-schemas.name}/glib-2.0/schemas'
    cp hp-os-toggle-floating-all.py "$out/bin/hp-os-toggle-floating-all"
    chmod +x "$out/bin/hp-os-toggle-floating-all"
    substituteInPlace "$out/bin/hp-os-toggle-floating-all" \
      --replace-fail '@python@' '${pkgs.python3}/bin/python3' \
      --replace-fail '@niri@' '${niri}/bin/niri'
    cp hp-os-recents.py "$out/bin/hp-os-recents"
    chmod +x "$out/bin/hp-os-recents"
    substituteInPlace "$out/bin/hp-os-recents" --replace-fail '@python@' '${pkgs.python3}/bin/python3'
    cp hp-os-files.py "$out/bin/hp-os-files"
    chmod +x "$out/bin/hp-os-files"
    substituteInPlace "$out/bin/hp-os-files" \
      --replace-fail '@python@' '${pkgs.python3}/bin/python3' \
      --replace-fail '@qtPlugins@' '${pkgs.kdePackages.plasma-integration}/lib/qt-6/plugins:${pkgs.kdePackages.breeze}/lib/qt-6/plugins' \
      --replace-fail '@filesAssets@' "$out/share/hp-os/packaging/files" \
      --replace-fail '@dolphin@' '${pkgs.kdePackages.dolphin}/bin/dolphin'
    substitute hp-os-files.desktop "$out/share/hp-os/applications/org.kde.dolphin.desktop" \
      --replace-fail '@exec@' "$out/bin/hp-os-files"
    wrapProgram "$out/bin/hp-os" \
      --set HP_OS_TOUCH_PATCHED "${if touchGestures then "1" else "0"}" \
      --set FONTCONFIG_FILE "${fontsConf}" \
      --prefix XDG_DATA_DIRS : "$out/share/hp-os/packaging/files/data:$out/share/hp-os:$out/share:${pkgs.adwaita-icon-theme}/share:${pkgs.hicolor-icon-theme}/share:${lib.makeSearchPath "share" desktopApps}" \
      --prefix PATH : '${lib.makeBinPath runtimeDeps}' \
      --prefix QML2_IMPORT_PATH : '${lib.makeSearchPath "lib/qt-6/qml" qmlDeps}' \
      --prefix QT_PLUGIN_PATH : '${lib.makeSearchPath "lib/qt-6/plugins" qmlDeps}'
    substitute hp-os-settings.desktop "$out/share/applications/hp-os-settings.desktop" \
      --replace-fail '@exec@' "$out/bin/hp-os"
    substitute hp-os-trash.desktop "$out/share/applications/hp-os-trash.desktop" \
      --replace-fail '@dolphin@' "$out/bin/hp-os-files"
    substitute hp-os.desktop "$out/share/wayland-sessions/hp-os.desktop" \
      --replace-fail '@exec@' "$out/bin/hp-os"
  '';
  passthru = { inherit shell niri niriStock touchSupport touchBackend; providedSessions = [ "hp-os" ]; };
  meta = { description = "HP-OS mobile-inspired desktop session"; license = lib.licenses.gpl3Only; platforms = lib.platforms.linux; mainProgram = "hp-os"; };
}

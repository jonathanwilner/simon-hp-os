{ lib, stdenv, fetchurl, dpkg, patchelf, makeWrapper, autoPatchelfHook
, alsa-lib, at-spi2-atk, at-spi2-core, cairo, cups, dbus, expat, gdk-pixbuf
, glib, gtk3, libdrm, libgbm, libglvnd, mesa, nspr, nss, pango
, systemd, libsecret, libnotify, xorg, libxkbcommon
}:
let
  version = "6.0.6";
  deb = fetchurl {
    url = "https://github.com/koush/vysor.io/releases/download/v${version}/vysor_${version}_amd64.deb";
    hash = "sha256-gqvhXNqn6tCmHQ39huq0ptakTW9R/DCsFTHQPSBOrMY=";
  };

  # The vendor Linux deb omits the Android APK used by the desktop viewer.
  androidApk = fetchurl {
    url = "https://app.v6.vysor.io/Vysor-release.apk";
    hash = "sha256-6oooKLeQsbqFJzXmEeajNE0gdv3aGWjfefi+AQvgqDY=";
  };

  libs = [
    alsa-lib at-spi2-atk at-spi2-core cairo cups dbus expat gdk-pixbuf
    glib gtk3 libdrm libgbm libglvnd mesa nspr nss pango systemd
    libsecret libnotify xorg.libX11 xorg.libXcomposite xorg.libXdamage
    xorg.libXext xorg.libXfixes xorg.libXrandr xorg.libxcb
    xorg.libXScrnSaver libxkbcommon
  ];
in
stdenv.mkDerivation {
  pname = "vysor";
  inherit version;
  src = deb;

  nativeBuildInputs = [ dpkg patchelf makeWrapper autoPatchelfHook ];
  buildInputs = libs;

  dontUnpack = true;
  dontConfigure = true;
  dontBuild = true;

  installPhase = ''
    runHook preInstall
    dpkg-deb --fsys-tarfile $src | tar --no-same-permissions -xf -
    mkdir -p $out/opt
    cp -r usr/lib/vysor $out/opt/Vysor
    install -Dm644 "${androidApk}" "$out/opt/Vysor/resources/app/native/android/Vysor-release.apk"
    cp -r usr/share $out/share
    substituteInPlace $out/share/applications/vysor.desktop --replace-fail "Name=vysor" "Name=Vysor"
    substituteInPlace $out/share/applications/vysor.desktop --replace-fail "Exec=vysor" "Exec=$out/bin/vysor"
    chmod -R u+w $out
    # Electron's suid sandbox cannot work from a read-only store path.
    rm -f $out/opt/Vysor/chrome-sandbox
    install -d $out/bin
    makeWrapper $out/opt/Vysor/vysor $out/bin/vysor \
      --prefix LD_LIBRARY_PATH : "$out/opt/Vysor:${lib.makeLibraryPath libs}" \
      --add-flags "--no-sandbox"
    runHook postInstall
  '';

  meta = {
    description = "Vysor — mirror and control iOS/Android devices from the desktop";
    homepage = "https://www.vysor.io";
    license = lib.licenses.unfree;
    platforms = [ "x86_64-linux" ];
    mainProgram = "vysor";
  };
}

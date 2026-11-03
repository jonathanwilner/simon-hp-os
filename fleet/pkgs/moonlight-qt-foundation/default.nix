{
  stdenv,
  lib,
  fetchFromGitHub,
  qt6,
  python3,
  pkg-config,
  vulkan-headers,
  SDL2,
  SDL2_ttf,
  ffmpeg,
  libopus,
  libplacebo,
  openssl,
  alsa-lib,
  libpulseaudio,
  libva,
  libvdpau,
  libxkbcommon,
  wayland,
  libdrm,
}:

stdenv.mkDerivation (finalAttrs: {
  pname = "moonlight-qt-foundation";
  version = "6.3.2-unstable-2026-10-10";

  # Build the Foundation/V+ fork from source. The published AppImage is built
  # with CONFIG+=disable-wayland and ships only Qt's xcb platform plugin, which
  # forces an otherwise-native Niri session through XWayland.
  src = fetchFromGitHub {
    owner = "qiin2333";
    repo = "moonlight-qt";
    rev = "ac1a11ea8396e56545c24e2d4203a17e76777a23";
    hash = "sha256-t2HzISreAQlKdf5AwTyEBkg/Gi4npAfH8mAivM1FvEU=";
    fetchSubmodules = true;
  };

  patches = [ ./stable-local-cursor.patch ];

  nativeBuildInputs = [
    qt6.qmake
    qt6.wrapQtAppsHook
    pkg-config
    python3
    vulkan-headers
  ];

  buildInputs = [
    SDL2
    SDL2_ttf
    ffmpeg
    libopus
    libplacebo
    qt6.qtdeclarative
    qt6.qtmultimedia
    qt6.qtsvg
    openssl
  ]
  ++ lib.optionals stdenv.hostPlatform.isLinux [
    alsa-lib
    libpulseaudio
    libva
    libvdpau
    libxkbcommon
    qt6.qtwayland
    wayland
    libdrm
  ];

  qmakeFlags = [ "CONFIG+=disable-prebuilts" ];

  # Prefer a native Wayland Qt and SDL stack while retaining the ability to
  # override either variable for troubleshooting from a shell.
  preFixup = ''
    qtWrapperArgs+=(
      --set-default QT_QPA_PLATFORM wayland
      --set-default SDL_VIDEODRIVER wayland
      --set-default MOONLIGHT_STABLE_LOCAL_CURSOR 1
      --set-default LIBVA_DRIVERS_PATH /run/opengl-driver/lib/dri
      --set-default PREFER_VULKAN 1
    )
  '';

  postInstall = ''
    substituteInPlace $out/share/applications/com.moonlight_stream.Moonlight.desktop \
      --replace-fail "Name=Moonlight" "Name=Moonlight Foundation" \
      --replace-fail \
        "Comment=Stream games and other applications from another PC running Sunshine or GeForce Experience" \
        "Comment=Foundation-enhanced Moonlight client for Sunshine streaming" \
      --replace-fail \
        "Keywords=nvidia;gamestream;stream;sunshine;remote play;" \
        "Keywords=foundation;moonlight;nvidia;gamestream;stream;sunshine;remote play;"
  '';

  meta = {
    description = "Foundation-enhanced Moonlight client with native Wayland support";
    longDescription = ''
      The qiin2333 Foundation client fork of Moonlight Qt, compiled from source
      with Qt Wayland, SDL Wayland, Wayland presentation pacing, VA-API, and the
      Vulkan renderer available. It retains standard Moonlight and Sunshine
      compatibility while adding Foundation Sunshine extensions.
    '';
    homepage = "https://github.com/qiin2333/moonlight-qt";
    changelog = "https://github.com/qiin2333/moonlight-qt/commits/${finalAttrs.src.rev}";
    license = lib.licenses.gpl3Plus;
    mainProgram = "moonlight";
    platforms = lib.platforms.linux;
    sourceProvenance = [ lib.sourceTypes.fromSource ];
  };
})

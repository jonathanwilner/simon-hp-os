{ pkgs }:
let
  version = "2026.903.160345";
  rev = "8d1c7ece8394ba4d95e0f9fa6a7ac6524526f39e";
  foundationSrc = pkgs.fetchgit {
    url = "https://github.com/AlkaidLab/foundation-sunshine.git";
    inherit rev;
    hash = "sha256-taaiEdC4RGDegSmHJcuD1Vn31YoKpNDMJJaWWcezSEs=";
    fetchSubmodules = true;
  };
  foundationUi =
    (pkgs.buildNpmPackage.override {
      nodejs = pkgs.nodejs_26;
    })
      {
        pname = "foundation-sunshine-ui";
        inherit version;
        src = foundationSrc;
        npmDepsFetcherVersion = 2;
        npmDepsHash = "sha256-ZOeU1X6JRfBWuSMgN7IS/LdqIRTqlTLAsSAzbd5nKqU=";
        postPatch = ''
          cp ${./foundation-sunshine-package-lock.json} package-lock.json
        '';
        installPhase = ''
          runHook preInstall
          mkdir -p "$out"
          cp -a build "$out"/
          runHook postInstall
        '';
      };
in
(pkgs.sunshine.override {
  cudaSupport = false;
}).overrideAttrs
  (old: {
    pname = "foundation-sunshine";
    inherit version;
    src = foundationSrc;
    ui = foundationUi;
    patches = (old.patches or [ ]) ++ [
      ../patches/foundation-sunshine-linux-packaging.patch
      ../patches/foundation-sunshine-linux-vdd.patch
      ../patches/foundation-sunshine-linux-compile.patch
      ../patches/foundation-sunshine-wayland-logical-pointer.patch
      ../patches/foundation-sunshine-app-display.patch
      ../patches/foundation-sunshine-kms-monitors.patch
      # FFmpeg changed NVENC preset enum values. Names work across versions.
      ../patches/foundation-sunshine-nvenc-preset-names.patch
    ];
    postPatch = ''
      cp ${./foundation-sunshine-vdd-utils-linux.cpp} \
        src/display_device/vdd_utils_linux.cpp

      sed -i '1i include_directories(BEFORE SYSTEM "''${CMAKE_SOURCE_DIR}/third-party/AMF/amf/public/include")' \
        cmake/compile_definitions/linux.cmake

      substituteInPlace cmake/targets/common.cmake \
        --replace-fail 'find_program(NPM npm REQUIRED)' ""

      sed -i -E 's/set\(BOOST_VERSION "[^"]*"\)/set(BOOST_VERSION "${pkgs.boost.version}")/' \
        cmake/dependencies/Boost_Sunshine.cmake
      echo 'set(FETCH_CONTENT_BOOST_USED TRUE)' >> cmake/dependencies/Boost_Sunshine.cmake

      substituteInPlace cmake/packaging/linux.cmake \
        --replace-fail 'find_package(Systemd)' "" \
        --replace-fail 'find_package(Udev)' ""
      substituteInPlace packaging/linux/sunshine.desktop \
        --replace-fail '/usr/bin/env systemctl start --u sunshine' 'sunshine'
      substituteInPlace packaging/linux/sunshine.service.in \
        --replace-fail '/bin/sleep' '${pkgs.lib.getExe' pkgs.coreutils "sleep"}'
    '';
    preBuild = ''
      cp -r ${foundationUi}/build ../
    '';
    # File capabilities discard LD_LIBRARY_PATH. The native
    # executable must find Ubuntu's matching NVIDIA libraries
    # through the Home Manager GPU bridge in its own RPATH.
    appendRunpaths = (old.appendRunpaths or [ ]) ++ [
      "/run/opengl-driver/lib"
      "${pkgs.vulkan-loader}/lib"
    ];
    buildInputs = builtins.filter (input: input != pkgs.amf-headers) old.buildInputs;
    env = (old.env or { }) // {
      BUILD_VERSION = version;
      # Upstream honors BUILD_VERSION only for this branch value.
      # The source remains pinned to the release commit above.
      BRANCH = "master";
      COMMIT = rev;
    };
    cmakeFlags =
      (builtins.filter (flag: !(pkgs.lib.hasPrefix "-DFFMPEG_PREPARED_BINARIES=" flag)) old.cmakeFlags)
      ++ [
        # Foundation tracks a newer Qt-based tray submodule while
        # its Linux CMake still names the retired tray_linux.c.
        # Slazenger runs Sunshine as a user service, so the tray is
        # unnecessary and the daemon remains fully functional.
        "-DSUNSHINE_ENABLE_TRAY:BOOL=OFF"
        "-DSUNSHINE_REQUIRE_TRAY:BOOL=OFF"
      ];
    meta = (old.meta or { }) // {
      homepage = "https://github.com/AlkaidLab/foundation-sunshine";
    };
  })

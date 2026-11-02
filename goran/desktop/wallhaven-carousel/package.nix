{
  lib,
  stdenvNoCC,
  fetchFromGitHub,
  python3,
}:

stdenvNoCC.mkDerivation {
  pname = "dms-wallhaven-carousel";
  version = "1.1.1";
  src = fetchFromGitHub {
    owner = "alicercedigital";
    repo = "wallhaven-carousel";
    rev = "fb508ec037a8ec63a622c3f49fd1f72031ca91c3";
    hash = "sha256-715H5DpiqoZ9foKYaAO5PvZ/0LrpagD7hbvIpBl2ndo=";
  };

  nativeBuildInputs = [ python3 ];
  postPatch = ''
    python3 ${./patch.py}
  '';
  dontBuild = true;
  installPhase = ''
    runHook preInstall
    mkdir -p "$out"
    cp -r . "$out/"
    runHook postInstall
  '';
  meta = {
    description = "Wallhaven search and wallpaper library compatible with Goran's pinned DMS";
    homepage = "https://github.com/alicercedigital/wallhaven-carousel";
    license = lib.licenses.mit;
    platforms = lib.platforms.linux;
  };
}

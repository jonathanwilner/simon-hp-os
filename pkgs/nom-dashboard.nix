{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  nix-output-monitor,
  tmux,
  rsync,
  openssh,
  bash,
  coreutils,
  gnused,
  gnugrep,
  findutils,
}:

# Nix build and test dashboard tooling.
#
# `nom-tmux` runs a command in a detached tmux session, renders Nix output
# through nom, and records a status/log/metadata triple. The record and publish
# scripts turn that state into the static dashboard served at
# a configurable local or remote directory. Nix and nixos-rebuild commands are rendered
# through nom; any other command (tests, scripts, any build) is tracked with
# the same log, exit status, and published metadata.
#
# The default state directory is intentionally the legacy
# `~/.local/state/nixos-intc/nom-tmux` path so the existing Armstrong publish
# service and already-published machine data keep working. Override with
# NOM_DASHBOARD_STATE_DIR, NOM_DASHBOARD_PUBLIC_DIR, or NOM_DASHBOARD_ASSET_DIR.
stdenvNoCC.mkDerivation {
  pname = "nom-dashboard";
  version = "1.0.0";

  src = ./nom-dashboard;

  nativeBuildInputs = [ makeWrapper python3 ];

  dontConfigure = true;
  dontBuild = true;

  installPhase = ''
    runHook preInstall
    mkdir -p "$out/bin" "$out/share/nom-dashboard"

    install -m755 nom-tmux.sh "$out/bin/nom-tmux"
    install -m755 nom-dashboard-watch.sh "$out/bin/nom-dashboard-watch.sh"
    install -m755 nom-dashboard-sync.sh "$out/bin/nom-dashboard-sync"
    install -m755 nom-dashboard-record.py "$out/bin/nom-dashboard-record.py"
    install -m755 nom_dashboard_feed.py "$out/bin/nom_dashboard_feed.py"
    install -m755 nom_dashboard_progress.py "$out/bin/nom_dashboard_progress.py"
    ln -s nom_dashboard_progress.py "$out/bin/nom-dashboard-progress"
    install -m755 nom-dashboard-publish.py "$out/bin/nom-dashboard-publish.py"
    install -m644 web/app.js web/index.html web/styles.css "$out/share/nom-dashboard/"

    patchShebangs "$out/bin"

    wrapProgram "$out/bin/nom-tmux" \
      --prefix PATH : ${
        lib.makeBinPath [
          python3
          nix-output-monitor
          tmux
          bash
          coreutils
          gnused
          gnugrep
          findutils
        ]
      }
    wrapProgram "$out/bin/nom-dashboard-sync" \
      --prefix PATH : ${
        lib.makeBinPath [
          python3
          rsync
          openssh
          coreutils
          gnused
          findutils
        ]
      }

    runHook postInstall
  '';

  meta = {
    description = "nom build and test dashboard tooling for local and remote reports";
    mainProgram = "nom-tmux";
    platforms = lib.platforms.unix;
  };
}

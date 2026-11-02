# HP CDE lock screen

The layout follows CDE's original lock dialog: a centered, undecorated frame with a 5-pixel outer bevel, 15-pixel margins, and adjacent 2-pixel raised password and logo panels. The left panel retains the original wording. The backdrop is black.

References: [CDE CreateLockDialog](https://github.com/cdesktopenv/cde/blob/master/cde/programs/dtsession/SmUI.c), [Dtsession defaults](https://github.com/cdesktopenv/cde/blob/master/cde/programs/dtsession/Dtsession.src), and [HP-UX Graphics Administration Guide, printed page 27](https://web-docs.gsi.de/~kraemer/COLLECTION/HPUX/lpv38356.pdf). The implementation is a source-based adaptation; no verified HP-specific historical screenshot was found.

Modern additions retain Goran's HP login artwork, the local username and hostname, clock/date, profile picture, password visibility and submit controls, authentication feedback, notifications and desktop status. Existing weather, media, alternate keyboard layouts, input methods, on-screen keyboard, fingerprint/security-key feedback and power controls keep their handlers and visibility settings.

Goran keeps its existing NVIDIA green palette selected by local hostname. Other desktops keep the Soft Honeydew HP banner and slate panels. The logo artwork is reused from the fleet login theme, not claimed as the original HP CDE lock logo.

## Fleet management

The AMD, Intel and Goran Home Manager configurations enable the shared module. `home.nix` manages assets and `90-hp-cde-lockscreen.conf`, ordered after the messaging override. Goran uses its installed package source. Armstrong uses its messaging-patched shell. Other desktops use their existing DMS cache. `run.sh` copies that source into a private cache, applies visual changes and starts the original backend. Unknown source revisions fall back to the original screen. Known DMS 1.5 and 1.6 components are checked by SHA-256.

The same shared launcher removes DMS's periodic Wi-Fi scan timer with
`dms-wifi-scan.py`. Wi-Fi list opening and manual refresh still scan.
NetworkManager manages background discovery and roaming. DMS 1.5 has no
such QML timer and remains unchanged. The network fix also applies when
the visual patch falls back to the original lock screen.

## Scoped deployment

Run on the target inside `nom-tmux`:

- Goran: `goran/deploy.sh --lockscreen-only`
- Krickstein: `scripts/deploy-krickstein.sh --lockscreen-only --checkout PATH`
- Other fleet desktops: `bash goran/desktop/hp-cde-lockscreen/install.sh BASE_QML_DIR DMS_BIN PYTHON3`

The installer validates before changing assets, backs up the prior configuration, then restarts DMS. Applications, the active Home Manager generation and PAM configuration remain unchanged. Locked sessions automatically use staging only. Explicit staging uses `install.sh --stage-only BASE_QML_DIR DMS_BIN PYTHON3`; rerun without that option after unlocking to activate. Normal Home Manager activation manages the same files afterward.

The override lives at `~/.config/systemd/user/dms.service.d/90-hp-cde-lockscreen.conf`. Installation removes the previous `50-*` override. Backups of assets and overrides live under `~/.local/state/hp-cde-lockscreen/`. To remove the theme, remove its override, reload the user systemd manager and restart DMS while unlocked. Failed immediate activation restores prior assets and overrides.

## Validation

Run `verify.py` with original `LockScreenContent.qml` files. It checks that all named functions, event handlers and existing component IDs remain unchanged, that the patch is idempotent and that unknown revisions are rejected. The current sources retain 46 handlers in DMS 1.6 and 29 in DMS 1.5. `Pam.qml`, `Lock.qml` and `LockSurface.qml` are unchanged.


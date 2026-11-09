# Desktop parity audit

9 November 2026. Configuration audit only; physical keys, UI, GPU and suspend
require separate acceptance. Simon imported `fleet/home.nix` plus Goran desktop
modules. Snapdragon originally imported fleet applications and a minimal
session. Packages alone did not provide those desktop integrations.

| Area | Source and disposition |
| --- | --- |
| Screenshot, launcher and window bindings | `goran/desktop/launchers.nix` and `niri.nix`: shared Niri module owns portable helpers/bindings. |
| Clipboard persistence/history | `goran/desktop/apps.nix`: shared session supervisor starts missing processes scoped to its display/bus. |
| Recording/mirroring/forwarding/fonts | `goran/desktop/apps.nix`: shared session supplies wf-recorder, wl-mirror, waypipe, CJK, emoji and terminal glyphs. |
| Input methods | Rime/Fcitx5 is opt-in; HP-OS owned touch keyboard keeps its input-method seat. Set environment variables only in the ordinary DMS launcher. |
| Privileged desktop actions | A session-scoped polkit agent starts only when no matching agent exists on that display/bus. System polkitd alone is insufficient. |
| DMS features | Monitoring, VPN, calendar, dynamic theme, clipboard paste belong in the DMS consumer. Never launch DMS inside HP-OS. |
| User-manager services | Ordinary Niri exports its environment and starts graphical-session.target. HP-OS private D-Bus stays private. |
| Ask IQ | `goran/desktop/search-iq.nix`: portable CPU-only service now shared behind `session.searchIq.enable`, default false. Downloads a model, binds localhost:30002, retains 2 GiB and 200% CPU limits. |
| Apps, Office, Chrome, media, Steam ARM, printing, Owly, Relay | Already shared fleet modules. Enrollment, credentials, sign-ins and games remain separate. |
| HP theme and terminal styles | Portable assets, but Goran activation mutates writable files and restarts Goran DMS. Extract defaults while preserving user themes and active sessions. |
| Wallhaven | Portable DMS option requiring its plugin/settings. Wallpaper files alone do not enable it. |
| Headphones/KDE Connect | Executables already shared. Pairing, daemon activation and network/firewall integration remain explicit. |
| Goran brightness/NVIDIA/HDR/EDID/Ghostty workaround | Hardware-specific. Never copy NVIDIA environment or panel overrides into Qualcomm defaults. |
| Battery workaround/suspend | Goran firmware-specific. Do not install automatic suspend policy while Snapdragon resume remains unreliable. |
| Artcraft | Simon wrapper forces NVIDIA. Needs architecture/GPU-neutral packaging before sharing. |
| Remote access/proxy/personal cloud-office | Host-owned identities, secrets and enrollment remain private. |
| Fish/tmux/editor/MIME preferences | Reusable optional user preferences, not automatic replacement of existing defaults. |

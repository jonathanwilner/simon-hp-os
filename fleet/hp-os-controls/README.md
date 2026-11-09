# Portable HP-OS controls

Import `home.nix` and enable `programs.hp-os-fleet.desktopControls.enable`.
The one-time activation adds notifications and adds battery only when Linux
reports an actual Battery power supply. Existing bar pieces remain in order.
The inherited Dolphin dock pin becomes COSMIC Files; deliberately absent pins
stay absent. The module installs COSMIC Files. A state marker preserves later
user edits. Missing HP-OS configuration is left untouched and retried next time.
No desktop process is restarted. Existing sessions may need to reload settings.

Optional touchscreen package adaptation:

```nix
shell = import ./fleet/hp-os-controls/package.nix { hpOs = originalShell; };
```

This reuses Goran's 600 ms long-press right-click patch and supplies matching
Niri and touch tools. Pass this adapted shell consistently to session launchers
and shared Niri configuration. It requires a compositor build and a new login
to take effect. It does not enable gestures, change touchscreen output mapping,
change the keyboard mode, alter PAM, or change suspend policy.

Excluded Goran settings: NVIDIA environment, eDP-1 mapping, Caps-as-Control,
forced on-screen keyboard disable, and its Ubuntu PAM binary bridge. Snapdragon
already has its own working Ubuntu PAM helper. Audio volume-protection limits
remain user-controlled. HP-OS touch keyboard support remains available through
the existing package and configuration; no additional seat owner is started.

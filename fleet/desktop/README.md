# NixOS desktop integration

Import `desktop-fleet.nixosModules.desktop` and set
`programs.hp-os-fleet.desktop.enable = true` in each participating NixOS host.
The module supplies ripgrep, fd, build dashboard tools, desktop CUPS support and
scoped passwordless desktop actions for wheel administrators. It preserves host
networking, authentication, hardware and login-session configuration. It is
disabled by default. Chrome channels still require the Chrome overlay and
`programs.hp-os-fleet.chromeChannels.enable` in Home Manager.

Home Manager consumers import `homeModules.fleetApps` as before. Release reports
now use the installed fleet marker without requiring a source checkout. Set
`programs.hp-os-fleet.release.consumerLock` to the consumer's live lock file to
report configured-versus-installed drift as well. Writers can explicitly set
`release.checkout` to retain source cleanliness and publication checks.
An activation marker tracks the actual Home Manager generation used by NixOS.
Scheduled dashboard tasks close their tmux session on success and failure;
interactive tasks can explicitly retain it with `NOM_TMUX_KEEP_SESSION=1`.

# Shared HP-OS desktop configuration

This public flake is the source of truth for common desktop packages and settings. Goran, Simon and NixOS HP-OS desktops consume `homeModules.fleetApps`. Add future common features here, then update the `desktop-fleet` lock in consuming flakes. Do not add a Goran-only copy of a common feature.

The module uses the consuming host package set. Linux ARM64 and x86-64 receive native Electron and the native Vulkan Upscayl engine. Simon remains `aarch64-linux`; his Ubuntu kernel, NVIDIA driver, user name and hardware settings remain in his host profile. Machine credentials and personal services never belong in this public module.

Current common features: Upscayl and the original wallpaper collection. Existing desktop features retain their existing modules until their host assumptions are separated. The module does not change the selected wallpaper.

Consumers add `inputs.desktop-fleet.url = "github:jonathanwilner/simon-hp-os"` and import `desktop-fleet.homeModules.fleetApps`. Run `nix flake update desktop-fleet`, review the lock change, build, and activate through the host deployment procedure. A lock update alone does not activate a configuration.

Simon can merge public main with `bash goran/installer/update-desktop.sh`. His configuration directly imports this same module, so the updater and installer receive the same shared features. Local customizations are retained by the updater recovery and merge workflow. Feature overrides are available under `programs.hp-os-fleet`: `enable`, `upscayl.enable`, and `wallpapers.enable`.

Upscayl updates are managed by Home Manager. On Ubuntu with AppArmor, activation installs a policy for the exact pinned Electron executable using passwordless sudo. This allows its user-namespace sandbox without disabling the sandbox. Linux hosts without that Ubuntu AppArmor tool path skip this activation step.

## Debugging tools

The shared fleet module imports the pinned [debugging tools flake](https://github.com/jonathanwilner/simon-hp-os/tree/5f7cc2aeeefbf921368ef4edec666cde064c4761/flakes/debug-tools).
Simon and Ubuntu Snapdragon enable the tools in their profiles. Other Home
Manager consumers set `programs.fleet-debug-tools.enable = true;`. Set
`programs.fleet-debug-tools.exclude` to keep a host-specific package for an
individual tool.

## Media keys

`media-keys.nix` installs `hp-os-media-key` with pinned WirePlumber and playerctl
dependencies. Hosts bind media keys to `volume-up`, `volume-down`, `mute`,
`mic-mute`, `play-pause`, `stop`, `next`, or `previous`. Volume changes use 10%
steps capped at 100% and unmute the selected output after a successful change.
This prevents a muted output from making working volume keys appear inactive.
Brightness remains in each host's hardware module. Set
`programs.hp-os-fleet.mediaKeys.enable = false` to omit this helper.
Both ARM64 and x86-64 expose `packages.<system>.hp-os-media-key` for focused
builds. The shared Home Manager import supplies the helper to both fresh
installations and existing systems when their fleet input is updated.

## Application launcher baseline

`launcher-apps.nix` installs Goran's portable terminal, media, audio, network,
scanner, remote desktop, recording and editor applications in every consuming
Home Manager account. Ghostty, Alacritty, Foot and fuzzel use each host's native
package set on ARM64 and x86-64. Package desktop entries provide executable
paths and icons to both fuzzel and the HP-OS app launcher. New accounts receive
Goran's light fuzzel appearance and Ghostty as the terminal for console apps.
Existing fuzzel settings and the theme service's writable file remain intact.

This baseline excludes Goran's Ubuntu and NVIDIA control panels, Googlebook VM
application bridges, installed Steam game shortcuts, personal proxy launchers,
and private service tools. Those entries require their corresponding runtime
or host configuration. Microsoft 365, search, Steam, Sunshine, COSMIC files,
other service integrations continue through their own modules.
The baseline installs applications without starting or restarting them.

`fleet/launcher-packages.nix` exposes the same native package list for NixOS
`environment.systemPackages`, making launcher entries available to every normal
account without separate Home Manager profiles. The list also includes COSMIC
Files with GVfs network-drive support, COSMIC Terminal, Emacs, KDE Connect,
LibrePods, OpenFreebuds, Fcitx configuration, BlueBubbles and the same pinned
source build of Moonlight Foundation used on Goran. Set
`programs.hp-os-fleet.bluebubbles.package` to install the private Glass build
from a consumer flake. Public configurations default to the nixpkgs client. Emacs uses native
Emacs PGTK without copying personal mail credentials or the private Emacs setup.

Goran's DeepSeek Harness desktop command depends on a separate ARM64 package
profile. Its web interface depends on a user server, model endpoint configuration
and application state. The shared `fleet/agents` module supplies the harness
command line and terminal UI; the desktop and web launchers stay with the host
because they need the local Qwen endpoints. Open WebUI runs a Docker container
configured for Goran's NVIDIA-hosted Qwen endpoints. These runtimes require
separate AMD service setup; copying their desktop files would create launchers
without their dependencies.
Windows 365 uses the public RDPiO flake and user authentication. Its package is
host-integrated independently of this package list. Goran's DMS wallpaper
launchers require the corresponding DMS plugins, supplied by the session module.

Ghostty is pinned to the shared upstream 1.4 release and launches with native
Wayland. `homeModules.fleetApps` supplies this package even when the consumer's
Nixpkgs has an older Ghostty. The `overlays.ghostty` export makes the same package
available to host configuration. A host with GPU overrides sets
`programs.hp-os-fleet.ghostty.package = pkgs.ghostty` after applying that overlay.
ARM64 includes the verified CPU frame presentation fallback for NVIDIA N1X;
Ghostty's OpenGL renderer stays active. GPU vendor paths remain host settings.

Mosh is installed by `homeModules.fleetApps` on ARM64 and x86-64, including
both `mosh` and `mosh-server`. Installer and updater generations consume this
same module. Sessions allow one week of network absence. Connect with
`mosh HOST -- tmux new-session -A -s work`. SSH starts the server; no persistent
Mosh service is required. The destination needs direct UDP connectivity on
60000–61000, or a selected range such as `mosh -p 60000:60019 HOST`.
Host modules own SSH and firewall policy. An SSH-only proxy does not carry
Mosh UDP traffic.

For a bounded interactive connection check, allocate a terminal and keep Mosh
in its foreground process group:

```sh
TERM=xterm-256color timeout --foreground 20 mosh HOST -- sh -c 'echo MOSH_OK; sleep 2'
```

Plain `timeout` creates a separate process group. Terminal job control can
suspend Mosh and its SSH child during startup, producing an apparent hang
after authentication. Use `timeout --foreground` for this check. Normal
interactive use is simply `mosh HOST`.

### Explicit Mosh access paths

The fleet also installs `fleet-mosh` and `fleet-mosh-server`. Standard `mosh`
keeps its usual behavior. A private consumer declares destinations:

```nix
programs.hp-os-fleet.mosh.hosts.example = {
  private = "example-private.example.org";
  tailscale = "example-tailnet.example.org";
  hostKeyAlias = "example";
  user = "operator";
};
```

`fleet-mosh example -- tmux new-session -A -s work` checks the private address,
then Tailscale, using a real short Mosh UDP session before starting the terminal.
`fleet-mosh --path private --check example` tests only the private destination;
use `--path tailscale` for the independent tailnet destination. Probes require
existing SSH trust and noninteractive authentication. They never accept new
host keys or print captured terminal output. Failed probes expire remotely after
15 seconds of network absence. Interactive sessions explicitly receive the
seven-day timeout, including SSH launches that do not source shell profiles.

The helper uses UDP 60000–60019 and disables SSH ProxyJump/ProxyCommand for these
direct destinations. The route to the private address still determines whether
LAN, WARP or WireGuard carries the traffic. DNS does not select among those
routes. Existing Cloudflare Access SSH and jump-host recovery remain separate.
Changing paths starts a new Mosh session; reattach the same tmux session to retain
work. The helper never changes routes or tears down an established session.

For a focused installation, build `.#fleet-mosh` on ARM64 or x86-64. Its config is
`~/.config/fleet-mosh/hosts.json`, or pass `--config FILE`. Home Manager writes this
file from the host mapping. Host addresses and identity remain outside this
public module. `fleet-mosh-server` is available as an explicit server executable;
ordinary `mosh` users can select it with `--server=fleet-mosh-server`.

## Agent command-line tools

`fleet/agents` wires the agent CLIs that every desktop should start the same
way. The module packages nothing. A consumer supplies the packages it already
builds, so the fleet keeps one copy of each package:

```nix
programs.hp-os-fleet.agents.packages = {
  pi = pi-engine;            # Pi coding agent
  piHarness = pi-harness;    # wrappers, settings, models
  deepseek = dsh;            # DeepSeek Harness CLI
  antigravity = antigravity-cli;  # provides `agy`, plus a `gemini` alias
  grok = grok-cli;           # Grok Build CLI
};
```

The module then supplies:

- `dsh-tui` and `dst`, with a user service that installs the terminal UI
  profile (`@deepseek-harness-tui/dsh-tui` 0.20.1) into the harness state
  directory.
- A `gemini` alias for `agy`.
- A Home Manager activation step that runs `pi-harness switch` when the
  provider keys exist.

Any package left `null` stays host-managed. With no packages the module is
inert, so a host that already owns the CLIs needs no opt-out.

Provider API keys are never part of this public flake. `pi-harness switch` reads
single-line key files from `agents.pi.secretRoot`, which defaults to
`~/.config/pi/secrets`. Provision `deepseek-api-key`, `kimi-k3-api-key`, and
`glm-coding-pro-api-key` with mode 0600, then either let activation run
`pi-harness switch` or run it by hand with `--secret-root`.

Set `agents.deepseek.home` when the host also runs a differently versioned
harness web service, so neither version migrates the other's sessions. Set
`agents.pi.switchOnActivation = false` when the host manages Pi settings itself.

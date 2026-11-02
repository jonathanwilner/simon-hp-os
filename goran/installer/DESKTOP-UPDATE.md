# Update Simon's HP-OS desktop

Simon uses the public repository [jonathanwilner/simon-hp-os](https://github.com/jonathanwilner/simon-hp-os),
branch `main`, and root flake output `.#homeConfigurations.simon-daytona`.

This updates the installed Ubuntu ARM64 desktop through Home Manager. Ubuntu
continues to manage the kernel, NVIDIA driver, login manager and system services.
The update does not rebuild the offline installer or change the boot configuration.

## First update

Log into Simon's account on the laptop. Keep a console available while updating.
The supported host is Ubuntu 26.04 ARM64 with NVIDIA driver 615.78.08. The original
Simon installer must already have installed the Ubuntu desktop prerequisites.

The repository and its dependencies are public. Cloning and updating require no
GitHub account or SSH key. Application sign-ins remain Simon's own.

```sh
mkdir -p ~/src
git clone --branch main \
  https://github.com/jonathanwilner/simon-hp-os.git ~/src/simon-hp-os
cd ~/src/simon-hp-os
bash goran/installer/update-desktop.sh
```

If the checkout already exists, preserve local changes, switch it to
`main`, and run the last command. The updater requires a clean
checkout and refuses unpublished local commits. It pulls with `--ff-only`, checks
that the required flake sources are tracked in Git, builds the locked desktop, and activates it only after
a successful build. It refuses activation under any account other than `simon`.

The first update requires `nix`, Git, `tmux`, and `nom` on PATH. The existing
profile normally provides them. The repository's `pkgs/nom-dashboard/nom-tmux.sh`
is the fallback when the `nom-tmux` command has not yet been installed.

Follow the attached build and activation log:

```sh
tmux attach -t update-simon-desktop
```

After success, save work and log out. Select **HP-OS (Simon N1X)** on the login
screen. The new compositor and touchscreen changes load with that login. Check
password unlock, touch-and-hold, application launching, audio and the default
file manager on Simon's physical machine.

## Later updates

Open **Update Applications** from the desktop launcher. The terminal shows the
tracked build and activation. After the Home Manager update succeeds, the command
updates Flatpak applications and runtimes in Simon's user installation. It uses
Simon's existing Flatpak remotes and credentials. A Flatpak failure is reported
separately; the successful Home Manager generation remains installed.

Open **Update Status** to see the installed desktop revision, user Flatpak
versions, cached pending Ubuntu packages and reboot status. The equivalent
read-only terminal command is `simon-desktop-update --status`.

The interactive Ubuntu update notifier is hidden in Simon's session. Ubuntu's
APT timers, unattended security updates and automatic Snap maintenance remain
unchanged. The application updater does not run APT, refresh system Flatpaks,
request sudo, stop Firefox or reboot the laptop.

The terminal equivalent of Update Applications is:

```sh
simon-desktop-update
```

The command uses `~/src/simon-hp-os`. To use another checkout, set
`SIMON_DESKTOP_CHECKOUT=/absolute/path` before calling it. The script also accepts
`--checkout PATH`.

Use the published lock file. Do not run `nix flake update` as the normal update
step: several reviewed dependencies use explicit revisions in `flake.nix`.
Maintainers publish updated source and lock files together on the update branch.

## Build without activation

An ARM64 builder such as Goran can validate Simon's profile without modifying
its own desktop:

```sh
bash goran/installer/update-desktop.sh --build-only
```

For a committed integration branch that has not been promoted yet:

```sh
bash goran/installer/update-desktop.sh --build-only --no-pull
```

The build-only path accepts another account. It never runs the activation script.

## Rollback and records

The updater keeps candidate and previous-generation garbage-collector roots,
source revision, and the update directory under
`~/.local/state/simon-desktop-update/<UTC timestamp>/`. After a successful update,
`~/.local/state/simon-desktop-update/current` points to that directory. It checks
that the active Home Manager profile points to the candidate. An activation
failure attempts to reactivate the previous generation.

To restore the generation preceding the last successful update, run this from
Simon's own console:

```sh
~/.local/state/simon-desktop-update/current/previous/activate
```

The `previous` link exists when a valid earlier Home Manager generation was
available. Save work and log out after restoring it. Home Manager backups of
conflicting files use the suffix `simon-update-<UTC timestamp>`.

Build logs and exit status are recorded by `nom-tmux`. Simon's profile starts with
local dashboard reporting; central dashboard upload needs a separately authorized
reporting account. The profile includes no dashboard upload credentials. A successful
build establishes package integrity. Physical desktop acceptance still requires
checks on Simon's laptop.

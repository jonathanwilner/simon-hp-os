# Simon: update the existing image with the touch desktop

Prepared 4 Nov 2026. Reviewed public source: `f7ee5ef` on
[jonathanwilner/simon-hp-os](https://github.com/jonathanwilner/simon-hp-os).

Simon can update his existing installation in place and keep his local source
changes. The command-line updater already uses a Nix flake and Home Manager.
Home Manager builds and activates the desktop in Simon's account. Ubuntu keeps
control of the kernel, NVIDIA driver, boot configuration and system services.
There is no need to reinstall the disk image for these desktop changes.

## What Simon receives

The published desktop includes compositor-level touch-and-hold for right-click
in native Wayland and XWayland applications, touchscreen gestures, and the same
long-press patches in the HDR compositor path. Touch support is enabled with the
laptop profile. The on-screen keyboard and automatic rotation remain Off.

The update also includes the current public application baseline, HP-OS icon
repairs, Microsoft 365 web launchers, search, COSMIC Files, Upscayl and the
wallpaper collection. Account enrollment remains personal. The selected wallpaper
is preserved. Optional remote-access setup is documented separately in
[the remote-access guide](../remote-access/README.md).

Published source and a successful build do not establish physical touch behavior
on Simon's machine. Simon should complete the checks below after logging in.

## Requirements

Use Simon's existing Ubuntu 26.04 ARM64 installation, account `simon`, home
`/home/simon`, and running NVIDIA driver `615.78.08`. Nix with flakes, Git,
Python 3, tmux and nom must already be available from the original installation.
The updater also checks native Ubuntu PAM, which supports password authentication.
Run from Simon's own login session without sudo. Save open work and keep a console
available. The profile is specific to Simon's N1X machine.

## Route 1: command-line installer and updater

Download the current updater, then run a build-only pass:

```sh
curl --fail --location --output /tmp/update-hp-os.sh \
  https://raw.githubusercontent.com/jonathanwilner/simon-hp-os/main/update-hp-os.sh
bash /tmp/update-hp-os.sh --build-only --attach
```

This creates or updates `~/src/simon-hp-os`, preserves supported local source
changes, merges public `main`, and builds the candidate. Build-only can change
the source checkout through the merge; it does not activate the desktop.

After the build succeeds, install the desktop update:

```sh
bash /tmp/update-hp-os.sh --attach
```

This fetches public `main` again, builds the merged result and activates it.
The activation pass can receive a newer upstream commit than the preview pass.
It retains recovery records and the preceding generation when available. The
update does not reboot or log out. After success, save work, log out and select
**HP-OS (Simon N1X)** at login so the new compositor loads.

The same updater is available as a ZIP at
[the HP-OS download page](https://files.thewilners.com/s/hp-os).
Extract it and run `bash update-hp-os.sh --attach` inside the extracted folder.
Use the live command above to fetch the current tool directly.

If Simon's old checkout is in a different location, identify it explicitly:

```sh
bash /tmp/update-hp-os.sh --from /absolute/path/to/old-checkout --build-only --attach
```

The default migration checks `~/src/nixos-amd` only when it contains Simon's
profile. The original checkout remains intact. An unknown baseline or unsupported
migration stops for review. Supply `--legacy-base COMMIT` only when the clean
baseline is known. Keep the recovery report instead of guessing a revision.

For later updates:

```sh
simon-desktop-update --attach
simon-desktop-update --status
```

**Update Applications** and **Update Status** provide the desktop equivalents.
The update also refreshes Simon's user Flatpaks after Home Manager succeeds.
Flatpak failures are reported separately from desktop activation.

## Keep and merge Simon's changes

The normal updater records uncommitted tracked and untracked source files in a
local recovery stash and commit, then merges public `main`. Local commits stay
in the branch. The updater never pushes Simon's local history or recovery copies.
Ignored files are outside the Git recovery snapshot.

Live configuration files managed by the candidate are archived before activation.
This is a backup, not a format-aware merge of live Niri or GTK settings. Review
important live edits and express lasting customizations in the source modules.

For an explicit review-first merge after the public checkout exists:

```sh
cd ~/src/simon-hp-os
git status --short
git diff
```

Review and commit intended local source edits before continuing. For example,
use `git add PATH` for each reviewed file, then `git commit`. Avoid committing
credentials or generated files. Once the checkout is clean:

```sh
git switch -c simon/touch-review-20261104
git branch simon-before-touch-20261104
git fetch origin main
git log --oneline HEAD..origin/main
git diff HEAD...origin/main -- goran/desktop vendor/HP-OSShell fleet flake.nix flake.lock
git merge --no-commit --no-ff origin/main
```

Use fresh branch names if those names already exist. Review the staged diff with
`git diff --cached`. If Git reports a conflict, use `git status`, edit each
conflicted file, and stage the resolved paths with `git add PATH`. Finish with
`git commit` when a merge is pending. If Git reports already up to date, no merge
commit is needed. To cancel an in-progress merge, use `git merge --abort`.

Build the exact committed integration branch without fetching again:

```sh
bash goran/installer/update-desktop.sh --build-only --no-pull --attach
```

When satisfied, use the normal guarded updater to activate:

```sh
bash goran/installer/update-desktop.sh --attach
```

That activation fetches and merges `main` again. `--no-pull` is deliberately
limited to build-only checks. Keep long-term customizations in this local branch
or a private fork. If `origin` points to a fork, the updater merges that fork's
`main`; maintain its relationship to the public upstream explicitly.

## Route 2: native Nix flake workflow

The existing repository is already the complete desktop flake. Its output is
`homeConfigurations.simon-daytona.activationPackage`. For source customizations,
merge the public repository as above and retain its reviewed `flake.lock`.
A direct, reproducible build from that clean checkout is:

```sh
cd ~/src/simon-hp-os
nom-tmux build-simon-touch -- nix build \
  .#homeConfigurations.simon-daytona.activationPackage \
  --no-update-lock-file --out-link result-touch
```

Follow the tracked task with `tmux attach -t build-simon-touch` while it runs.
Wait for its successful exit before proceeding. If `nom-tmux` is not installed,
use `bash pkgs/nom-dashboard/nom-tmux.sh` in its place.

Use `bash goran/installer/update-desktop.sh --attach` for activation. It adds
host checks, source-stability checks, live-file backups, generation records and
rollback handling around the same Nix build. Calling `result-touch/activate`
directly bypasses those protections and is outside this recommended procedure.

For an image pipeline that needs to pin the entire published desktop as an input,
this minimal flake exposes the existing Simon profile:

```nix
{
  description = "Pinned Simon HP-OS desktop";
  inputs.simon-desktop.url = "github:jonathanwilner/simon-hp-os";
  outputs = { simon-desktop, ... }: {
    homeConfigurations.simon-daytona =
      simon-desktop.homeConfigurations.simon-daytona;
  };
}
```

Run `nix flake lock` in that separate project, review and commit `flake.nix` and
`flake.lock`, then build the same output through `nom-tmux`. The lock records the
exact upstream revision. To advance this input later, run
`nix flake update simon-desktop`, review the lock diff, commit and rebuild.
This wrapper exposes the full fixed `simon` profile; use a source fork for changes
to that profile. It is an integration example, not a newly tested image installer.

For shared applications in a different Home Manager configuration, the public
flake also exports `homeModules.fleetApps`. That module supplies common apps and
wallpapers; importing it alone does not install the touch compositor or Simon's
complete desktop. See [fleet integration](../../fleet/README.md).

Within the Simon source checkout, normal updates merge the published source and
lock together. Avoid a blanket `nix flake update` as the routine desktop update:
it can advance dependencies beyond the reviewed combination.

## Verify and recover

After the new login, run `simon-desktop-update --status` and check:

- Touch-and-hold opens a context menu in COSMIC Files and a browser. Dragging and
  scrolling still work without an unwanted right-click.
- Touch gestures work in the selected session. The DMS Niri configuration maps
  three-finger horizontal swipes to view movement and left/right edge swipes to
  column focus. Check the HP-OS session's own gesture behavior separately.
- The laptop on-screen keyboard stays Off. Audio, Search, application launch,
  password lock/unlock and any local customizations still work.

Inspect the recorded desktop revision with:

```sh
cat ~/.local/state/simon-desktop-update/current/source-revision
```

Keep `~/.local/state/simon-desktop-update/` and its recovery refs until acceptance.
The `current` link records the last successful activation, so it can still refer
to an earlier run after a failed update. Check the latest task log as well.

If the last successful update has a `previous` generation, restore it from
Simon's own console:

```sh
~/.local/state/simon-desktop-update/current/previous/activate
```

Then save work and log out before returning to the desktop. Rollback restores the
Home Manager generation; local source merge history and user Flatpak updates
remain separate. Full recovery details are in
[DESKTOP-UPDATE.md](DESKTOP-UPDATE.md).

The update applies to an installed system. Rebuilding or capturing a distributable
disk image is a separate operation. Validate a new image on the target hardware
before distributing it. No fresh image or physical Simon-device acceptance was
performed for this documentation update.

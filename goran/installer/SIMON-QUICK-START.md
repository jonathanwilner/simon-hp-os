# Simon: update HP-OS on your existing Ubuntu machine

Download: **https://files.thewilners.com/s/hp-os**

## Before starting

Use your existing `simon` login on Ubuntu 26.04 ARM64 with NVIDIA driver
615.78.08. The original installation should already provide Nix, Git, Python 3
and tmux. Use an internet connection and save your work. Your own application
accounts and sign-ins remain yours. No private GitHub account or Tailscale
connection is needed to download the configuration.

## Load the update

1. Open the download link and save the ZIP.
2. Extract the ZIP. Open a terminal inside the `simon-hp-os-updater` folder.
3. Run this command as `simon`, without `sudo`:

```sh
bash update-hp-os.sh --attach
```

The tool creates or updates `~/src/simon-hp-os` and loads the currently published
public configuration. It builds the desktop before activating it. It leaves the
Ubuntu kernel, NVIDIA driver and boot configuration in place. It does not reboot
or close the desktop session.

If your old checkout is somewhere other than `~/src/nixos-amd`, specify it:

```sh
bash update-hp-os.sh --from /absolute/path/to/old-checkout --attach
```

Add `--build-only` to build without activating the desktop. If the terminal
closes while the task is running, reconnect with:

```sh
tmux attach -t update-simon-desktop
```

## Keep your changes

The tool detects the old `~/src/nixos-amd` checkout when it contains Simon's
profile. It leaves that checkout intact and tries to merge supported local
configuration changes into the public checkout. It never publishes your private
history, local commits or recovery copies.

The updater saves uncommitted tracked and untracked files in the public checkout
and records them in a local commit. It then merges the published update. Ignored
files stay in place. Existing live configuration files managed by the candidate
are backed up separately before activation. Live GTK and Niri file formats are
not merged automatically.

A conflict, unknown baseline or unsupported migration stops the update for
review before activation. Keep the reported recovery files. If you know the
clean baseline of your old checkout, supply `--legacy-base COMMIT` with `--from`.
Do not guess the baseline or discard changes to continue.

For a Git merge conflict, review the files listed by `git status`, resolve them,
then run `git add <resolved-files>` and `git commit` in `~/src/simon-hp-os`.
Rerun the updater afterward. `git merge --abort` cancels an active merge and
returns to the saved local configuration. Legacy migration conflicts produce a
review report and leave the public destination unchanged.

## After success

Save your work, log out, and choose **HP-OS (Simon N1X)** when logging back in.
Check taskbar Search, Super+S, Ask IQ, audio, touch-and-hold, password unlock and
your applications. The final ARM64 profile built successfully before handoff;
these physical checks still need to run on your machine.

For later updates, open **Update Applications**, or run `simon-desktop-update`.
Use **Update Status**, or `simon-desktop-update --status`, to inspect the result.
Keep recovery records under `~/.local/state/simon-desktop-update/` until you have
verified the updated desktop.

The previous generation, when available, can be restored from your own console:

```sh
~/.local/state/simon-desktop-update/current/previous/activate
```

Save work and log out after restoring it. Detailed backup, conflict and rollback
instructions are in [DESKTOP-UPDATE.md](DESKTOP-UPDATE.md).

Source: https://github.com/jonathanwilner/simon-hp-os

After this update, open **Set Up Remote Access** once and enter Simon's sudo password. This enables the Goran-matching Foundation Sunshine host and SSH. Tailscale is installed with its daemon running, and a fresh machine remains unenrolled. Open `https://localhost:47990` to create Sunshine credentials and pair Moonlight. Existing credentials and settings are preserved. See [remote access](../remote-access/README.md).

Open **Relay** to create your own clipboard account or join an existing account with its setup URL. Relay opens personal history on later launches. The first clipboard value is not uploaded. Account and setup links are excluded from clipboard history.

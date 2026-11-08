# Tested fleet releases

Shared desktop applications and launcher settings belong in this repository's
`fleet/` modules. Consumer repositories hold machine identity, hardware overrides,
credentials, and personal services. Publish a shared fix here before updating a
consumer lock file. Both the installer and updater must use the same release
selection policy.

## Release sequence

1. Commit a change in a dedicated branch. Push it to the fleet repository so the
   commit can be tested and reviewed on another machine.
2. The trusted local controller runs release checks for ARM64 and x86-64 at the
   exact submitted SHA. Ordinary ARM Linux builds run in Dropshot's Apple
   Virtualization guest. NVIDIA-specific builds and hardware checks run only on
   Goran for now. The configured x86-64 fleet host builds ordinary x86-64 packages.
   Validate the shared Home Manager configuration and launcher behavior.
3. Deploy that exact candidate revision to an ARM64 and x86-64 canary. Record
   application launch, the required display backend, and the active generation.
   A build result alone does not establish desktop acceptance.
4. Promote only the revision with successful checks and both canary results.
   Keep an immutable release tag. `fleet-stable` points to the promoted commit.
5. GitHub stores source commits, release refs and status evidence. GitHub-hosted
   runners do not build, test, or promote fleet releases.
6. Simon's updater fetches `fleet-stable`. Consumer repositories update their
   `desktop-fleet` lock input to the same commit, validate the resulting
   configuration, and push the lock changes. Activation follows each machine's
   documented deployment procedure.

Publishing a commit, promoting a release, updating a consumer, and activating a
machine are separate states. Report each state explicitly. Preserve the previous
working generation and the updater's configuration snapshots. Do not replace a
user's dirty checkout or restart the desktop to force a release through.

## Release status

`fleet/release/status.py` produces a readable report or JSON for an updater or
dashboard. It refreshes Git tracking refs without changing the working tree.
A network failure or missing activation evidence produces `unknown`.

For a shared fleet checkout:

```sh
python3 fleet/release/status.py --checkout ~/src/simon-hp-os \
  --installed-record ~/.local/state/simon-desktop-update/current
```

For a consumer checkout:

```sh
python3 fleet/release/status.py --checkout ~/src/nixos-amd \
  --consumer-lock ~/src/nixos-amd/goran/flake.lock \
  --installed-record ~/.local/state/hp-os-fleet/installed.json --json
```

Use `--input NAME` when the consumer's flake input has another name.
`--release-url URL` selects another fleet repository. An empty URL uses the
checkout's origin. `--offline` reads cached information and marks remote-dependent
checks unknown. `--check` returns 1 for drift and 2 for unknown evidence; normal
reporting returns 0 so an updater can display incomplete information.

The report separates:

- `working_tree`: uncommitted changes.
- `publication`: local commits absent from all fetched origin branches.
- `release_pin`: configured fleet revision versus the current stable release.
- `activation`: recorded installed revision versus configured revision, provided
  the active generation matches the activation record.

A commit published on a feature branch is `published` even when it is not in a
release. In that case `release_pin` still reports `differs`. This catches fixes
that were pushed but omitted from the deployed release.

## Activation evidence contract

The shared Home Manager activation records its fleet revision and generation.
Host wrappers can also record the source revision after their health checks.
Write a temporary file and rename it atomically. This record establishes
provenance; the canary probe separately establishes application acceptance:

```json
{
  "source_revision": "full consumer or shared-source commit SHA",
  "fleet_revision": "full shared fleet commit SHA",
  "generation": "/nix/store/...-home-manager-generation"
}
```

The default path is `$XDG_STATE_HOME/hp-os-fleet/installed.json`, falling back to
`~/.local/state/hp-os-fleet/installed.json`. The reporter checks the actual profile
at `~/.local/state/nix/profiles/home-manager`. Select another profile with
`--active-generation PATH`, including a system profile for a NixOS deployment.
A record whose generation differs from the active profile is `unknown`, including
a rollback that did not update the record. This prevents an old successful build
record from being presented as the running configuration.

Simon's existing update record directory is also supported. It contains
`source-revision`, `published-revision` (or `fleet-revision`), and a `candidate`
symlink. A local merged configuration can have a different source revision from
the published fleet revision; the report retains both values.

## Completion and recovery

A shared change is complete when the source commit is pushed, validation passes,
the exact candidate passes canary acceptance, the release is promoted, and
consumer lock updates are pushed. Report which machines have activated it.
Offline machines can remain pending and receive the tested release on their next
update. Never describe them as deployed without checking their active generation.

If a check fails, retain its logs and fix the candidate before promotion. If a
machine fails activation, keep or restore its previous generation using that
host's guarded deployment path. A release channel must not silently fall back to
an untested development branch when the stable branch is unavailable.

## Submission and consumer automation

Run `fleet-publish submit --checkout PATH` from a clean shared checkout. The
command runs unit tests and native architecture evaluation through `nom-tmux`,
verifies the source stayed unchanged, then fast-forward pushes main. Submission
uses `--evaluate-only`; it never builds package outputs on an arbitrary submitting
machine. The trusted local controller then runs the full build matrix on the
registered builders. Passing submission alone does not qualify a release.
`fleet-publish install-hook --checkout PATH` adds this action to main-branch commits while preserving the existing hook. Feature branches require
explicit submission. Shared Home Manager installations install the hook when the
configured `programs.hp-os-fleet.release.checkout` exists. A commit on a host-only
repository remains a host change; edit shared features in the shared repository.

The controller normally promotes automatically after full validation and both
canaries accept the exact revision. To request promotion explicitly on the
trusted writer, run:

```sh
fleet-publish promote FULL_SHA --config /path/to/controller.json
```

This starts `fleet-controller --revision FULL_SHA --promote-only` through
`nom-tmux`. The controller must find successful validation and canary evidence
for that exact SHA before publishing the stable ref and immutable tag. The
command never dispatches a GitHub Actions workflow. A queued local job is not a
successful release. Without `--config`, the command reads
`$XDG_CONFIG_HOME/hp-os-fleet/controller.json` or
`~/.config/hp-os-fleet/controller.json`. `--state` selects the controller's
persistent evidence directory.

`fleet-consumers --config FILE` runs through `nom-tmux` and reads a JSON object
with a `consumers` array. Each entry names `checkout`, `branch`, `flakes` (relative
directories), and `checks` (nonempty arrays of command arguments). It fetches the
stable SHA, updates only the registered lock files, runs all checks, commits and
pushes from an isolated worktree based on the registered remote branch. Dirty
source checkouts and failed checks stop that consumer. Local source branches
remain unchanged. A failed push retains the validated commit for a later retry.

Configure `programs.hp-os-fleet.release.consumers` on a trusted writer to run the
same reconciliation every 15 minutes. Credentials and private repository names
stay in that host's configuration. Activation remains a separate, host-specific
operation. The generation records its fleet revision under
`~/.local/state/hp-os-fleet/installed.json` for drift checks and canary evidence.

## Automatic promotion controller

A trusted writer sets `programs.hp-os-fleet.release.controller` with exactly two
`canaries`, keyed by `aarch64-linux` and `x86_64-linux`. Each supplies a consumer
registration, synchronous `deploy` command, `probe` command invoking
`fleet-launch-test --revision {revision} --system SYSTEM`, and `evidence_url`.
Optional `rollback` runs after a failed deployment or probe. Commands are argument
arrays; the controller replaces only `{revision}`. `consumers` lists remaining
lock consumers to update after promotion.

The controller fetches the exact current main SHA and runs the registered local
validation commands. The required validation keys are `aarch64-linux`,
`x86_64-linux`, and `nvidia`. The ARM builder host is Dropshot and the NVIDIA host
is Goran. Each validation command must finish successfully and produce evidence for that same SHA. Registration includes the
host and review URL. Missing, stale, failed or evaluation-only results cannot
qualify a release.

The controller then updates and validates each canary pin, deploys, and checks
fresh Ghostty and Moonlight windows through the installed Fuzzel helper. It
closes only its tagged test windows and never starts media playback. ARM desktop
and NVIDIA acceptance runs on Goran. Successful evidence is retained under
`~/.local/state/hp-os-fleet/controller/SHA/` and written into the tracked job log
before commit status publication. A failed attempt records a `.failed` file and
stops until the failure is inspected and that marker is cleared. No failed
candidate reaches the stable updater channel.

Promotion runs on the trusted writer and publishes the stable ref and immutable
release tag only after the local gates pass. The controller then reconciles the
remaining consumers. Its timer checks every ten minutes. The report timer runs
every thirty minutes and writes `latest-report.json` with separate publication,
release pin and activation states. Both jobs publish logs and status through the
existing build dashboard.

## Builder routing and NVIDIA boundary

Dropshot provides native `aarch64-linux` builds using Apple
Virtualization.framework. It has no NVIDIA device. Goran is the only authorized
host for NVIDIA-specific builds and runtime checks for now. Merely choosing an
ARM target does not establish that a package is safe to send to Dropshot.

The validation gate inspects the build dependency graph before dispatch. A
NVIDIA dependency must be routed to the registered Goran path; a generic builder
must fail closed if such a dependency would run there. Do not add a fallback
that sends NVIDIA work to Dropshot or another fleet host when Goran is offline.
A blocked NVIDIA gate holds promotion until Goran can complete it. Build success
still requires separate display, driver and application acceptance on Goran.

Private SSH keys, builder addresses and machine credentials remain in private
host configuration. The shared fleet repository contains the routing policy,
release tools and tests. Configure the client Nix daemon's SSH access explicitly;
interactive user SSH access alone does not prove daemon access.

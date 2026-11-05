# Full HP-OS desktop test VM

This disposable NixOS VM runs the production HP-OS shell and its Niri compositor,
with the shared AirDrop, Wi-Fi Aware printing and Relay Home Manager modules.
It provides a repeatable desktop for reviewing the control center, light and dark
appearance, window placement and scrolling. This exercises the installed desktop; it is separate from installer ISO and
bootloader validation. It does not emulate a NAN radio or
prove printer or Apple-device wireless interoperability.

## Build and launch

On an x86-64 Linux host with `/dev/kvm` and an accessible EGL render node at
`/dev/dri/renderD128`:

```sh
nom-tmux build-hpos-desktop-vm -- nix build \
  .#nixosConfigurations.hp-os-test.config.system.build.vm \
  --out-link result-desktop-vm
# Run after the build exits successfully. Keep the VM in a separate tmux session.
tmux new-session -d -s hp-os-desktop-vm ./tests/desktop-vm/run.sh
```

If QEMU reports `Failed to initialize io_uring: Cannot allocate memory`, use
`./tests/desktop-vm/run.sh --raise-memlock`. This runs `sudo prlimit` to raise only
the launch process's memory-lock limit. QEMU still runs as the current user.
Armstrong requires this because its interactive shell limit is 8 MiB. No global
host setting changes.

Niri requires GPU rendering. The VM uses virtio-vga-gl through the host EGL
render node; plain emulated VGA and a software-only guest renderer cannot drive
this desktop.

The VM uses four virtual CPUs and 6 GiB RAM. Its 12 GiB disk is sparse, and its
Nix store is shared read-only from the host. The output link preserves the built
closure. The launcher also roots the running VM closure so a later build cannot
make the active guest eligible for garbage collection. Runtime files and the generated SSH key stay under
`~/.local/state/hp-os-desktop-vm`, outside the repository. Override this directory
with `HPOS_VM_STATE` if needed. `HPOS_VM_RESULT` selects another built output.

The VM automatically signs into the `tester` desktop. It exposes these endpoints
only on the local host:

- SSH: `127.0.0.1:22291`, user `tester`.
- VNC: `127.0.0.1:5991`.
- QMP: `~/.local/state/hp-os-desktop-vm/qmp.sock`.

```sh
ssh -i ~/.local/state/hp-os-desktop-vm/id_ed25519 \
  -o UserKnownHostsFile=~/.local/state/hp-os-desktop-vm/known_hosts \
  -o StrictHostKeyChecking=accept-new -p 22291 tester@127.0.0.1
```

Password authentication is disabled. The generated public key is read from the
VM's shared runtime directory. `tester` has passwordless sudo inside this test VM.
Do not bind the forwarding ports to external interfaces or put production
credentials in the guest. The VM contains no personal account or host secrets.

## Review

Use the actual desktop and its control center. The guest contains `grim`, `jq`
and `foot`. Obtain the compositor's environment from the running session when
issuing shell IPC commands over SSH. Capture screenshots in the guest or through
QMP. Publish evidence through the repository's normal private debug gallery and
record exactly which shell revision and viewport were reviewed.

Check the initial desktop, control-center anchor, expanded printer content and
scrolling at 1280×800, and both light and dark appearance. Network capability
messages should report the VM's actual missing wireless hardware. Use physical
hosts for wireless acceptance tests.

Stop with `sudo poweroff` inside the guest. Keep the sparse disk to preserve test
settings. To reset, stop the VM first and move its disk aside before relaunching.
The next build and launch picks up the source revision under test.

# COSMIC Files on HP-OS

COSMIC Files uses the desktop's private D-Bus session. The shared fleet module
installs a config-only COSMIC settings daemon activation file. This serves COSMIC
configuration watchers while HP-OS/DMS retains input, audio, brightness and power
management. The theme activation seeds the installed COSMIC schema before applying
the HP-OS palette. Folder links use the current GVfs-enabled Files wrapper.

## Slow opening and closing with remote mounts

On Snapdragon on 11 Nov 2026, opening took 8–12 seconds and closing took
3.5–4.6 seconds. The GTK file chooser portal responded in about 4 milliseconds.
A syscall trace showed repeated synchronous `.Trash` and `.Trash-1000` probes on
9P mail and SSHFS Org mounts. One open/close trace spent 10.3 seconds probing the
mail mount and 2.7 seconds probing the Org mount. The autofs and mounted 9P entries
caused duplicate scans. Each mail probe required a network round trip.

An isolated mount-namespace test hiding only the mail mount from the test process
reduced opening to 2 seconds and closing to 1 second. The host mount remained
available to Emacs throughout. This test established the cause; hiding mail is
not the installed solution.

The fleet package filters remote and automount filesystems during Trash discovery.
It retains the full mount list for filesystem boundary and deletion decisions.
Remote file browsing and the existing mail and Org mounts remain available.
Remote Trash directories are omitted from the aggregate Trash view. Explicit
trash operations still use the original mount boundaries and move files into
the remote `.Trash-UID` directory when supported. No permanent-delete fallback
is added. Restore those remote items through the remote system or by browsing
its Trash directory. Local disk and USB Trash remain in the aggregate view.
The upstream report is https://github.com/pop-os/cosmic-files/issues/1986.

## Focused verification

1. Read the actual Niri session environment, including its private D-Bus address.
   Set the active Wayland display and Niri socket for diagnostic processes.
2. Time a fresh Files window and close only that test window.
3. Inspect logs for COSMIC watcher and theme-schema errors.
4. If delays remain, trace the launched process and its children with `strace
   -ff -tt -T`. Count remote `.Trash` probes and their cumulative duration.
5. Verify the existing mail mount and Org files remain readable. Do not remount,
   clear caches, or restart Emacs to test a file-manager change.
6. Capture the final window and publish it to the private debug gallery.

Portal routing and Secret Service providers are separate from Trash discovery.
Preserve the active session's credential provider and portal mappings unless a
specific failing portal operation is demonstrated.

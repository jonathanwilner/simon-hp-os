# Shared session services

Import `home.nix`, enable `programs.hp-os-fleet.session.enable`, and add a Niri
`spawn-at-startup` entry for `${config.programs.hp-os-fleet.session.package}/bin/hp-os-fleet-session-start`.
The DMS launcher can set GTK_IM_MODULE=fcitx, QT_IM_MODULE=fcitx and
XMODIFIERS=@im=fcitx when enabling the optional input method. Keep these unset
for HP-OS with its owned touch keyboard.

The supervisor supplies missing clipboard history, clipboard persistence, and
optional Fcitx5 input-method processes. It supplies CJK/emoji/terminal fonts,
screen recording, mirroring, and Wayland forwarding tools. Set
`programs.hp-os-fleet.session.inputMethod.enable` to enable Rime/Fcitx5 for a
DMS session. HP-OS owned sessions always retain their own touch-keyboard seat. Existing processes on the same display or bus remain authoritative. Services started here stop
when their Niri socket disappears. No DMS process, lock screen, power policy,
GPU override, personal credentials are installed. A polkit authentication agent starts only
when none is already running in the session.

HP-OS owned sessions keep their private D-Bus. Other Niri sessions publish their
Wayland environment to the user manager and start the graphical-session target
so existing fleet services can connect. Clipboard history is local in cliphist's
normal user cache; the helper does not enroll or enable remote clipboard sync.

# Native iMessage images alongside Mosh

`ost-imessage-mosh HOST` opens a dedicated tmux session over normal Mosh and
starts an authenticated SSH image helper. The printed session name can be used
with `--session NAME` to reconnect. The remote account needs the current
`teams-cli imessage` wrapper at `~/.local/bin/teams-cli`, plus `ost-kitty-bridge`.
The local terminal needs Kitty Unicode placeholders, such as Ghostty 1.4.

Mosh carries image placement as ordinary Unicode cells, RGB image IDs, and
combining marks. It does not carry image bytes. SSH carries a private per-pane
JSON manifest. The local helper validates PNG data and writes generated Kitty
virtual-placement commands directly to the local terminal owned by the Mosh
client. It accepts no terminal commands from the remote manifest.

The app only selects native mode when all clients viewing that pane have a
fresh matching helper heartbeat. Other clients retain the terminal-cell
fallback. A dedicated session keeps ordinary attached tmux clients independent.
Loss of the helper expires the heartbeat after eight seconds. SSH reconnects
rehydrate image data; restarting the app changes the manifest generation.
The helper ends when its originating local Mosh process ends.

For an existing connection, determine its local Mosh PID/TTY and the matching
remote tmux client PID. Matching UDP destination to the remote mosh-server PID
and its tmux process descendants gives a precise association. Then run:

```
ost-kitty-bridge --host HOST --pane %PANE --client-pid REMOTE_TMUX_PID \
  --tty /dev/pts/LOCAL_TTY --mosh-pid LOCAL_MOSH_PID
```

The remote `--serve` process owns a lock and heartbeat in
`/run/user/$UID/ost-kitty-bridge/pane-N/`. Files stay private to the account.
The manifest schema is `version: 1`, optional `generation`, and `images` with
`id`, `png_base64`, `columns`, `rows`. Limits are 24 images, 20 MiB per PNG,
64 MiB per manifest, 16 million pixels per image, and 64 columns by 63 rows.
Image IDs are in the RGB range 1–16777215.

The synthetic proof used unmodified Mosh 1.4.0 and Ghostty 1.4.0 on Goran.
It confirmed real Mosh preserves the placeholder and combining marks while
local Kitty uploads render an image. This is an application-specific helper,
not a native graphics patch to Mosh.

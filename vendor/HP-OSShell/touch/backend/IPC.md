# HP-OS native input bridge

`hp-os-input-backend --socket $XDG_RUNTIME_DIR/hp-os-touch/input.sock`
claims one input-method-v2 seat. It requires virtual-keyboard-v1 for navigation
and raw-key compatibility. `--probe` reports globals without claiming the seat.
The current implementation binds the compositor's first seat. Multiple seat
selection is not implemented; run only on a single-seat desktop.

The socket directory is 0700, the socket is 0600, peers must have the same UID,
and an advisory lock rejects duplicate backends. Never record IPC traffic:
commands, preedit and candidates can contain user text. Diagnostics contain
only fixed error codes and protocol booleans. The process does not log typed
text, surrounding text, candidates or commits. Rime diagnostics are limited to
fatal severity. Secure fields bypass Rime and clear composition. Manual raw
compatibility also disables composition/prediction because the application
has not supplied its content purpose.

Protocol: one JSON object per line. No input command is accepted without an
active text-input context, except when `manual` explicitly enables raw input.

Commands:

- `{"op":"text","text":"…"}` commits Unicode. In Chinese mode, ASCII is fed
  to librime and its actual candidates/preedit are emitted.
- `{"op":"key","key":"BackSpace","modifiers":[]}` uses XKB keysyms.
  Supported modifiers: `Shift`, `Control`, `Alt`, `Super`. Key commands are
  complete press/release pairs; UI repeat sends additional key commands.
- `{"op":"language","language":"zh_CN"}` or `en_US`. Chinese initialization
  deploys the installed Rime dictionary locally on first use.
- `{"op":"candidate","index":0}` selects an actual candidate on current page.
- `{"op":"page","direction":1}` or `-1` changes Rime candidate page.
- `{"op":"manual","enabled":true}` permits virtual-keyboard input when no
  text-input client is active. The controller must disable it when hiding.
- `{"op":"reset"}` discards composition and clears application preedit.
- `{"op":"prediction","enabled":true}` enables local English prefix completion.
  Completions use the packaged Hunspell word list and real surrounding text.
  They are dictionary matches, not statistical next-word prediction.
- `{"op":"status"}` requests the current state.

Events: `{type:"state", active, available, secure, manual, purpose, language,
preedit, candidates:[string], page, hasMore, serial, rimeReady}`. `purpose` uses
text-input-v3 enum numbers. `serial` counts input-method done events. Content
state is applied atomically on done. State events do not contain surrounding
text. Errors are `{type:"error",code:"fixed-code"}`.

The keyboard surface must use layer-shell keyboard interactivity `None`.
The bridge does not own a visible surface or grab the physical keyboard.
Squeekboard and Fcitx Wayland input-method must not run on the same seat as
this backend. Controller switches must stop one backend before starting the
other. An `unavailable` event means seat ownership conflict, not a reason to
start another competing input method.

Exit status: 2 missing protocols/display, 3 seat ownership conflict, 1 other
startup/runtime error. Never interpret raw virtual keyboard availability as
text-focus detection. `--probe` is read-only; it cannot establish seat ownership.

## Validation

Nix builds run the atomic protocol-state tests and a real librime test that
converts `nihao`, selects `你好`, and checks the resulting commit. The tests
use synthetic fixtures and disposable dictionaries.

For real Wayland input, launch a **disposable** Niri compositor, then run:

```
XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-N \
  python3 test_wayland.py /path/to/backend-package
```

This launches a Qt text-input client and the backend in the isolated compositor.
It checks English, Unicode, emoji, BackSpace, actual Pinyin candidates/commit,
secure-field bypass and focus changes. The fixture must have compositor focus.
Never run this input-injecting test against the user's normal compositor. The
helper exits both processes and writes no application text into diagnostics.
This is application input verification; it does not verify physical touch,
rotation, compositor gesture routing or the shell's QML visuals.

## Gesture decoding

`{op:"gesture",keys:["h","e","l","o"],points:[{x:0,y:0,t:0}]}` decodes
against the actual packaged English dictionary. Contiguous repeated keys are
collapsed. Candidates must match the first and last traced keys and pass a
weighted edit-distance threshold. This simple local decoder tolerates some
intervening keys. It has no language model, personalization or timing model;
ambiguous traces can produce poor ranking or no candidates. Candidate selection
commits the chosen actual dictionary word. Secure fields reject gesture input.

`--gesture-decoder /absolute/executable` optionally replaces the built-in
algorithm. The executable receives one JSON object on stdin with keys, points,
and language, and returns `{candidates:["actual","words"]}` on stdout. It runs
without a shell, with a two-second deadline and bounded result size. Output is
discarded after a focus/context change. Decoder stderr is discarded. Only use
a trusted local decoder: it receives the trace. No decoder is invoked for
password fields. The default decoder does not access the network.

State additionally includes `inputAllowed` (active field or explicit manual
compatibility) and `gestureAvailable` (dictionary or configured decoder ready).

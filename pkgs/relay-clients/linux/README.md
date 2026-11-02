# Relay on Linux

Enable `services.relayClipboard.enable` in Home Manager, then open **Relay** from the app launcher. First launch offers **Create my Relay account** or **Join an existing account**. Joining uses a setup URL generated on another enrolled device. Opening Relay again keeps the existing enrollment and opens account history in the browser.

The account page creates a single-use setup URL for another device and provides the personal history URL. These links grant account access. Relay excludes its setup and account links from clipboard history.

Runtime enrollment is under `~/.config/relay/` by default. `linux.json`, `device-token`, and `management-token` have mode `0600`. Credentials never enter the Nix store. Existing configurations and tokens remain intact; a disabled configuration stays disabled. Legacy configurations use their existing device token to open history; account administration follows the permissions granted by the server.

The launcher starts `relay-clipboard.service` with the current Wayland display. It records the display in a private runtime environment file and addresses the normal systemd user bus even when HP-OS runs on a private session bus. The first clipboard value is a baseline: only later copies are uploaded. Automatic remote clipboard replacement remains disabled; explicit deliveries still work.

Command-line enrollment: `relay --join 'https://clipboard-api.thewilners.com/#invite=…'`. An already enrolled client preserves its existing account even if given another invitation. Enrollment needs network access; an error leaves existing enrollment intact so Relay can be reopened.

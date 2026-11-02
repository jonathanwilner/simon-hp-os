# Simon's desktop applications

The `simon-apps.nix` module adds the seven pinned ARM64 ArtCraft applications,
Microsoft 365 document handlers, and the optional Relay clipboard service.
ArtCraft uses the NVIDIA shim already supplied by the N1X Home Manager profile.

Microsoft web links use Simon's own Chrome sign-in. To enable local document
uploads, follow [personal Office enrollment](../../pkgs/cloud-office-personal/README.md).
This is Simon's own OneDrive connection. It requires an authorized Microsoft
public-client application ID and Simon's delegated sign-in. Cloud documents
remain in OneDrive; edits are not automatically downloaded to the local original.

## Relay enrollment

Open **Relay** from the app launcher. Choose **Create my Relay account**, or
**Join an existing account** and paste a setup URL from your other device.
Relay saves private credentials, starts the clipboard service, and opens your
personal history. Later launches keep the same account. The account page creates
setup links for additional devices.

The first clipboard value is a baseline and is not uploaded. Later clipboard
copies go to your account. Account and setup links are excluded from history.
Automatic incoming clipboard replacement remains disabled; explicit deliveries
remain available.

Credentials and `linux.json` stay in `~/.config/relay/` with mode `0600`. They are
runtime data, not flake data. Existing enrollment is preserved. See the
[Linux Relay guide](../../pkgs/relay-clients/linux/README.md) for details.

Stop synchronization with `systemctl --user stop relay-clipboard.service`.
To keep it disabled on later logins, set `enabled` to `false` in the private
`linux.json` file and stop the service. Opening Relay preserves that disabled state.

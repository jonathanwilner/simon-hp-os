# Simon's desktop applications

The `simon-apps.nix` module adds the seven pinned ARM64 ArtCraft applications,
Microsoft 365 document handlers, and the optional Relay clipboard service.
ArtCraft uses the NVIDIA shim already supplied by the N1X Home Manager profile.

Microsoft web links use Simon's own Chrome sign-in. To enable local document
uploads, follow [personal Office enrollment](../../pkgs/cloud-office-personal/README.md).
This is Simon's own OneDrive connection. It requires an authorized Microsoft
public-client application ID and Simon's delegated sign-in. Cloud documents
remain in OneDrive; edits are not automatically downloaded to the local original.

## Optional Relay enrollment

The clipboard service stays inactive until Simon creates his own configuration.
Obtain a Relay service URL and a token for Simon's account from the service owner.
Create `~/.config/relay/linux.json` with this shape, replacing placeholders:

```json
{
  "enabled": true,
  "url": "https://YOUR-RELAY-SERVICE",
  "device_id": "simon-daytona",
  "device_name": "Simon Daytona",
  "token_file": "/home/simon/.config/relay/token",
  "auto_receive": false
}
```

Save the account token in the separate `token` file, then run:

```sh
chmod 700 ~/.config/relay
chmod 600 ~/.config/relay/linux.json ~/.config/relay/token
systemctl --user start relay-clipboard.service
```

The token and endpoint are private runtime configuration, not flake data.
Enrollment enables sending newly copied clipboard text to the selected account.
`auto_receive=false` keeps automatic incoming clipboard replacement disabled;
explicit deliveries remain available. Stop synchronization with
`systemctl --user stop relay-clipboard.service`, or set `enabled` to `false` and
remove the configuration file to keep the service inactive on future logins.

# Apple Account identity setup

OM Drop can use an Apple-issued AirDrop identity to send to Apple devices set
to **Contacts Only**. The fleet adds a setup panel, validated identity import,
expiry status and a return to the self-signed identity. The same implementation
is packaged for ARM64 and x86-64 Linux. Account files belong to the local user;
flake configuration contains no account, password or private key.

This setup imports an identity you already own. It does not sign in to Apple,
register an AirDrop identity, or ask for an Apple Account password. A normal Mac
with its default security settings cannot generally run the advanced exporter
included here. If you do not already have an identity or a suitable export
environment, use the self-signed mode and the Apple recipient's **Everyone for
10 Minutes** setting.

## Choose the setup that fits

| Need | Setup |
| --- | --- |
| Receive files without an Apple identity | Use the default self-signed identity. |
| Send to an Apple recipient set to Everyone | Use the default self-signed identity. |
| Send to an Apple recipient set to Contacts Only | Import a valid Apple identity. The recipient must recognize that account. |
| Restrict who can send to this Linux computer | Add known senders and select Contacts Only. This is independent of the computer's own Apple identity. |
| Store an existing identity in 1Password | Use upstream OM Drop's optional 1Password workflow. It may prompt when fetching credentials. |

For a recipient using a different Apple Account, their Contacts app must contain
the sender's Apple Account email address or phone number. The sender is the
account represented by the imported identity, which may differ from the Linux
computer's display name. [Apple's Contacts Only guidance](https://support.apple.com/en-lamr/guide/iphone/iphcd8b9f0af/ios).

## Import through the panel

1. Open **Omdrop AirDrop**, find **Apple Account**, and select **Set up**. Finish active
   transfers and stop receiving before importing or changing the identity.
2. Prepare a private folder containing these three files from one account:

   | File | Content |
   | --- | --- |
   | `certificate.pem` | AirDrop certificate with its intermediate certificate chain, in PEM format |
   | `key.pem` | Matching private key, in PEM format |
   | `validation_record.cms` | Apple-signed AirDrop validation record, in DER format |

3. Select the folder with **Import identity folder**. Read the result. Import must pass
   validation before the account becomes usable.
4. Check the displayed identity source and expiry, then enable AirDrop again.
   When receiving is active, the active source identifies the credentials held
   by that receive window.
5. Test a small file with the intended Apple recipient. Open its AirDrop share
   sheet, keep the devices nearby, and verify the received file.

Use only credentials from an account and device you control. These files allow
a process to present that AirDrop identity. Keep the folder outside repositories,
Nix expressions, public shares and support logs. The importer stores credentials
under the invoking user's home directory, not in the Nix store. Run the panel
and identity commands as that user, without `sudo`.

Import validates the whole trio before changing files and refuses to run while
receiving or sending is active. It installs files with mode `0600` under
`~/.omdrop/keys`, saves the previous trio and settings in a private backup under
`~/.local/state/omdrop-identity/`, and restores the previous state if final
validation fails. Backups also contain credentials and need the same protection.

The command-line equivalent is:

```sh
hp-os-omdrop-identity status --json
hp-os-omdrop-identity import /path/to/private-identity-folder --json
hp-os-omdrop-identity check --json
```

A valid identity is one prerequisite. It does not establish radio compatibility,
contact recognition or a completed transfer. A same-account Mac transfer does
not establish that another person's iPhone recognizes the sender as a contact.

## Advanced Mac exporter

The optional helper reads the current signed-in Mac account's AirDrop identity
through macOS Sharing and Security frameworks. It requires Xcode Command Line
Tools and private Apple entitlements that an ordinary ad-hoc signed application
cannot normally use. It is intended for an existing development environment
that already permits those entitlements. This setup does not disable System
Integrity Protection, change AMFI boot settings, modify keychain permissions,
or automate a security downgrade.

Open **Setup guide**, then **Save Mac helper…** to save the source bundle from
the panel, or run on Linux:

```sh
hp-os-omdrop-identity export-helper /path/to/existing-parent --json
```

This creates `omdrop-mac-helper` inside the selected parent and refuses an
existing destination. Copy that source folder to your own suitably configured
Mac. Use a new output
directory whose parent exists:

```sh
bash /path/to/omdrop-mac-helper/build-export.sh /path/to/new-private-output
```

If the Mac denies access, stop there and use another supported identity source
or self-signed mode. Entering an Apple password in a terminal does not grant the
private entitlement. The helper does not request keychain interaction and does
not overwrite an existing output directory. Transfer the resulting trio to the
Linux computer through a private, authenticated connection, then import it.
The exporter uses private APIs, so compatibility can change with macOS releases.

The older [SEEMOO research exporter](https://github.com/seemoo-lab/airdrop-keychain-extractor)
documents the same credential trio and the private-entitlement restriction. Its
security-changing procedure is outside this setup workflow.

## Contacts Only on the Linux receiver

The panel's **Visible to** choice controls incoming transfers to this computer.
It does not select the identity used to send. Configure the Apple Account
identifiers of people who may send, then choose Contacts Only:

```sh
omdrop senders add person@example.com
omdrop visibility contacts
```

Use the person's actual Apple Account email address or phone number in place of
the example. An empty known-senders list permits no senders. OM Drop checks the
sender's signed identity during an incoming transfer. Changing this list does
not import Apple's Contacts database or sign the Linux user into iCloud.
[Upstream Contacts Only behavior](https://github.com/netmojo-systems/omdrop-plugin#contacts-only).

To accept incoming transfers from everyone while receiving is enabled:

```sh
omdrop visibility everyone
```

## Expiry and renewal

The certificate and validation record can expire at different times. Use the
status dates and refresh an identity before the earliest applicable expiry.
Re-import all three files from the same account as one set. Never combine a
new record with an unrelated key or certificate.

Re-exporting on the Mac may return its cached record. Check that the new record
actually has later validity dates. This helper cannot force Apple to renew a
record and does not implement Apple Account enrollment. Expiry checks report
health; they do not manufacture a renewed identity. Do not interpret a successful
scheduled check as proof that renewal occurred.

Home Manager enables `hp-os-omdrop-identity-check.timer` daily. Set
`programs.hp-os-fleet.owly.identityExpiryNotifications = false;` to disable its
notifications. The standalone `omdrop-identity` flake package also provides the
CLI, but does not create a user timer on its own. The daily check notifies when
the selected disk identity is invalid or has seven days or less remaining. A manual notification check is:

```sh
hp-os-omdrop-identity check --notify --json
```

The setup preserves both the self-signed identity and the imported Apple trio.
Finish transfers and stop receiving before changing the source. To return to
the self-signed identity, select **Use basic identity** or run the command below,
then enable AirDrop again:

```sh
hp-os-omdrop-identity use-self-signed --json
```

Sending to an Apple recipient in Contacts Only then requires a valid Apple
identity again. For an immediate test in self-signed mode, ask that recipient to
select Everyone for 10 Minutes. Apple's temporary visibility setting expires;
check it again if discovery stops. [Apple AirDrop settings](https://support.apple.com/en-us/119857).

## Optional 1Password storage

Upstream OM Drop can move an existing identity into 1Password with
`omdrop identity 1password import`, or use an existing item with
`omdrop identity 1password use ITEM`. This obtains credentials from the vault,
not from Apple. The vault may require interactive authorization. Disk mode is
the setup panel's path for unattended use; it relies on the local user account's
file protections. Use `omdrop identity status --json` when diagnosing an existing
1Password configuration. [Upstream identity setup](https://github.com/netmojo-systems/omdrop-plugin#your-airdrop-identity).

## Troubleshooting and acceptance

| Result | Next action |
| --- | --- |
| No Apple identity configured | Import an existing valid trio, or use self-signed mode. |
| Identity invalid or expired | Obtain a complete current trio. Keep the last known-good files until the replacement passes. |
| Files exist but active source differs | Review the current receive window and restart receiving when transfers have finished. |
| Identity valid but recipient missing | Check radio status, proximity, the Apple recipient's visibility and contact card. Open its AirDrop share sheet. |
| Transfer says accepted but file is absent | Inspect the destination and transfer result. Discovery or acceptance alone is not success. |

For a complete test, send a small identifiable file, confirm it exists on the
recipient, and compare content or SHA-256. Repeat in the reverse direction if
both sending and receiving are required. Record which recipient enforced
Contacts Only and whether the devices used the same account. This distinguishes
radio transport, identity validation and contact recognition.

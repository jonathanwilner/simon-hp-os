# Personal Microsoft 365 document opener

This package opens Microsoft cloud links in the local managed Chrome profile.
Local documents upload to the signed-in user's own OneDrive under
`HP-OS Office/<content SHA-256>/<filename>` and then open in Word, Excel or
PowerPoint. Reopening the same original preserves its cloud edits. A changed
local document creates a separate copy. Uploads do not create public sharing
links. Files are limited to 250 MB. Download other web attachments locally first.

## Sign in for local document uploads

A Microsoft Entra administrator or an account allowed to register applications
must create a public desktop application for the intended Microsoft account.
Use a mobile/desktop platform with `http://localhost` as a redirect URI and the
Microsoft Graph delegated permission `Files.ReadWrite`. Use a single-tenant
registration for a managed company tenant, or the appropriate supported account
types for personal Microsoft accounts. Organization policy may require consent.
No client secret is used. Then run as Simon:

```sh
cloud-office-open --configure APPLICATION_CLIENT_ID --tenant TENANT_ID
cloud-office-open --login
```

Use `--tenant common` with a registration that supports the desired personal or
organizational accounts. Sign in using Simon's account. Browser document links
work without this upload enrollment; they use the browser's own sign-in.

Configuration and tokens stay in `~/.local/state/cloud-office-personal` with
private file permissions. They are never part of the flake, Git, or Nix store.
Running `--configure` again removes the cached tokens and selected account.
Authentication is serialized to avoid simultaneous token-cache writers.

This module replaces the Jonathan-specific Armstrong Office relay for Simon.
It does not access Armstrong, Jonathan's archive service, or Jonathan's OneDrive.
Live Microsoft account acceptance requires Simon's sign-in; mocked tests verify
routing, conflict behavior, private configuration and account-independent links.

The implementation follows Microsoft's [MSAL public-client API](https://learn.microsoft.com/en-us/python/api/msal/msal.application.publicclientapplication)
and [Graph upload-session API](https://learn.microsoft.com/en-us/graph/api/driveitem-createuploadsession).

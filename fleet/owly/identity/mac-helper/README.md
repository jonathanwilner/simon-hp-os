# Advanced Mac AirDrop identity exporter

Run this helper only on your own Mac, signed in to the Apple Account whose
AirDrop identity you want to use. It needs Xcode Command Line Tools and an
existing development environment that allows the private Apple entitlements in
`entitlements.plist`. Default macOS security normally prevents an ad-hoc signed
program from using them.

The helper does not change System Integrity Protection, AMFI, boot settings or
keychain access rules. If macOS denies access, use another supported identity
source or OM Drop's self-signed mode. This bundle does not provide Apple Account
login or enrollment.

Choose a new output directory. Its parent must already exist:

```sh
bash build-export.sh /path/to/new-private-output
```

The output contains `certificate.pem`, `key.pem` and `validation_record.cms`.
Keep these together. The directory is private and each file has mode `0600`.
The helper refuses to overwrite an existing destination and disables interactive
keychain authorization. Copy the files through an authenticated private
connection to the Linux computer and import them with OM Drop's Apple Account
setup panel. Do not put them in Git, the Nix store or a public share.

Re-exporting may return a cached validation record. Check its validity dates in
the import panel. This exporter does not force renewal. Private macOS APIs can
change, so an export failure may need a helper update.

# Keep the standard GTK portal wrappers and service layout. Pass the unmodified
# package explicitly so an overlay cannot accidentally recurse into itself.
{ portalGtk }:
portalGtk.overrideAttrs (old: {
  patches = (old.patches or [ ]) ++ [ ./network-file-chooser.patch ];
})

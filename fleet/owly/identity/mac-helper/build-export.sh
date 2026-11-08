#!/usr/bin/env bash
# Build on the Mac that owns the signed-in AirDrop identity; export to a new directory.
set -euo pipefail
umask 077

if [[ $# != 1 || $1 == -h || $1 == --help ]]; then
  echo "Usage: $0 NEW_OUTPUT_DIRECTORY" >&2
  echo "Output contains private credentials. Keep it outside source repositories." >&2
  exit 2
fi
if [[ $(uname -s) != Darwin ]]; then
  echo "This helper requires macOS and its native Sharing and Security frameworks." >&2
  exit 2
fi

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
case $1 in
  /*) output_dir=$1 ;;
  *) output_dir=$PWD/$1 ;;
esac
if [[ -e $output_dir || -L $output_dir ]]; then
  echo "Output directory already exists; refusing to overwrite." >&2
  exit 2
fi
if [[ ! -d $(dirname -- "$output_dir") ]]; then
  echo "The output directory's parent must already exist." >&2
  exit 2
fi

build_dir=$(mktemp -d "${TMPDIR:-/tmp}/omdrop-identity-build.XXXXXXXX")
trap 'rm -rf -- "$build_dir"' EXIT
/usr/bin/xcrun clang -framework Foundation -framework Security \
  -o "$build_dir/omdrop-export-apple-identity" "$source_dir/export.m"
/usr/bin/codesign -f -s - --entitlements "$source_dir/entitlements.plist" \
  "$build_dir/omdrop-export-apple-identity"
"$build_dir/omdrop-export-apple-identity" "$output_dir"

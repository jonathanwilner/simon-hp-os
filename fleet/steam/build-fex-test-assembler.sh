#!/usr/bin/env bash
# NASM 3.01 drops the operand-size prefix from `smsw bx` in FEX's 32-bit test.
# Use the upstream 2.16.03 assembler for reproducible test generation.
set -euo pipefail
export PATH=/usr/bin:/bin
version=2.16.03
prefix=$HOME/.local/opt/nasm-$version
source_dir=$HOME/src/nasm-fex-tests
archive=$source_dir/nasm-$version.tar.xz
mkdir -p "$source_dir"
if [[ ! -x $prefix/bin/nasm ]]; then
  curl -fL --retry 3 "https://www.nasm.us/pub/nasm/releasebuilds/$version/nasm-$version.tar.xz" -o "$archive"
  printf '%s  %s\n' 1412a1c760bbd05db026b6c0d1657affd6631cd0a63cddb6f73cc6d4aa616148 "$archive" | sha256sum -c -
  tar -xJf "$archive" -C "$source_dir"
  cd "$source_dir/nasm-$version"
  ./configure --prefix="$prefix"
  make -j "${FEX_BUILD_JOBS:-8}"
  make install
fi
"$prefix/bin/nasm" -v

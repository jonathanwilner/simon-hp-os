#!/usr/bin/env bash
# Run on Ubuntu ARM64 through nom-tmux. Keep upstream source unmodified.
set -euo pipefail
rev=14c92681f4d62cf84d901460e0358de09c8847a7
src=${FEX_SOURCE:-$HOME/src/FEX-latest}
prefix=${FEX_PREFIX:-$HOME/.local/opt/fex-$rev}
bash "$(dirname "${BASH_SOURCE[0]}")/build-fex-test-assembler.sh"
export PATH="$HOME/.local/opt/nasm-2.16.03/bin:/usr/bin:/bin"
export CC=/usr/bin/clang-21 CXX=/usr/bin/clang++-21
if [[ ! -d $src/.git ]]; then
  git clone https://github.com/FEX-Emu/FEX.git "$src"
fi
[[ $(git -C "$src" rev-parse HEAD) == "$rev" ]] || {
  git -C "$src" fetch origin "$rev"
  git -C "$src" checkout --detach "$rev"
}
git -C "$src" submodule update --init --recursive --depth 1
cmake -S "$src" -B "$src/build" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$prefix" \
  -DPython_EXECUTABLE=/usr/bin/python3 \
  -DCMAKE_ASM_NASM_COMPILER="$HOME/.local/opt/nasm-2.16.03/bin/nasm" \
  -DBUILD_TESTING=ON -DBUILD_FEXCONFIG=ON -DBUILD_THUNKS=OFF \
  -DENABLE_LTO=ON -DUSE_LINKER=lld-21 -DENABLE_ASSERTIONS=OFF
cmake --build "$src/build" --parallel "${FEX_BUILD_JOBS:-8}"
cmake --install "$src/build" --component Runtime
"$prefix/bin/FEXGetConfig" --version
printf '%s\n' "$rev" > "$prefix/upstream-revision"
# binfmt descriptions are installed only inside the isolated prefix.
# This script does not register any executable handler in the kernel.

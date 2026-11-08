#!/usr/bin/env bash
# Build upstream's Steam depot layout without installing into /usr or /.
set -euo pipefail
rev=14c92681f4d62cf84d901460e0358de09c8847a7
src=${FEX_SOURCE:-$HOME/src/FEX-latest}
depot=${FEX_STEAM_PREFIX:-$HOME/.local/opt/fex-steam-$rev}
export PATH=/usr/bin:/bin CC=/usr/bin/clang-21 CXX=/usr/bin/clang++-21
[[ $(git -C "$src" rev-parse HEAD) == "$rev" ]]
cmake -S "$src" -B "$src/build-steam" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr \
  -DBUILD_STEAM_SUPPORT=ON -DBUILD_TESTING=OFF -DBUILD_FEXCONFIG=OFF \
  -DBUILD_THUNKS=ON -DENABLE_CLANG_THUNKS=ON \
  -DENABLE_LTO=ON -DUSE_LINKER=lld-21 -DENABLE_ASSERTIONS=OFF
cmake --build "$src/build-steam" --parallel "${FEX_BUILD_JOBS:-8}"
DESTDIR="$depot" cmake --install "$src/build-steam" --component Runtime
printf '%s\n' "$rev" > "$depot/upstream-revision"

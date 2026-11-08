#!/usr/bin/env bash
set -euo pipefail
[[ $(uname -m) == aarch64 ]]
base=https://repo.steampowered.com/steamrt4/images
version=$(curl -fsSL "$base/latest-public-beta/VERSION.txt" | tr -d '\r\n')
[[ $version =~ ^4\.0\.[0-9]+\.[0-9]+$ ]]
cache="$HOME/.cache/steam-arm64-installer/runtime-$version"
mkdir -p "$cache" "$HOME/.local/share/Steam/steamapps/common"
cd "$cache"
curl -fsSLO "$base/$version/SHA256SUMS"
file=SteamLinuxRuntime_4-arm64.tar.xz
curl -fSL --retry 3 -o "$file" "$base/$version/$file"
grep "[ *]$file\$" SHA256SUMS | sha256sum -c -
tar -xJf "$file" -C "$HOME/.local/share/Steam/steamapps/common"
printf 'Installed official Steam Runtime ARM64 %s\n' "$version"

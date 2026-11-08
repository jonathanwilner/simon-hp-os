#!/usr/bin/env bash
set -euo pipefail
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
rev=14c92681f4d62cf84d901460e0358de09c8847a7
depot=$HOME/.local/opt/fex-steam-$rev
tool=$HOME/.local/share/Steam/compatibilitytools.d/fex-git-linux
[[ -x $depot/FEXCompatTool ]]
[[ -f $HOME/.fex-emu/RootFS/Ubuntu_24_04.sqsh ]]
mkdir -p "$tool"
install -m755 "$source_dir/fex-steam-launch.sh" "$tool/fex-launch"
install -m644 "$source_dir/gpu.py" "$tool/gpu.py"
cat > "$tool/compatibilitytool.vdf" <<'VDF'
"compatibilitytools"
{
  "compat_tools"
  {
    "fex_git_linux"
    {
      "install_path" "."
      "display_name" "FEX Git 2610 - Linux x86 on ARM64"
      "from_oslist" "linux"
      "to_oslist" "linux"
    }
  }
}
VDF
cat > "$tool/toolmanifest.vdf" <<'VDF'
"manifest"
{
  "commandline" "/fex-launch %verb% --"
  "version" "2"
  "use_tool_subprocess_reaper" "1"
}
VDF
printf '%s\n' "$rev" > "$tool/upstream-revision"
"$tool/fex-launch" run /usr/bin/uname -m

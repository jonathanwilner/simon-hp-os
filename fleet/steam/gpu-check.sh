#!/usr/bin/env bash
set -euo pipefail
export PATH=/usr/bin:/bin
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
python3 "$source_dir/gpu.py"
printf 'Kernel page size: '; getconf PAGESIZE
# Loader reports prove the GPU selected, not merely the presence of an ICD.
summary=$(python3 "$source_dir/gpu.py" --exec vulkaninfo --summary)
printf '%s\n' "$summary"
if ! grep -Eq 'deviceType.*(DISCRETE_GPU|INTEGRATED_GPU)' <<< "$summary"; then
  echo 'No hardware Vulkan GPU reported; acceleration remains unavailable.' >&2
  exit 1
fi
if [[ -n ${DISPLAY:-} ]]; then
  python3 "$source_dir/gpu.py" --exec glxinfo -B
fi

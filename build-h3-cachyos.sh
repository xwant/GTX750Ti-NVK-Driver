#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
work=${GM107_H3_WORKDIR:-"$root/work-h3"}
export GM107_WSI=${GM107_WSI:-1}
bash "$root/ci/build_mesa.sh" h3 "$work" "" "${GM107_MESA_MIRROR:-}"
printf '\nPrivate H3 build ready: %s\nNo install performed. Diagnostics require NVK_SHADER_TELEMETRY=true.\n' "$work"

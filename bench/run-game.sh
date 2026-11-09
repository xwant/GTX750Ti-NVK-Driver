#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
work=${GM107_WORKDIR:-"$root/work"}
[[ $# -ge 3 ]] || { echo "Usage: bash run-game.sh nvidia|base|off|cap RUN_ID GAME [ARGS...]" >&2; exit 2; }
mode=$1
runid=$2
shift 2
[[ $runid =~ ^[a-zA-Z0-9_-]+$ ]] || exit 2
driver=$(basename -- "$(readlink -f /sys/bus/pci/devices/0000:01:00.0/driver)")
unset NVK_GM107_CMD_CACHE_LIMIT_KIB VK_ICD_FILENAMES
case "$mode" in
  nvidia)
    [[ $driver == nvidia ]] || { echo "Expected loaded nvidia driver" >&2; exit 1; }
    export VK_DRIVER_FILES=/usr/share/vulkan/icd.d/nvidia_icd.json
    ;;
  base|off|cap)
    [[ $driver == nouveau ]] || { echo "Nouveau is not loaded. This script never switches drivers." >&2; exit 1; }
    variant=patched
    [[ $mode != base ]] || variant=base
    export VK_DRIVER_FILES="$work/mesa-$variant/build-gm107/src/nouveau/vulkan/nouveau_devenv_icd.x86_64.json"
    [[ -f $VK_DRIVER_FILES ]] || { echo "Build ICD missing: $VK_DRIVER_FILES" >&2; exit 1; }
    [[ $mode != cap ]] || export NVK_GM107_CMD_CACHE_LIMIT_KIB=256
    ;;
  *) exit 2 ;;
esac
run="$root/logs/${mode}_${runid}"
[[ ! -e $run ]] || { echo "Run exists; choose another RUN_ID" >&2; exit 1; }
mkdir -p "$run"
case "$run" in *,*) echo "Use a path without commas for MangoHud" >&2; exit 1;; esac
cat > "$run/MangoHud.conf" <<EOF
log_interval=0
log_duration=120
output_folder=$run
gpu_stats
gpu_temp
gpu_core_clock
gpu_mem_clock
vram
ram
frametime
EOF
export MANGOHUD_CONFIGFILE="$run/MangoHud.conf"
unset MANGOHUD_CONFIG
date -Is > "$run/start.txt"
vulkaninfo --summary > "$run/vulkan.txt" 2>&1
printf "%s\n" "$mode" > "$run/mode.txt"
printf "%q " "$@" > "$run/command.txt"
echo "Warm the same scene first. Press Left Shift+F2 to record 120 seconds."
exec mangohud "$@"
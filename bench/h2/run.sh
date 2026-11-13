#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
work=${GM107_H2_WORKDIR:-"$root/work-h2"}; work=$(cd "$work" && pwd)
mode=${1:?base|off|on|diag|diag-on}; run=${2:?unique-run-name}; shift 2
[[ "$run" =~ ^[A-Za-z0-9_.-]+$ && "$run" != . && "$run" != .. && $# -gt 0 ]]
case "$mode" in
 base) variant=base; flags= ;;
 off) variant=h2; flags= ;;
 on) variant=h2; flags=gm107_ubo_cbuf ;;
 diag) variant=h2; flags=gm107_ubo_diag ;;
 diag-on) variant=h2; flags=gm107_ubo_diag,gm107_ubo_cbuf ;;
 *) exit 2 ;;
esac
driver=$(basename "$(readlink -f /sys/bus/pci/devices/0000:01:00.0/driver)")
[[ "$driver" == nouveau ]] || { echo "Kernel binding: $driver. Use your existing Nouveau boot manually; no changes made." >&2; exit 77; }
[[ -f "$work/icd/$variant.json" ]]
mkdir -p "$work/results" "$work/cache/$mode"; out="$work/results/$run"; mkdir "$out"
export VK_DRIVER_FILES="$work/icd/$variant.json" VK_ICD_FILENAMES="$work/icd/$variant.json" NVK_DEBUG="$flags" MESA_SHADER_CACHE_DIR="$work/cache/$mode"
unset NAK_DEBUG NVK_GM107_CMD_CACHE_LIMIT_KIB MESA_SHADER_CACHE_DISABLE
if [[ "$mode" == diag* ]]; then export MESA_SHADER_CACHE_DISABLE=true; fi
printf 'mode=%s\nICD=%s\nflags=%s\ncache=%s\n' "$mode" "$VK_DRIVER_FILES" "$NVK_DEBUG" "$MESA_SHADER_CACHE_DIR" > "$out/launch.txt"
cp "$work/logs/library-$variant.sha256" "$out/"
expected="$work/mesa-$variant/build-h2/src/nouveau/vulkan/libvulkan_nouveau.so"
checksum=$(cut -d ' ' -f1 "$work/logs/library-$variant.sha256")
set +e
python3 "$root/bench/h2/launch_verified.py" --out "$out" --expected "$expected" --checksum "$checksum" -- "$@"
status=$?
set -e
# The collector reports unverified coverage explicitly; performance consumers
# must require verification.json=verified rather than interpreting silence.
cat "$out/stdout.txt"; tail -20 "$out/stderr.txt" >&2
if [[ "$mode" == diag* ]]; then python3 "$root/bench/h2/summarize_c0.py" "$out/stderr.txt" > "$out/c0-summary.json"; fi
echo "Records: $out" >&2
exit "$status"
